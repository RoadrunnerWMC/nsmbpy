"""
This file implements a generic object-oriented struct system.
"""

import enum
import struct
from typing import Any, Dict, Generic, List, Literal, TypeVar, Union

from . import _common


FT = TypeVar('FT')  # "field type"
class StructField(Generic[FT]):
    """
    Base class for a struct field
    """

    def get(self, data: bytes) -> FT:
        raise NotImplementedError

    def set(self, data: bytearray, value: FT) -> None:
        raise NotImplementedError

    def empty_value(self) -> FT:
        raise NotImplementedError


class BytestringField(StructField[bytes]):
    """
    Simple StructField subclass that just returns raw bytestrings
    """
    offset: int
    length: int

    def __init__(self, offset, length):
        super().__init__()
        self.offset = offset
        self.length = length

    def get(self, data: bytes) -> bytes:
        return bytes(data[self.offset : self.offset + self.length])

    def set(self, data: bytearray, value: bytes) -> None:
        data[self.offset : self.offset + self.length] = value

    def empty_value(self) -> bytes:
        return b'\0' * self.length

    def decode(self, encoding: str) -> 'StringField':
        """
        Decode to a string when loading the field.
        This is a fluent interface.
        """
        return StringField(self, encoding)


class StringField(StructField[Union[str, bytes]]):
    """
    Wrapper field type for casting a (null-padded, fixed-length) BytestringField to a str.
    If decoding fails, returns the (null-rstripped) bytes instead.
    """
    parent: BytestringField
    encoding: str

    def __init__(self, parent, encoding):
        self.parent = parent
        self.encoding = encoding

    def get(self, data: bytes) -> Union[str, bytes]:
        field_data = self.parent.get(data)
        try:
            return _common.decode_null_terminated_string_from(field_data, 0, self.encoding, fixed_length=self.parent.length)
        except UnicodeDecodeError:
            return field_data.rstrip(b'\0')

    def set(self, data: bytearray, value: Union[str, bytes], *, enforce_null_termination_on_bytes=True) -> None:
        if isinstance(value, str):
            value_bytes = (value + '\0').encode(self.encoding)
        elif enforce_null_termination_on_bytes and b'\0' not in value:
            value_bytes += b'\0'

        if len(value_bytes) < self.parent.length:
            value_bytes = value_bytes.ljust(self.parent.length, b'\0')

        if len(value_bytes) > self.parent.length:
            raise ValueError(
                f"Unable to set string field to {value!r}, as encoded form {value_bytes!r} can't fit into {self.parent.length} bytes")

        assert len(value_bytes) == self.parent.length
        self.parent.set(data, value_bytes)

    def empty_value(self) -> str:
        return ''



class NumericField(StructField[FT]):
    """
    StructField subclass that deals with numeric types loaded by struct.unpack().
    """
    offset: int
    type: type

    # Must be defined in subclasses
    endianness: Literal['<', '>']
    format_char: str

    def __init__(self, offset):
        self.offset = offset

    def __init_subclass__(cls, **kwargs):
        """
        Get the endianness and struct-format-string-character arguments
        from the class definition, and apply them.
        """
        EMPTY = object()

        endianness = EMPTY
        format_char = EMPTY
        type_ = EMPTY

        if 'endianness' in kwargs:
            endianness = kwargs.pop('endianness')
        if 'format_char' in kwargs:
            format_char = kwargs.pop('format_char')
        if 'type' in kwargs:
            type_ = kwargs.pop('type')

        super().__init_subclass__(**kwargs)

        if endianness is not EMPTY:
            cls.endianness = endianness
        if format_char is not EMPTY:
            cls.format_char = format_char
        if type_ is not EMPTY:
            cls.type = type_

    def format_string(self) -> str:
        """
        Get the format string representing this field
        """
        return self.endianness + self.format_char

    def get(self, data: bytes) -> FT:
        """
        Retrieve the field's value
        """
        return struct.unpack_from(self.format_string(), data, self.offset)[0]

    def set(self, data: bytearray, value: FT, *, bitmask:int=-1) -> None:
        """
        Given a bytearray and a new value, insert it into the bytearray
        """
        format_string = self.format_string()

        # If there's an interesting bitmask, make sure to avoid
        # overwriting any data not included in the mask
        if bitmask != -1:
            orig_value, = struct.unpack_from(format_string, data, self.offset)
            value = (value & bitmask) | (orig_value & ~bitmask)

        # Pack into struct
        try:
            struct.pack_into(format_string, data, self.offset, value)
        except struct.error:
            raise ValueError(f'struct.pack_into({format_string!r}, {data!r}, {self.offset!r}, {value!r})')

    def empty_value(self) -> FT:
        return self.type(0)


class IntegralNumericField(NumericField[int]):
    """
    NumericField subclass that deals with integral types.
    This adds various transformations, both with the transform() method
    and as a fluent interface.
    """
    type = int

    def mask(self, bitmask: int) -> 'NumericFieldMask':
        """
        Apply a bitmask transformation when loading the field.
        This is a fluent interface.
        """
        return NumericFieldMask(self, bitmask)

    def lshift(self, amount: int) -> 'NumericFieldLshift':
        """
        Apply a left-shift transformation when loading the field.
        This is a fluent interface.
        """
        return NumericFieldLshift(self, amount)

    def rshift(self, amount: int) -> 'NumericFieldRshift':
        """
        Apply a right-shift transformation when loading the field.
        This is a fluent interface.
        """
        return NumericFieldRshift(self, amount)

    def bool(self) -> 'NumericFieldBool':
        """
        Apply a bool transformation when loading the field.
        This is a fluent interface.
        """
        return NumericFieldBool(self)

    def mask_bool(self, mask:int=1) -> 'NumericFieldBool':
        """
        mask should have exactly one bit set (i.e. it is 1 << x for some x).
        This function is then a shortcut for self.rshift(x).mask(1).bool().
        """
        assert bin(mask).count('1') == 1
        num_trailing_zeros = len(bin(mask)) - len(bin(mask).rstrip('0'))
        return self.rshift(num_trailing_zeros).mask(1).bool()

    def enum(self, enum_type: type) -> 'NumericFieldEnum':
        """
        Apply a transformation to enum when loading the field.
        This is a fluent interface.
        """
        return NumericFieldEnum(self, enum_type)


# Create subclasses of NumericField implementing all interesting struct
# format-string characters
class BE_U8(IntegralNumericField, endianness='>', format_char='B'): pass
class BE_S8(IntegralNumericField, endianness='>', format_char='b'): pass
class BE_U16(IntegralNumericField, endianness='>', format_char='H'): pass
class BE_S16(IntegralNumericField, endianness='>', format_char='h'): pass
class BE_U32(IntegralNumericField, endianness='>', format_char='I'): pass
class BE_S32(IntegralNumericField, endianness='>', format_char='i'): pass
class BE_U64(IntegralNumericField, endianness='>', format_char='Q'): pass
class BE_S64(IntegralNumericField, endianness='>', format_char='q'): pass
class BE_F32(IntegralNumericField, endianness='>', format_char='f'): pass
class BE_F64(IntegralNumericField, endianness='>', format_char='d'): pass
class LE_U8(IntegralNumericField, endianness='<', format_char='B'): pass
class LE_S8(IntegralNumericField, endianness='<', format_char='b'): pass
class LE_U16(IntegralNumericField, endianness='<', format_char='H'): pass
class LE_S16(IntegralNumericField, endianness='<', format_char='h'): pass
class LE_U32(IntegralNumericField, endianness='<', format_char='I'): pass
class LE_S32(IntegralNumericField, endianness='<', format_char='i'): pass
class LE_U64(IntegralNumericField, endianness='<', format_char='Q'): pass
class LE_S64(IntegralNumericField, endianness='<', format_char='q'): pass
class LE_F32(IntegralNumericField, endianness='<', format_char='f'): pass
class LE_F64(IntegralNumericField, endianness='<', format_char='d'): pass
U8 = BE_U8
S8 = BE_S8


class NumericFieldMask(IntegralNumericField):
    """
    Wrapper field type for masking the value of an IntegralNumericField.
    """
    parent: IntegralNumericField
    bitmask: int

    def __init__(self, parent, bitmask):
        self.parent = parent
        self.bitmask = bitmask

    def get(self, data: bytes) -> int:
        return self.parent.get(data) & self.bitmask

    def set(self, data: bytearray, value: int, *, bitmask:int=-1) -> None:
        self.parent.set(data, value & self.bitmask, bitmask=(bitmask & self.bitmask))


class NumericFieldLshift(IntegralNumericField):
    """
    Wrapper field type for left-shifting the value of an IntegralNumericField.
    """
    parent: IntegralNumericField
    amount: int

    def __init__(self, parent, amount):
        self.parent = parent
        self.amount = amount

    def get(self, data: bytes) -> int:
        return self.parent.get(data) << self.amount

    def set(self, data: bytearray, value: int, *, bitmask:int=-1) -> None:
        self.parent.set(data, value >> self.amount, bitmask=(bitmask >> self.amount))


class NumericFieldRshift(IntegralNumericField):
    """
    Wrapper field type for right-shifting the value of an IntegralNumericField.
    """
    parent: IntegralNumericField
    amount: int

    def __init__(self, parent, amount):
        self.parent = parent
        self.amount = amount

    def get(self, data: bytes) -> int:
        return self.parent.get(data) >> self.amount

    def set(self, data: bytearray, value: int, *, bitmask:int=-1) -> None:
        self.parent.set(data, value << self.amount, bitmask=(bitmask << self.amount))


class NumericFieldBool(StructField[bool]):
    """
    Wrapper field type for casting an IntegralNumericField to bool.
    """
    parent: IntegralNumericField

    def __init__(self, parent):
        self.parent = parent

    def get(self, data: bytes) -> bool:
        return bool(self.parent.get(data))

    def set(self, data: bytearray, value: bool, *, bitmask:int=-1) -> None:
        self.parent.set(data, (1 if value else 0), bitmask=bitmask)

    def empty_value(self) -> bool:
        return False


ET = TypeVar('ET')  # "enum type"
class NumericFieldEnum(StructField[ET]):
    """
    Wrapper field type for casting an IntegralNumericField to an IntEnum
    subclass.
    """
    parent: IntegralNumericField
    enum_type: type

    def __init__(self, parent, enum_type):
        self.parent = parent
        self.enum_type = enum_type

    def get(self, data: bytes) -> Union[ET, int]:
        value = self.parent.get(data)
        try:
            return self.enum_type(value)
        except ValueError:
            return value

    def set(self, data: bytearray, value: Union[ET, int], *, bitmask:int=-1) -> None:
        if isinstance(value, int):
            self.parent.set(data, value, bitmask=bitmask)
        else:
            self.parent.set(data, value.value, bitmask=bitmask)

    def empty_value(self) -> Union[ET, int]:
        try:
            return self.enum_type(0)
        except ValueError:
            return 0


class BaseStruct:
    """
    An abstract class representing a struct.
    In this system, a "struct" is defined as a wrapper around a
    fixed-length bytearray, adding access to named "fields" that can
    get/set portions of the data.
    Fields need not cover the entirety of the data, and they're also
    allowed to overlap.
    This is a wrapper rather than a bytearray subclass because we don't
    support everything bytearray does (for example, because we have a
    fixed length, `<BaseStruct> += b'\0'` is illegal)
    """
    raw_data: bytearray

    # These must be statically defined in subclasses
    raw_data_length: int
    fields: Dict[str, StructField]

    def __init__(self, data:bytes=None, **kwargs):
        if not hasattr(self, 'raw_data_length'):
            raise ValueError(f'BaseStruct subclass ("{type(self).__name__}") must define raw_data_length')
        if not hasattr(self, 'fields'):
            raise ValueError(f'BaseStruct subclass ("{type(self).__name__}") must define fields')

        if data is None:
            # New empty bytearray
            self.raw_data = bytearray(self.raw_data_length)
        else:
            # Make a copy of the data even if it's already a bytearray
            self.raw_data = bytearray(data)

        # (can only do this after self.raw_data has been initialized)
        # If self.fields includes any field names of actual existing
        # class members (e.g. "__init__"), raise an error
        for field_name in self.fields:
            if field_name in vars(self):
                raise ValueError(f'BaseStruct subclass ("{type(self).__name__}") includes illegal field "{field_name}"')

        # Set any initial field values
        for key, value in kwargs.items():
            self.set(key, value)

    def _assert_field_exists(self, name: str) -> None:
        """
        Raise a ValueError if the specified field name doesn't exist
        """
        if name not in self.fields:
            raise ValueError(f'"{name}" is not a field of "{type(self).__name__}"')

    def get(self, key: str) -> Any:
        """
        Get the current value of a field
        """
        self._assert_field_exists(key)
        return self.fields[key].get(self.raw_data)

    def set(self, key: str, value: Any) -> None:
        """
        Set a field to a new value
        """
        self._assert_field_exists(key)
        self.fields[key].set(self.raw_data, value)

    def __getattr__(self, key: str) -> Any:
        if key == 'raw_data':
            return self.__dict__['raw_data']
        try:
            return self.get(key)
        except ValueError:
            raise AttributeError(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key == 'raw_data':
            # Ensure it's a bytearray
            if not isinstance(value, bytearray):
                try:
                    value = bytearray(value)
                except TypeError:
                    raise TypeError(f'Can\'t set struct raw data to "{value}"')

            # Ensure it has the correct length
            if len(value) != self.raw_data_length:
                raise ValueError(
                    f'Attempting to set struct raw_data to a value of wrong length ({len(value)} instead of {self.raw_data_length})')

            # Set it
            self.__dict__['raw_data'] = value
            return

        # This allows @properties to work correctly
        # Yes, it looks a bit gross
        elif hasattr(self.__class__, key) and hasattr(getattr(self.__class__, key), '__set__'):
            getattr(self.__class__, key).__set__(self, value)
            return

        try:
            self.set(key, value)
        except ValueError:
            raise AttributeError(key)

    def __str__(self) -> str:
        return f'<{type(self).__name__}: {self.raw_data.hex()}>'
    def __repr__(self) -> str:
        return f'{type(self).__name__}({_common.short_bytes_repr(self.raw_data)})'

    # Define a bunch of dunder methods that allow us to behave more like
    # the bytearray we wrap
    def __bytes__(self) -> bytes:
        return bytes(self.raw_data)
    def __lt__(self, other) -> bool:
        return self.raw_data < other
    def __le__(self, other) -> bool:
        return self.raw_data <= other
    def __eq__(self, other) -> bool:
        return self.raw_data == other
    def __ne__(self, other) -> bool:
        return self.raw_data != other
    def __gt__(self, other) -> bool:
        return self.raw_data > other
    def __ge__(self, other) -> bool:
        return self.raw_data >= other
    def __bool__(self, other) -> bool:
        return bool(self.raw_data)
    def __len__(self) -> int:
        return self.raw_data_length
    def __getitem__(self, key: Any) -> Any:
        return self.raw_data[key]
    def __setitem__(self, key: Any, value: Any) -> None:
        self.raw_data[key] = value


def create_basestruct_subclass(name: str, raw_data_length: int, fields: Dict[str, StructField], *, mixins:List[type]=None) -> type:
    """
    Dynamically create a new subclass of BaseStruct
    """
    if mixins is None:
        mixins = []

    return type(
        name,
        (BaseStruct, *mixins),
        {
            'raw_data_length': raw_data_length,
            'fields': fields,
        },
    )


def load_struct_array(data: bytes, struct_type: type, *, terminator:bytes=b'') -> List[BaseStruct]:
    """
    Helper function to load an array of structs, possibly with a terminator
    """
    arr = []
    for item_offset in range(0, len(data) - len(terminator), struct_type.raw_data_length):
        item_data = data[item_offset : item_offset + struct_type.raw_data_length]

        if terminator and item_data.startswith(terminator):
            break

        arr.append(struct_type(item_data))

    return arr


def save_struct_array(elements: List[BaseStruct], *, terminator:bytes=b'') -> bytes:
    """
    Helper function to save an array of structs, possibly with a terminator
    """
    return b''.join([bytes(e) for e in elements] + [terminator])

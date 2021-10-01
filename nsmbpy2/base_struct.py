import struct
from typing import Any, Callable, Dict, Generic, List, Literal, TypeVar

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

    def transform(self, name: str, *values) -> 'StructField':
        raise ValueError(f'unsupported field transformation: "{name}({str(values)[1:-1]})"')


# Names for field types (not the actual class names -- rather, names
# that the json api definitions can reference)
FIELD_TYPES_BY_NAME = {}


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

FIELD_TYPES_BY_NAME['bytestring'] = BytestringField


class NumericField(StructField[FT]):
    """
    StructField subclass that deals with numeric types loaded by struct.unpack().
    """
    offset: int

    # Must be defined in subclasses
    endianness: Literal['<', '>']
    format_char: str

    def __init__(self, offset):
        self.offset = offset

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


class IntegralNumericField(NumericField[int]):
    """
    NumericField subclass that deals with integral types.
    This adds various transformations, both with the transform() method
    and as a fluent interface.
    """
    def transform(self, name: str, *values) -> StructField:
        if name == '&':
            return NumericFieldMask(self, *values)
        elif name == '<<':
            return NumericFieldLshift(self, *values)
        elif name == '>>':
            return NumericFieldRshift(self, *values)
        elif name == 'bool':
            return NumericFieldBool(self, *values)
        return super().transform(name, *values)

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


# Create subclasses of NumericField implementing all interesting struct
# format-string characters
for endian_value, endian_name in [('<', 'le'), ('>', 'be')]:
    for format_name, format_char, format_superclass in [
            ('u8', 'B', IntegralNumericField),
            ('s8', 'b', IntegralNumericField),
            ('u16', 'H', IntegralNumericField),
            ('s16', 'h', IntegralNumericField),
            ('u32', 'I', IntegralNumericField),
            ('s32', 'i', IntegralNumericField),
            ('u64', 'Q', IntegralNumericField),
            ('s64', 'q', IntegralNumericField),
            ('f32', 'f', NumericField),
            ('f64', 'd', NumericField)]:
        # Pick class name (lowercase)
        name = f'{endian_name}_{format_name}'
        # Create class (uppercase name)
        cls = type(name.upper(), (format_superclass,), {'endianness': endian_value, 'format_char': format_char})
        # Assign to FIELD_TYPES_BY_NAME (lowercase name)
        FIELD_TYPES_BY_NAME[name] = cls
        # Assign to module namespace (uppercase name)
        exec(f'{name.upper()} = cls')


class NumericFieldMask(IntegralNumericField):
    """
    Wrapper field type for masking the value of an IntegralNumericField.
    """
    parent: IntegralNumericField
    bitmask: int

    def __init__(self, parent, bitmask):
        self.parent = parent
        self.bitmask = int(bitmask, 0)

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
        self.amount = int(amount, 0)

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
        self.amount = int(amount, 0)

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
            raise AttributeError

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

        try:
            self.set(key, value)
        except ValueError:
            raise AttributeError

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


def create_basestruct_subclass(name: str, raw_data_length: int, fields: dict) -> type:
    """
    Dynamically create a new subclass of BaseStruct
    """
    return type(
        name,
        (BaseStruct,),
        {
            'raw_data_length': raw_data_length,
            'fields': fields,
        },
    )

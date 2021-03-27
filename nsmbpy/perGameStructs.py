
import enum
import struct

from . import VariesPerGame
from . import _common


class ConcreteStructField:
    """
    A class representing a specific field (bit pattern) in a struct.
    Despite the "concrete" in the name, this is an abstract class that
    needs to be subclassed to implement getValueFromData() and
    setValueInData().
    """
    def load(self, game, data):
        """
        Given a game context and the data for the full struct, retrieve
        this field's value.
        """
        raise NotImplementedError

    def save(self, game, data, value):
        """
        Given a game context, struct data (bytearray), and a new value,
        insert the value into the struct.
        """
        raise NotImplementedError


class ConcreteBytestring(ConcreteStructField):
    """
    ConcreteStructField subclass that just returns raw bytestrings.
    """
    def __init__(self, offset, length):
        super().__init__()
        self.offset = offset
        self.length = length

    def load(self, game, data):
        return data[self.offset : self.offset + self.length]

    def save(self, game, data, value):
        data[self.offset : self.offset + self.length] = value


class ConcreteNumericField(ConcreteStructField):
    """
    ConcreteStructField subclass that deals with numeric types.
    Provides a fluent interface that lets you declare a sequence of
    transformations (masks, shifts, and casts) to perform on the raw
    values.
    """
    def __init__(self, offset, endianness=None):
        """
        If endianness is not specified, it defaults to that of the game
        context, when loading/saving.
        """
        self.transformations = []
        self.offset = offset
        self.endianness = endianness


    def __init_subclass__(cls, *, format_char, **kwargs):
        """
        Get the struct format string character argument from the class
        definition, and apply it.
        """
        super().__init_subclass__(**kwargs)
        cls.format_char = format_char

        # Find an overall bitmask for the field (e.g. U32 -> 0xFF)
        numBits = struct.calcsize(format_char) * 8
        cls.overall_bitmask = (1 << numBits) - 1


    class Transformation:
        """
        Represents a transformation that can be applied to a value,
        such as a shift or an "&".
        """
        def transform(self, game, value):
            """
            Apply the transformation to the value.
            """
            raise NotImplementedError

        def untransform(self, game, value):
            """
            Apply the reverse transformation to the value, so it can be
            saved to the struct.
            """
            raise NotImplementedError

        def unbitmask(self, game, value):
            """
            Apply a reverse transformation to a bitmask value, so the
            saving machinery can determine the total set of bits that
            the concrete numeric field spans.

            Often this will be identical to untransform(), but not
            necessarily always. In particular, while transform() and
            untransform() may convert the value to/from some
            non-integral type (e.g. bool, enum), unbitmask() will always
            be passed an integer.
            """
            raise NotImplementedError


    def format_string(self, game):
        """
        Get the format string with respect to the specified game
        """
        if self.endianness is None:
            return game.endianness() + self.format_char
        else:
            return self.endianness + self.format_char


    def get_bitmask(self, game):
        """
        Get the bitmask pattern with respect to the specified game
        """
        bitmask = -1
        for t in reversed(self.transformations):
            bitmask = t.unbitmask(game, bitmask)

        if bitmask == -1:
            return -1
        else:
            return bitmask & self.overall_bitmask


    def load(self, game, data):
        """
        Given a game context and the data for the full struct, retrieve
        this field's value.
        """
        # Get initial value
        value, = struct.unpack_from(self.format_string(game), data, self.offset)

        # Apply all transformations, and return
        for t in self.transformations:
            value = t.transform(game, value)
        return value


    def save(self, game, data, value):
        """
        Given a game context, struct data (bytearray), and a new value,
        insert the value into the struct.
        """
        format_string = self.format_string(game)
        # Undo all transformations
        for t in reversed(self.transformations):
            value = t.untransform(game, value)

        # If there's an interesting bitmask, make sure to avoid
        # overwriting any data not included in the mask
        bitmask = self.get_bitmask(game)
        if bitmask != -1:
            origValue, = struct.unpack_from(format_string, data, self.offset)
            value = (origValue & ~bitmask) | value

        # Pack into struct
        try:
            struct.pack_into(format_string, data, self.offset, value)
        except struct.error:
            raise ValueError(f'struct.pack_into({format_string!r}, {data!r}, {self.offset!r}, {value!r})')


    class BitmaskTransformation(Transformation):
        """
        A bitmask transformation (value & some_constant).
        """
        def __init__(self, bitmask):
            self.bitmask = bitmask

        def transform(self, game, value):
            return value & self.bitmask

        def untransform(self, game, value):
            return value & self.bitmask

        def unbitmask(self, game, value):
            return value & self.bitmask

    def mask(self, bitmask):
        """
        Apply a bitmask transformation when loading the field.
        This is a fluent interface.
        """
        self.transformations.append(self.BitmaskTransformation(bitmask))
        return self


    class LeftShiftTransformation(Transformation):
        """
        A left-shift transformation (value << some_constant).
        """
        def __init__(self, amount):
            self.amount = amount

        def transform(self, game, value):
            return value << self.amount

        def untransform(self, game, value):
            return value >> self.amount

        def unbitmask(self, game, value):
            return value >> self.amount

    def lshift(self, amount):
        """
        Apply a left-shift transformation when loading the field.
        This is a fluent interface.
        """
        self.transformations.append(self.LeftShiftTransformation(amount))
        return self


    class RightShiftTransformation(Transformation):
        """
        A right-shift transformation (value >> some_constant).
        """
        def __init__(self, amount):
            self.amount = amount

        def transform(self, game, value):
            return value >> self.amount

        def untransform(self, game, value):
            return value << self.amount

        def unbitmask(self, game, value):
            return value << self.amount

    def rshift(self, amount):
        """
        Apply a right-shift transformation when loading the field.
        This is a fluent interface.
        """
        self.transformations.append(self.RightShiftTransformation(amount))
        return self


    class EnumTransformation(Transformation):
        """
        A transformation that converts a value into a member of some
        enum.
        The enum should be a subclass of StructFieldEnum, or at least
        implement the same load/save interface.
        """
        def __init__(self, enum_class):
            self.enum_class = enum_class

        def transform(self, game, value):
            return self.enum_class.load(game, value)

        @staticmethod
        def untransform(game, value):
            return value.save(game)

        @staticmethod
        def unbitmask(game, value):
            # value will be an integer type, so it's best to just return
            # the same value
            return value

    def enum(self, enum_class):
        """
        Apply an enum transformation when loading the field.
        This is a fluent interface.
        """
        self.transformations.append(self.EnumTransformation(enum_class))
        return self


    class BoolTransformation(Transformation):
        """
        A transformation that casts a value to a bool (representing the
        values 0 and 1).
        """
        @staticmethod
        def transform(game, value):
            return bool(value)

        @staticmethod
        def untransform(game, value):
            return 1 if value else 0

        @staticmethod
        def unbitmask(game, value):
            # value is guaranteed to be an int, so we should do this
            return value & 1

    def bool(self):
        """
        Apply a bool transformation when loading the field.
        This is a fluent interface.
        """
        self.transformations.append(self.BoolTransformation())
        return self


    def mask_bool(self, mask):
        """
        mask should equal 1 << x for some x.
        This function is then a shortcut for self.rshift(x).mask(1).bool().
        """
        assert bin(mask).count('1') == 1
        num_trailing_zeros = len(bin(mask)) - len(bin(mask).rstrip('0'))
        return self.rshift(num_trailing_zeros).mask(1).bool()


# Create subclasses of ConcreteNumericField implementing all interesting
# struct format string characters
class U8(ConcreteNumericField, format_char='B'): pass
class S8(ConcreteNumericField, format_char='b'): pass
class U16(ConcreteNumericField, format_char='H'): pass
class S16(ConcreteNumericField, format_char='h'): pass
class U32(ConcreteNumericField, format_char='I'): pass
class S32(ConcreteNumericField, format_char='i'): pass
class U64(ConcreteNumericField, format_char='Q'): pass
class S64(ConcreteNumericField, format_char='q'): pass
class F32(ConcreteNumericField, format_char='f'): pass


class StructFieldEnum(enum.Enum):
    """
    Enum subclass that provides methods for converting values to/from
    enum members, in the contexts of different games that may represent
    each member with different values.

    Each enum member should be an instance of VariesPerGame, which
    specifies, for each game where the member has a value
    representation, what that representation actually is.
    """
    @classmethod
    def load(cls, game, value):
        """
        Given the value "value" in the context of some game, return the
        matching enum member.
        """
        # Find the member that matches the value
        for member in cls:
            member_value = member.value.get(game)
            if member_value is not None and member_value == value:
                return member

        raise ValueError(f'{cls}: No known enum member for value {value} in {game}')

    def save(self, game):
        """
        Get the value that represents this enum member in the specified
        game context.
        """
        # Just get the value from the VariesPerGame instance.
        # Raise an error if it's None.

        raw_value = self.value.get(game)
        if raw_value is None:
            raise ValueError(f'{self.__class__.__name__}: No known value for {value} in {game}')
        return raw_value


class PerGameStructFieldMeta(type):
    """
    Metaclass to achieve a "PerGameStructField / x" syntactic sugar for
    "PerGameStructField(x)"
    """
    def __truediv__(self, other):
        return self(other)


class PerGameStructField(metaclass=PerGameStructFieldMeta):
    """
    A class used in PerGameStruct type annotations to denote class
    attributes that represent actual struct members.
    """
    def __init__(self, formats):
        if not isinstance(formats, VariesPerGame):
            formats = VariesPerGame(formats)

        self.formats = formats


    def get_format(self, game):
        """
        Get the ConcreteStructField instance for this field, with
        respect to the specified game.
        """
        return self.formats.get(game)


class PerGameStruct:
    """
    Generic class for any struct that is present in multiple games but
    may have different layouts in different games.
    """

    # Both of the below can be instances of VariesPerGame
    length: int
    block_terminator: bytes = b''

    def __init__(self, **kwargs):
        # Set all field values
        for name in self.fields():

            # Pick a value for this field
            if name in kwargs:
                # A value was passed as a constructor keyword argument
                value = kwargs.pop(name)
            elif hasattr(self.__class__, name):
                # A different default value was specified in the class definition
                value = getattr(self.__class__, name)
            else:
                # Automatic default
                value = 0

            setattr(self, name, value)

        # Throw exception if there are any leftover kwargs
        if kwargs:
            raise ValueError(f'Unexpected keyword arguments for {self.__class__.__name__}: {kwargs}')


    @classmethod
    def fields(cls):
        """
        Iterator over all field names
        """
        for name, annotation in cls.__annotations__.items():
            if isinstance(annotation, PerGameStructField):
                yield name


    @classmethod
    def fields_and_formats(cls, game):
        """
        Iterator over all field names and formats
        """
        for name in cls.fields():
            format = cls.__annotations__[name].get_format(game)
            if format is not None:
                yield name, format


    @classmethod
    def get_length(cls, game):
        """
        Get the length value with respect to a specific game
        """
        if isinstance(cls.length, VariesPerGame):
            value = cls.length.get(game)
            if value is None:
                raise ValueError(f'{cls.__name__} has unknown struct length in {game}')
            return value

        return cls.length


    @classmethod
    def get_block_terminator(cls, game):
        """
        Get the block_terminator value with respect to a specific game
        """
        if isinstance(cls.block_terminator, VariesPerGame):
            value = cls.block_terminator.get(game)
            if value is None:
                raise ValueError(f'{cls.__name__} has unknown block terminator in {game}')
            return value

        return cls.block_terminator


    @classmethod
    def load(cls, game, data):
        """
        Create an instanceof this class from data.
        """
        self = cls()

        for field_name, format in cls.fields_and_formats(game):
            setattr(self, field_name, format.load(game, data))

        # # TEMP: debugging
        # print(cls)
        # print(data)
        # print(self.save(game))
        # assert self.save(game) == data

        return self


    def save(self, game):
        """
        Save the object to bytes in the format for the specified game.
        """
        data = bytearray(self.get_length(game))

        for field_name, format in self.fields_and_formats(game):
            format.save(game, data, getattr(self, field_name))

        return bytes(data)


    def copy(self):
        """
        Create a new instance of the same class, with all of the same
        field values as the current one.
        """
        self2 = type(self)()

        for field_name in self.fields():
            value = getattr(self, field_name)

            # Handle some common mutable types, just in case
            if isinstance(value, list):
                value = list(value)
            elif isinstance(value, bytearray):
                value = bytearray(value)

            setattr(self2, field_name, value)

        return self2


    @classmethod
    def load_block(cls, game, data):
        """
        Load a block (array with optional terminator) of this type.
        """
        terminator = cls.get_block_terminator(game)

        if terminator and not data.endswith(terminator):
            raise ValueError(f'Block of {cls.__name__} does not end with {terminator}')
        elif terminator:
            data = data[:-len(terminator)]

        item_len = cls.get_length(game)
        return [cls.load(game, d) for d in _common.divide_block(data, item_len)]


    @classmethod
    def save_block(cls, game, items):
        """
        Save a list of this type as a block (array with optional
        terminator).
        """
        array = b''.join(item.save(game) for item in items)

        terminator = cls.get_block_terminator(game)
        if terminator:
            array += terminator

        return array


    def _non_default_field_values(self):
        """
        Helper function for __str__ and __repr__, which yields
        (name, value) pairs for all fields with non-default values
        """
        for name in self.fields():
            if hasattr(self.__class__, name):
                default = getattr(self.__class__, name)
            else:
                default = 0

            value = getattr(self, name)
            if value != default:
                yield name, value


    def __str__(self):
        # Make a list of "x=y" strings for all non-default field values
        attribs_str_list = []
        for name, value in self._non_default_field_values():
            attribs_str_list.append(f'{name}={getattr(self, name)}')

        # Create list representing final string output
        final_str_list = ['<', self.__class__.__name__]
        if attribs_str_list:
            final_str_list.append(' ')
            final_str_list.append(' '.join(attribs_str_list))
        final_str_list.append('>')

        # Return
        return ''.join(final_str_list)


    def __repr__(self):
        # Make a list of "x=y" strings for all non-default field values
        attribs_str_list = []
        for name, value in self._non_default_field_values():
            attribs_str_list.append(f'{name}={getattr(self, name)}')

        # Create list representing final string output
        final_str_list = [self.__class__.__name__, '(']
        if attribs_str_list:
            final_str_list.append(', '.join(attribs_str_list))
        final_str_list.append(')')

        # Return
        return ''.join(final_str_list)

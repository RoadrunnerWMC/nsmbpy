import codecs
from typing import Any


def short_bytes_repr(data: bytes, max_len=None):
    """
    Like bytes.__repr__(), but will truncate large amounts of data.
    Will also take advantage of octal encoding to make the output more
    compact.
    """
    if max_len is None:
        max_len = 50

    OPENING_QUOTE = "b'"
    CLOSING_QUOTE = "'"
    ELLIPSIS = '...'

    def generate(truncate_optimistically: bool) -> str:
        """
        If truncate_pessimistically, truncate as soon as it's clear that
        adding the next character would make the string too long if an
        ellipsis is needed.
        Otherwise, be optimistic and guess that maybe there'll only be
        a small number of characters remaining and maybe it'll fit.
        Optimistic truncation may return a string that's longer than
        max_len, but pessimistic truncation never will.

        I'll try to explain with examples (also see:
        _test_short_bytes_repr(), included elsewhere in this file)

        Example prefixes of b'\x88\x99\xaa\xbb\xcc':
            XXXXXXXXXXXXXXXXX <- max_len
            b''
            b'\x88'
            b'\x88\x99'
            b'\x88\x99\xaa'
            b'\x88\x99\xaa\xbb'
            b'\x88\x99\xaa\xbb\xcc'

        Pessimistic truncation:
            XXXXXXXXXXXXXXXXX
            b''
            b'\x88'
            b'\x88\x99'
            b'\x88\x99'...    <- truncates here because it wouldn't be
            b'\x88\x99'...       able to fit the "..." anymore if it
            b'\x88\x99'...       kept going

        Optimistic truncation:
            XXXXXXXXXXXXXXXXX
            b''
            b'\x88'               doesn't truncate here because maybe
            b'\x88\x99'           this is the last character or there's
            b'\x88\x99\xaa'    <- a \0 next or something
            b'\x88\x99\xaa'... <- truncated too late, now the string is
            b'\x88\x99\xaa'...    too long

        The actual ideal output for each case would be this:
            XXXXXXXXXXXXXXXXX
            b''
            b'\x88'
            b'\x88\x99'
            b'\x88\x99\xaa'
            b'\x88\x99'...
            b'\x88\x99'...

        That is, try optimistic truncation first, and if it doesn't
        work, start over with pessimistic truncation.
        """
        string_pieces = [OPENING_QUOTE]
        truncated = False

        for i, b in enumerate(data):
            # We have to be careful to avoid shortening e.g. b'\x01\x31' into b'\11',
            # so we don't shorten if the following byte is an ASCII digit
            if b < 8 and (i == len(data) - 1 or data[i + 1] not in range(0x30, 0x3A)):
                this_byte_as_a_string = f'\\{b}'
            else:
                this_byte_as_a_string = repr(b.to_bytes(1, 'big'))[2:-1]

            string_pieces_length = sum(len(part) for part in string_pieces)
            length_of_proposed_string = string_pieces_length + len(this_byte_as_a_string) + len(CLOSING_QUOTE)
            length_of_proposed_truncated_string = length_of_proposed_string + len(ELLIPSIS)

            if (not truncate_optimistically) and length_of_proposed_truncated_string > max_len:
                truncated = True
                break
            elif length_of_proposed_string > max_len:
                truncated = True
                break
            else:
                string_pieces.append(this_byte_as_a_string)

        string_pieces.append(CLOSING_QUOTE)
        if truncated:
            string_pieces.append(ELLIPSIS)

        return ''.join(string_pieces)

    optimistically_truncated_string = generate(True)

    if len(optimistically_truncated_string) <= max_len:
        return optimistically_truncated_string
    else:
        return generate(False)


def _test_short_bytes_repr():
    """
    Test function for short_bytes_repr(), for debugging.
    See the comments of short_bytes_repr() for more explanation.
    """
    MAX_LEN = 17
    print('X' * MAX_LEN)

    for s in ['', '88', '8899', '8899aa', '8899aabb', '8899aabbcc']:
        print(short_bytes_repr(bytes.fromhex(s), max_len=17))


def decode_null_terminated_string_from(
        data, offset, encoding='latin-1', *, fixed_length=None, **kwargs):
    """
    Load a null-terminated string from data at offset, with the options
    given.
    fixed_length is for if the string occupies a fixed-length field (for
    example, a string at the start of a 0x20-long null-padded buffer).
    """
    # OK, so doing this both (relatively) efficiently and correctly is
    # a bit tricky.

    # A naive implementation would be to just read bytes up until the
    # first null byte, then call bytes.decode() on it.

    # That's very very wrong, though, as it fails for UTF-16 text with
    # ascii characters.

    # A better implementation would be to search the bytes for the first
    # N consecutive nulls, where N is the number of bytes per character.
    # (A previous version of this function worked that way.)

    # That's better and works in most practical cases, but it doesn't
    # take alignment into account (consider the sequence [U+1100 U+0011]
    # in UCS-2), and conceptually doesn't work at all on variable-width
    # encodings.

    # (Side note, UTF-8 is designed such that scanning until the first
    # null byte does actually work correctly, but that may not be true
    # of all variable-width encodings in general.)

    # The most correct solution, then, is to decode one character at a
    # time until you reach U+00. So that's what we do.

    # Also, since codecs.iterdecode() requires an iterable of bytes, and
    # we don't know how long the string is going to be beforehand, we
    # use a memoryview to avoid any potentially costly memory copies.

    with memoryview(data) as m:
        if fixed_length is None:
            slice = m[offset:]
        else:
            slice = m[offset : offset+fixed_length]

        chars = []

        for chunk in codecs.iterdecode((bytes([b]) for b in slice), encoding, **kwargs):
            for char in chunk:
                if char == '\0':
                    return ''.join(chars)
                else:
                    chars.append(char)

        return ''.join(chars)


def handle_normal_setattr_stuff(self, super_, key: str, value: Any) -> bool:
    """
    Helper function for __setattr__ methods to check if the key is already
    an attribute of the object, and if so, assign it normally.

    "super_" is the return value of super() in __setattr__'s scope.

    Returns True if it did that, or False if the key wasn't found and
    should be handled with class-specific fallback mechanisms instead.
    """
    if key in self.__dict__:
        super_.__setattr__(key, value)
        return True

    # This allows @properties to work correctly
    # Yes, it looks a bit gross
    elif hasattr(self.__class__, key) and hasattr(getattr(self.__class__, key), '__set__'):
        getattr(self.__class__, key).__set__(self, value)
        return True

    return False

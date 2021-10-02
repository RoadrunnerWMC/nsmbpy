def short_bytes_repr(data: bytes, max_len=None):
    """
    Like bytes.__repr__(), but will truncate large amounts of data.
    Will also take advantage of octal encoding to make the output more
    compact.
    """
    if max_len is None:
        max_len = 50

    r = ["b'"]
    truncated = False
    for i, b in enumerate(data):
        # We have to be careful to avoid shortening e.g. b'\x01\x31' into b'\11',
        # so we don't shorten if the following byte is an ASCII digit
        if b < 8 and (i == len(data) - 1 or data[i + 1] not in range(0x30, 0x3A)):
            r.append(f'\\{b}')
        else:
            r.append(repr(b.to_bytes(1, 'big'))[2:-1])

        if sum(len(part) for part in r) + 1 > max_len:
            truncated = True
            break

    r.append("'")

    final = ''.join(r)
    if truncated:
        return final + '...'
    else:
        return final


def load_null_terminated_string_from(
        data, offset, charWidth=1, encoding='latin-1'):
    """
    Load a null-terminated string from data at offset, with the options
    given.
    This is copypasted from ndspy.
    """
    end = data.find(b'\0' * charWidth, offset)
    return data[offset:end].decode(encoding)
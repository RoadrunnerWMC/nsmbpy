def divide_block(data, item_size):
    """
    Split a block of data into a list of chunks of length item_size.
    """
    items = []
    for i in range((len(data) + item_size - 1) // item_size):
        items.append(data[i*item_size : i*item_size+item_size])
    return items


def merge_block(items):
    """
    Combine a list of data chunks into a large one again.
    If data is already bytes, return it unaltered.
    """
    if isinstance(items, bytes) or isinstance(items, bytearray):
        return items

    return b''.join(items)
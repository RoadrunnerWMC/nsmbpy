# Copyright 2020 RoadrunnerWMC
#
# This file is part of Newer Tileset Animations Tool.
#
# Newer Tileset Animations Tool is free software: you can redistribute
# it and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Newer Tileset Animations Tool is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Newer Tileset Animations Tool.  If not, see
# <https://www.gnu.org/licenses/>.

import struct
from typing import Dict, Union

from . import _common


U8_MAGIC = b'\x55\xAA\x38\x2D'

U8Folder = Dict
PathLike = Union[str, 'pathlib.Path']


def load(data: bytes) -> U8Folder:
    """
    Read a U8 archive and return its contents as a dict.
    """
    if not data.startswith(U8_MAGIC):
        raise ValueError('Incorrect magic for U8 archive')

    # Read header stuff
    root_node_offs, header_size, data_table_offs = struct.unpack_from('>3I', data, 4)
    assert root_node_offs == 0x20

    # "Size" field of the root node tells us the total number of nodes;
    # this is how we calculate the offset of the string table
    root_node_size, = struct.unpack_from('>I', data, root_node_offs + 8)
    string_table_offs = root_node_offs + 12 * root_node_size

    def read_node_at(idx: int) -> (str, Union[bytes, U8Folder], int):
        """
        Read the U8 node at the given index.
        Returns:
        - node's name
        - node's data (bytes if a file, dict if a folder)
        - next node index to read (idx + 1 if a file, idx + [some larger
          number] if a folder)
        """
        offs = root_node_offs + 12 * idx

        type = data[offs]
        name_offs = int.from_bytes(data[offs + 1 : offs + 4], 'big')
        data_offs, size = struct.unpack_from('>II', data, offs + 4)

        name = _common.decode_null_terminated_string_from(data, string_table_offs + name_offs)

        if type == 0:  # File
            file_data = data[data_offs : data_offs + size]
            return name, file_data, idx + 1

        elif type == 1:  # Folder
            contents = {}

            # Keep reading nodes until we reach node number 'size'
            # (1-indexed)
            idx += 1
            while idx < size:
                item_name, item_data, idx = read_node_at(idx)
                contents[item_name] = item_data

            return name, contents, idx

        else:
            raise ValueError(f'Unknown U8 node type: {type}')

    # Read root node and return it
    _, root, _ = read_node_at(0)
    return root


def load_from_file(path: PathLike) -> U8Folder:
    """
    Load a U8 archive file from a path on the filesystem
    """
    with open(path, 'rb') as f:
        return load(f.read())


def save(contents: U8Folder) -> bytes:
    """
    Save a U8 archive file, given its contents as a dictionary
    """
    # Data table offset is aligned to 0x20, as are node data offsets

    # Blank header; actual values will be filled in at the very end
    data = bytearray(b'\0' * 0x20)

    # Tables to populate
    strings_table = bytearray()
    data_table = bytearray()

    # Save each node
    values_to_increase_by_data_table_offs = {}
    def save_node(name: str, contents: U8Folder, my_idx: int, recursion: int) -> int:
        """
        Save a file or folder node, with a given name and contents
        (bytes or dict), to the given index, and with the given
        recursion value (only used if this is a folder)
        """
        nonlocal data, data_table, strings_table

        # Add the name
        name_offs = len(strings_table)
        strings_table += (name + '\0').encode('latin-1')

        # Add dummy data for this node
        node_offs = len(data)
        data += b'\0' * 12

        if isinstance(contents, dict):  # Folder
            idx = my_idx + 1
            # The keys MUST be sorted alphabetically and case-insensitively
            for k in sorted(contents, key=lambda s: s.lower()):
                idx = save_node(k, contents[k], idx, recursion + 1)

            type_ = 1
            data_offs = max(0, recursion)
            size = next_idx = idx

        else:  # File
            while len(data_table) % 0x20:
                data_table.append(0)
            data_offs = len(data_table)
            data_table += contents

            # This is a bit of a hack: the "data offset" node value is
            # absolute, but at this point we're just putting the file
            # data together into a separate bytearray. So we keep track
            # of all of the offsets that we'll need to fix up once we
            # know exactly where the data table is going to go.
            values_to_increase_by_data_table_offs[node_offs + 4] = data_offs

            type_ = 0
            size = len(contents)
            next_idx = my_idx + 1

        # Save node info
        data[node_offs] = type_
        data[node_offs + 1 : node_offs + 4] = name_offs.to_bytes(3, 'big')
        struct.pack_into('>II', data, node_offs + 4, data_offs, size)
        
        return next_idx

    save_node('', contents, 0, -1)

    # Append the strings table, and make a note of the current length
    # (starting at the root node, at 0x20)
    data += strings_table
    header_size = len(data) - 0x20

    # Align to 0x20, make a note of the current length, and append the
    # data table
    while len(data) % 0x20:
        data.append(0)
    data_table_offs = len(data)
    data += data_table

    # Fix up data offsets for all of the file nodes
    for offs, relative_value in values_to_increase_by_data_table_offs.items():
        struct.pack_into('>I', data, offs, data_table_offs + relative_value)

    # Add the final header values and return
    struct.pack_into('>4s3I', data, 0, U8_MAGIC, 0x20, header_size, data_table_offs)
    return bytes(data)


def save_to_file(contents: U8Folder, path: PathLike) -> None:
    """
    Save a U8 archive file to a path on the filesystem
    """
    data = save(contents)
    with open(path, 'wb') as f:
        f.write(data)

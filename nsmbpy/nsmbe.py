# Copyright 2019 RoadrunnerWMC
#
# This file is part of nsmbpy.
#
# nsmbpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# nsmbpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with nsmbpy.  If not, see <https://www.gnu.org/licenses/>.
"""
Support for NSMBe file formats.
"""

import io
import struct

import ndspy.lz10


NML_MAGIC = b'\x15NSMBe4 Exported Level'
NMT_MAGIC = b'\x16NSMBe Exported Tileset'
NMB_MAGIC = b'\x19NSMBe Exported Background'
NMP_MAGIC = b'\x15NSMBe4 Exported Patch'


def _c_sharp_read_7_bit_encoded_int(bio):
    # https://referencesource.microsoft.com/#mscorlib/system/io/binaryreader.cs,582
    acc = shift = 0
    while True:
        if shift >= 5 * 7:
            raise ValueError('C# 7-bit encoded integer is too long!')

        b, = bio.read(1)

        acc |= (b & 0x7F) << shift
        shift += 7

        if b >> 7 == 0:
            break

    if acc & 0x80000000:
        acc = -((~acc) & 0x7FFFFFFF) - 1

    return acc


def _c_sharp_write_7_bit_encoded_int(bio, value):
    # http://referencesource.microsoft.com/#mscorlib/system/io/binarywriter.cs,2daa1d14ff1877bd
    value &= 0xFFFFFFFF
    while value >= 0x80:
        bio.write(bytes([(value & 0x7F) | 0x80]))
        value >>= 7
    bio.write(bytes([value]))


def load_nml(data):
    bio = io.BytesIO(data)

    # Magic
    magic = bio.read(len(NML_MAGIC))
    if magic != NML_MAGIC:
        raise ValueError(f'NML file has incorrect header (found {magic})')

    # Version
    version, = struct.unpack('<H', bio.read(2))
    if version != 1:
        raise ValueError(f'Unsupported NML version: {version}')

    # File IDs
    level_file_id, objects_file_id = struct.unpack('<HH', bio.read(4))

    # File datas
    level_file = bio.read(struct.unpack('<I', bio.read(4))[0])
    objects_file = bio.read(struct.unpack('<I', bio.read(4))[0])

    return version, (level_file_id, objects_file_id, level_file, objects_file)

loadNML = load_nml  # Deprecated alias for backwards-compatibility


def save_nml(version, other_args):
    if version != 1:
        raise ValueError('nsmbpy can only save NML version 1!')

    level_file_id, objects_file_id, level_file, objects_file = other_args

    bio = io.BytesIO()
    bio.write(NML_MAGIC)

    bio.write(struct.pack('<3H', version, level_file_id, objects_file_id))
    bio.write(struct.pack('<I', len(level_file)))
    bio.write(level_file)
    bio.write(struct.pack('<I', len(objects_file)))
    bio.write(objects_file)

    return bio.getvalue()

saveNML = save_nml  # Deprecated alias for backwards-compatibility


def load_nmt(data, *, decompress=True):
    bio = io.BytesIO(data)

    magic = bio.read(len(NMT_MAGIC))
    if magic != NMT_MAGIC:
        raise ValueError(f'NMT file has incorrect header (found {magic})')

    ncl = bio.read(struct.unpack('<I', bio.read(4))[0])
    ncg = bio.read(struct.unpack('<I', bio.read(4))[0])
    pnl = bio.read(struct.unpack('<I', bio.read(4))[0])
    unt = bio.read(struct.unpack('<I', bio.read(4))[0])
    unt_hd = bio.read(struct.unpack('<I', bio.read(4))[0])
    chk_len_data = bio.read(4)
    if chk_len_data:
        chk = bio.read(struct.unpack('<I', chk_len_data)[0])
    else:
        chk = None

    if decompress:
        ncl = ndspy.lz10.decompress(ncl)
        ncg = ndspy.lz10.decompress(ncg)

    return ncl, ncg, pnl, unt, unt_hd, chk

loadNMT = load_nmt  # Deprecated alias for backwards-compatibility


def save_nmt(ncl, ncg, pnl, unt, unt_hd, chk, *, compress=True):
    if compress:
        ncl = ndspy.lz10.compress(ncl)
        ncg = ndspy.lz10.compress(ncg)

    bio = io.BytesIO()
    bio.write(NMT_MAGIC)

    bio.write(struct.pack('<I', len(ncl)))
    bio.write(ncl)
    bio.write(struct.pack('<I', len(ncg)))
    bio.write(ncg)
    bio.write(struct.pack('<I', len(pnl)))
    bio.write(pnl)
    bio.write(struct.pack('<I', len(unt)))
    bio.write(unt)
    bio.write(struct.pack('<I', len(unt_hd)))
    bio.write(unt_hd)
    if chk is not None:
        bio.write(struct.pack('<I', len(chk)))
        bio.write(chk)

    return bio.getvalue()

saveNMT = save_nmt  # Deprecated alias for backwards-compatibility


def load_nmb(data, *, decompress=True):
    bio = io.BytesIO(data)

    magic = bio.read(len(NMB_MAGIC))
    if magic != NMB_MAGIC:
        raise ValueError(f'NMB file has incorrect header (found {magic})')

    ncg = bio.read(struct.unpack('<I', bio.read(4))[0])
    ncl = bio.read(struct.unpack('<I', bio.read(4))[0])
    nsc = bio.read(struct.unpack('<I', bio.read(4))[0])

    if decompress:
        ncl = ndspy.lz10.decompress(ncl)
        ncg = ndspy.lz10.decompress(ncg)
        nsc = ndspy.lz10.decompress(nsc)

    return ncg, ncl, nsc

loadNMB = load_nmb  # Deprecated alias for backwards-compatibility


def save_nmb(ncg, ncl, nsc, *, compress=True):
    if compress:
        ncl = ndspy.lz10.compress(ncl)
        ncg = ndspy.lz10.compress(ncg)
        nsc = ndspy.lz10.compress(nsc)

    bio = io.BytesIO()
    bio.write(NMB_MAGIC)

    bio.write(struct.pack('<I', len(ncg)))
    bio.write(ncg)
    bio.write(struct.pack('<I', len(ncl)))
    bio.write(ncl)
    bio.write(struct.pack('<I', len(nsc)))
    bio.write(nsc)

    return bio.getvalue()

saveNMB = save_nmb  # Deprecated alias for backwards-compatibility


def load_nmp(data):
    bio = io.BytesIO(data)

    magic = bio.read(len(NMP_MAGIC))
    if magic != NMP_MAGIC:
        raise ValueError(f'NMP file has incorrect header (found {magic})')

    files = []

    while True:
        marker, = bio.read(1)
        if marker == 0:
            break
        elif marker != 1:
            raise ValueError(f'Found an unexpected marker byte at 0x{bio.tell()-1:X} while reading NMP: {marker}')

        # NSMBe uses a BinaryWriter without specifying the encoding;
        # according to C# docs, the default encoding is then UTF-8.

        filenameLen = _c_sharp_read_7_bit_encoded_int(bio)
        filename = bio.read(filenameLen).decode('utf-8')
        file_id, = struct.unpack('<H', bio.read(2))
        file = bio.read(struct.unpack('<I', bio.read(4))[0])

        files.append((filename, file_id, file))

    return files

loadNMP = load_nmp  # Deprecated alias for backwards-compatibility


def save_nmp(files):
    bio = io.BytesIO()
    bio.write(NMP_MAGIC)

    for filename, file_id, file in files:
        bio.write(b'\1')

        # NSMBe uses a BinaryWriter without specifying the encoding;
        # according to C# docs, the default encoding is then UTF-8.

        filename_enc = filename.encode('utf-8')
        _c_sharp_write_7_bit_encoded_int(bio, len(filename_enc))
        bio.write(filename_enc)

        bio.write(struct.pack('<H', file_id))

        bio.write(struct.pack('<I', len(file)))
        bio.write(file)

    bio.write(b'\0')

    return bio.getvalue()

saveNMP = save_nmp  # Deprecated alias for backwards-compatibility

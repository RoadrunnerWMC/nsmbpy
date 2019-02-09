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


def _cSharpRead7BitEncodedInt(bio):
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


def _cSharpWrite7BitEncodedInt(bio, value):
    # http://referencesource.microsoft.com/#mscorlib/system/io/binarywriter.cs,2daa1d14ff1877bd
    value &= 0xFFFFFFFF
    while value >= 0x80:
        bio.write(bytes([(value & 0x7F) | 0x80]))
        value >>= 7
    bio.write(bytes([value]))


def loadNML(data):
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
    levelFileID, objectsFileID = struct.unpack('<HH', bio.read(4))

    # File datas
    levelFile = bio.read(struct.unpack('<I', bio.read(4))[0])
    objectsFile = bio.read(struct.unpack('<I', bio.read(4))[0])

    return version, (levelFileID, objectsFileID, levelFile, objectsFile)


def saveNML(version, otherArgs):
    if version != 1:
        raise ValueError('nsmbpy can only save NML version 1!')

    levelFileID, objectsFileID, levelFile, objectsFile = otherArgs

    bio = io.BytesIO()
    bio.write(NML_MAGIC)

    bio.write(struct.pack('<3H', version, levelFileID, objectsFileID))
    bio.write(struct.pack('<I', len(levelFile)))
    bio.write(levelFile)
    bio.write(struct.pack('<I', len(objectsFile)))
    bio.write(objectsFile)

    return bio.getvalue()


def loadNMT(data, *, decompress=True):
    bio = io.BytesIO(data)

    magic = bio.read(len(NMT_MAGIC))
    if magic != NMT_MAGIC:
        raise ValueError(f'NMT file has incorrect header (found {magic})')

    ncl = bio.read(struct.unpack('<I', bio.read(4))[0])
    ncg = bio.read(struct.unpack('<I', bio.read(4))[0])
    pnl = bio.read(struct.unpack('<I', bio.read(4))[0])
    unt = bio.read(struct.unpack('<I', bio.read(4))[0])
    untHd = bio.read(struct.unpack('<I', bio.read(4))[0])
    chkLenData = bio.read(4)
    if chkLenData:
        chk = bio.read(struct.unpack('<I', chkLenData)[0])
    else:
        chk = None

    if decompress:
        ncl = ndspy.lz10.decompress(ncl)
        ncg = ndspy.lz10.decompress(ncg)

    return ncl, ncg, pnl, unt, untHd, chk


def saveNMT(ncl, ncg, pnl, unt, untHd, chk, *, compress=True):
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
    bio.write(struct.pack('<I', len(untHd)))
    bio.write(untHd)
    if chk is not None:
        bio.write(struct.pack('<I', len(chk)))
        bio.write(chk)

    return bio.getvalue()


def loadNMB(data, *, decompress=True):
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


def saveNMB(ncg, ncl, nsc, *, compress=True):
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


def loadNMP(data):
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

        filenameLen = _cSharpRead7BitEncodedInt(bio)
        filename = bio.read(filenameLen).decode('utf-8')
        fileID, = struct.unpack('<H', bio.read(2))
        file = bio.read(struct.unpack('<I', bio.read(4))[0])

        files.append((filename, fileID, file))

    return files


def saveNMP(files):
    bio = io.BytesIO()
    bio.write(NMP_MAGIC)

    for filename, fileID, file in files:
        bio.write(b'\1')

        # NSMBe uses a BinaryWriter without specifying the encoding;
        # according to C# docs, the default encoding is then UTF-8.

        filenameEnc = filename.encode('utf-8')
        _cSharpWrite7BitEncodedInt(bio, len(filenameEnc))
        bio.write(filenameEnc)

        bio.write(struct.pack('<H', fileID))

        bio.write(struct.pack('<I', len(file)))
        bio.write(file)

    bio.write(b'\0')

    return bio.getvalue()

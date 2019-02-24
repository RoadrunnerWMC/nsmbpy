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
Support for tileset files (untHD, unt, etc)
"""

import enum
import struct

from . import Game
from . import _tilesetObjectLayout


class ObjectLayoutStep:
    """
    Represents any layout step in a tileset object
    """

    @classmethod
    def fromData(cls, game, data, startOffset=0):
        raise NotImplementedError('fromData() must be reimplemented in subclasses of ObjectLayoutStep')


    def save(self, game):
        raise NotImplementedError('save() must be reimplemented in subclasses of ObjectLayoutStep')


class NewlineObjectLayoutStep(ObjectLayoutStep):
    """
    Represents a newline layout step in a tileset object
    This behaves similarly to "\n" in strings.
    """

    @classmethod
    def fromData(cls, game, data, startOffset=0):
        v = data[startOffset]
        if v != 0xFE:
            raise ValueError(f'Unexpected byte 0x{v:02X} when parsing newline object layout step')
        return cls()


    def save(self, game):
        return b'\xFE'


class TileObjectLayoutStep(ObjectLayoutStep):
    """
    Represents a layout step that simply places a tile (that possibly
    repeats in the x and/or y directions).
    """

    def __init__(self, tilesetID, tileID, repeatX=False, repeatY=False, contents=0):
        self.tilesetID = tilesetID
        self.tileID = tileID
        self.repeatX = repeatX
        self.repeatY = repeatY
        self.contents = contents

    @classmethod
    def fromData(cls, game, data, startOffset=0):

        a, b, c = data[startOffset : startOffset+3]

        if a & 0x80:
            raise ValueError('TileObjectLayoutStep.fromData(): data starts with MSB set')

        if game is Game.NEW_SUPER_MARIO_BROS:
            # Three bytes:
            #    Repeat: Bitfield (0000 00YX)
            #        Y: Y-repeat
            #        X: X-repeat
            #    Tilenum: two bytes
            v = (c << 8) | b
            if v < 256:
                tilesetID, tileID = 0, v
            elif v < 1024:
                tilesetID, tileID = 1, v - 256
            else:
                tilesetID, tileID = 2, v - 1024
            repeatX = bool(a & 1)
            repeatY = bool(a & 2)
            contents = 0

        else:
            # Three bytes:
            #    Repeat: Bitfield (0000 00YX)
            #        Y: Y-repeat
            #        X: X-repeat
            #    Tilenum: Tile number within this tileset
            #    Other: Bitfield (PPPP PPNN)
            #        P: Parameter (item held)
            #        N: Tileset number (Pa_)
            tilesetID = c & 3
            tileID = b
            repeatX = bool(a & 1)
            repeatY = bool(a & 2)
            contents = c >> 2

        return cls(tilesetID, tileID, repeatX, repeatY, contents)


    def save(self, game):
        a = b = c = 0
        if self.repeatX: a |= 1
        if self.repeatY: a |= 2
        b = self.tileID
        c |= self.parameter << 2
        c |= self.tilesetID & 3

        c |= self.tilesetID & 3
        return bytes([a, b, c])


class SlopeObjectLayoutStep(ObjectLayoutStep):
    """
    Represents a slope layout step.
    """

    class SectionType(enum.Enum):
        MAIN = 'main'
        SUB_FILL_ALL = 'sub_fill_all' # only valid in NSMBDS
        SUB = 'sub'


    class SlopeType(enum.IntEnum):
        """
        These names are relative to going from left to right.

                           /|  |\ 
            FLOOR_UPWARD  /_|  |_\  FLOOR_DOWNWARD
                          | |  | |
                          |_|  |_|

                          |¯|  |¯|
                          | |  | |
        CEILING_DOWNWARD  \¯|  |¯/  CEILING_UPWARD
                           \|  |/
        """
        FLOOR_UPWARD = 0
        FLOOR_DOWNWARD = 1
        CEILING_DOWNWARD = 2
        CEILING_UPWARD = 3


    def __init__(self, sectionType, slopeType):
        self.sectionType = sectionType
        self.slopeType = slopeType


    @classmethod
    def fromData(cls, game, data, startOffset=0):

        v = data[startOffset]

        # Quick sanity checks
        if not (v & 0x80):
            raise ValueError('SlopeObjectLayoutStep.fromData(): data does not start with MSB set')
        elif v == 0xFF:
            raise ValueError('SlopeObjectLayoutStep.fromData(): data starts with 0xFF')
        elif v == 0xFE:
            raise ValueError('SlopeObjectLayoutStep.fromData(): data starts with 0xFE')

        sectionType = cls.SlopeType(v & 3)

        if game == Game.NEW_SUPER_MARIO_BROS:
            # 0x84 = sub-fill-all section type (unused)
            # 0x85 = sub section type
            # Otherwise:
            # 1000 00SS
            # SS = section type

            if v == 0x84:
                return cls(cls.SectionType.SUB_FILL_ALL, None)
            elif v == 0x85:
                return cls(cls.SectionType.SUB, None)

            return cls(cls.SectionType.MAIN, sectionType)

        else:
            # 0b100A0BSS
            # A = this is a sub section
            # B = this is a main section
            # SS = section type
            sub = v & 0x10
            main = v & 4

            if main:
                if sub:
                    # uh
                    raise ValueError('SlopeObjectLayoutStep: main and sub are both set')
                else:
                    return cls(cls.SectionType.MAIN, None)
            else:
                if sub:
                    return cls(cls.SectionType.SUB, sectionType)
                else:
                    # uh
                    raise ValueError('SlopeObjectLayoutStep: neither main nor sub is set')


    def save(self, game):
        if game == Game.NEW_SUPER_MARIO_BROS:

            if self.sectionType is self.SectionType.MAIN:
                return bytes([0x80 | (self.slopeType & 3)])
            elif self.sectionType is self.SectionType.SUB_FILL_ALL:
                return b'\x84'
            elif self.sectionType is self.SectionType.SUB:
                return b'\x85'
            else:
                raise ValueError(f'Unknown (NSMB) slope section type: {self.sectionType}')

        else:

            if self.sectionType is self.SectionType.MAIN:
                return b'\x84'
            elif self.sectionType is self.SectionType.SUB:
                return bytes([0x90 | (self.slopeType & 3)])
            else:
                raise ValueError(f'Unknown (NSMBW+) slope section type: {self.sectionType}')



def loadObjectLayout(game, data, startOffset=0):

    layout = []
    off = startOffset
    while off < len(data):
        b = data[off]

        if b == 0xFF: # End of object
            return layout
        elif b == 0xFE:
            layout.append(NewlineObjectLayoutStep())
        elif b & 0x80:
            layout.append(SlopeObjectLayoutStep.fromData(game, bytes([b])))
        else:
            # Tile (3 bytes)
            layout.append(TileObjectLayoutStep.fromData(game, data[off:off+3]))
            off += 2
        off += 1

    raise ValueError('End of data reached while reading object layout')


def saveObjectLayout(game, layout):
    return b''.join(step.save(game) for step in layout) + b'\xFF'


class Object:
    """
    A tileset object
    """

    layout = []
    width = 1
    height = 1
    randomizeX = False
    randomizeY = False
    randomizeN = 0

    def __init__(self, game, layout=None, width=1, height=1, randomizeX=False, randomizeY=False, randomizeN=0):
        self.layout = [] if layout is None else layout
        self.width = width
        self.height = height
        self.randomizeX = randomizeX
        self.randomizeY = randomizeY
        self.randomizeN = randomizeN


    @classmethod
    def fromLayoutData(cls, game, layoutData, layoutDataStartOffset=0, width=1, height=1, randomizeX=False, randomizeY=False, randomizeN=0):
        """
        Create a new Object with the provided raw layout data and header parameters.
        """
        if game is Game.NEW_SUPER_MARIO_BROS:
            layout = loadObjectLayout(game, layoutData, layoutDataStartOffset)

        else:
            raise NotImplementedError

        return cls(game, layout, width, height, randomizeX, randomizeY, randomizeN)


    @classmethod
    def fromData(cls, game, headerData, layoutData):
        """
        Given the data for an entry in an untHD file, and an entire
        corresponding unt file, create a new Object.
        """

        if game is Game.NEW_SUPER_MARIO_BROS:
            offset, width, height = struct.unpack_from('<HBB', headerData)
            randomizeX = randomizeY = False
            randomizeN = 0

        else:
            raise NotImplementedError

        return cls.fromLayoutData(game, layoutData, offset, width, height, randomizeX, randomizeY, randomizeN)


    def save(self, game, layoutDataOffset=0):
        """
        Save the Object to raw layout and header data.
        """
        if game is Game.NEW_SUPER_MARIO_BROS:
            headerData = struct.pack('<HBB', layoutDataOffset, self.width, self.height)
            layoutData = saveObjectLayout(game, self.layout)

        else:
            raise NotImplementedError

        return headerData, layoutData


    def render(self, game, width, height, *, fullslope=False):
        """
        Render the object as a 2D list (list of lists) containing
        (tilesetID, tileID) pairs.
        Randomization is ignored.
        """
        return _tilesetObjectLayout.renderObject(game, self.layout, width, height, fullslope=fullslope)


    def renderAsImage(self, width, height, tileImageLookup):
        """
        Same as .render(), but returns a PIL.Image.
        tileImageLookup should be a dict:
        {tilesetID: {tileID: tileImage, ...}, ...}
        """
        raise NotImplementedError


    def __str__(self):
        """
        Return a nice-looking string representing this Object.
        """
        return f'<object {self.width}x{self.height}>'


def loadObjects(game, headerData, layoutData):
    """
    Load a list of Objects from header (untHD) and layout (unt) data
    """
    
    objectHeaderSize = {
        Game.NEW_SUPER_MARIO_BROS: 4,
        Game.NEW_SUPER_MARIO_BROS_WII: 4,
        Game.NEW_SUPER_MARIO_BROS_2: 6,
        Game.NEW_SUPER_MARIO_BROS_U: 6,
        Game.NEW_SUPER_LUIGI_U: 6,
        Game.NEW_SUPER_MARIO_BROS_U_DELUXE: 6,
    }.get(game)
    if objectHeaderSize is None:
        raise ValueError(f'Unknown game when loading Object: {game}')

    objects = []
    count = len(headerData) // objectHeaderSize

    for i in range(count):
        entry = headerData[i*objectHeaderSize : (i+1)*objectHeaderSize]
        objects.append(Object.fromData(game, entry, layoutData))

    return objects


def saveObjects(game, objects):
    """
    Save a list of Objects to header (untHD) and layout (unt) data
    """
    headerData = bytearray()
    layoutData = bytearray()

    for obj in objects:
        a, b = obj.save(game, len(layoutData))
        headerData.extend(a)
        layoutData.extend(b)

    return bytes(headerData), bytes(layoutData)

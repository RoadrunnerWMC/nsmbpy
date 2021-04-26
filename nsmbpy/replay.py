# Copyright 2021 RoadrunnerWMC
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
Support for replay files.
"""

import dataclasses
import enum
import struct
import typing


class NSMBWPlayerCharacter(enum.IntEnum):
    """
    Represents the four player characters in NSMBW.
    """
    MARIO = 0
    LUIGI = 1
    BLUE_TOAD = 2
    YELLOW_TOAD = 3


class NSMBWPlayerPowerup(enum.IntEnum):
    """
    Represents the powerups available in NSMBW.
    """
    NONE = 0
    MUSHROOM = 1
    FIRE_FLOWER = 2
    MINI_MUSHROOM = 3
    PROPELLER_SUIT = 4
    PENGUIN_SUIT = 5
    ICE_FLOWER = 6


class WiiRemoteButtonInputs(enum.IntFlag):
    """
    Represents a set of simultaneous Wii remote button inputs.
    """
    HOME       = 0x8000
    MINUS      = 0x1000
    A          = 0x0800
    B          = 0x0400
    ONE        = 0x0200
    TWO        = 0x0100
    PLUS       = 0x0010
    DPAD_LEFT  = 0x0008
    DPAD_RIGHT = 0x0004
    DPAD_UP    = 0x0002
    DPAD_DOWN  = 0x0001


@dataclasses.dataclass
class NSMBWReplayFile:
    """
    Represents a NSMBW replay file (otakara, otehon, title).

    Note:
    - Otakara: Hint Movies (S = Super Skills, U = 1-UPs, G = Secret Exit, C = Star Coin)
    - Otehon: Super Guide
    - Title: Title Screen (attract mode)

    Note 2: for multiplayer replays, each player has a different replay file.
    """

    @dataclasses.dataclass
    class Frame:
        """
        Represents one frame of input
        """
        # Bits related to saving optional values, which are implied by
        # the non-default values of those optional values, are cleared upon load.
        # If you want to force an optional value to be saved despite having
        # its default value, you can set the corresponding bit to achieve that.
        # There are also other flags used, though it's unclear if they do anything.
        flags: int

        unkVal01: int
        inputs: WiiRemoteButtonInputs

        # Below: values that default to a specific in-game value each frame
        # are set to that value; values that default to something from
        # previous frames are set to None.
        optionalVal_10000000_0: int = None
        optionalVal_08000000_0: float = 0.0   # <Ninji> heh
        optionalVal_08000000_1: float = -1.0  # <Ninji> one vec3, three vec2s
        optionalVal_08000000_2: float = 0.0   # <Ninji> okay, they're different parts of the Wiimote input
        optionalVal_04000000_0: float = 1.0   # <Ninji> the first vec3 is "Acc", the first vec2 is "AccVertical", and
        optionalVal_04000000_1: float = 0.0   #         i'm not sure what the other two are pulled from but they're
        optionalVal_02000000_0: float = 0.0   #         almost certainly motion control related as well
        optionalVal_02000000_1: float = 0.0
        optionalVal_01000000_0: float = 0.0
        optionalVal_01000000_1: float = 0.0
        optionalVal_00800000_0: int = 0
        optionalVal_00800000_1: int = 0xffff  # game never reads this, but it takes on various values, most often 0xffff
        rngSeed: int = None


        def __init__(self):
            pass


        def _buildFlagsForOptionalValues(self) -> int:
            """
            Create a flags mask representing the extra data pieces we'd need
            to save in order to include all the optional values we have with non-default values
            """
            flags = 0
            if self.optionalVal_10000000_0 is not None:
                flags |= 0x10000000
            if (self.optionalVal_08000000_0, self.optionalVal_08000000_1, self.optionalVal_08000000_2) != (0.0, -1.0, 0.0):
                flags |= 0x08000000
            if (self.optionalVal_04000000_0, self.optionalVal_04000000_1) != (1.0, 0.0):
                flags |= 0x04000000
            if (self.optionalVal_02000000_0, self.optionalVal_02000000_1) != (0.0, 0.0):
                flags |= 0x02000000
            if (self.optionalVal_01000000_0, self.optionalVal_01000000_1) != (0.0, 0.0):
                flags |= 0x01000000
            if (self.optionalVal_00800000_0, self.optionalVal_00800000_1) != (0, 0xffff):
                flags |= 0x00800000
            if self.rngSeed is not None:
                flags |= 0x00400000
            return flags


        @classmethod
        def load(cls, data: bytes, offset: int) -> ('Frame', int):
            """
            Load a frame from some offset in a bytes object.
            Returns both the Frame instance and the number of bytes read.
            """
            self = cls()
            origOffset = offset

            flags, self.unkVal01, inputs_raw = struct.unpack_from('>3I', data, offset)
            self.inputs = WiiRemoteButtonInputs(inputs_raw)
            offset += 12

            if flags & 0x10000000:
                self.optionalVal_10000000_0, = struct.unpack_from('>I', data, offset)
                offset += 4

            # Never happens in retail replays
            if flags & 0x08000000:
                self.optionalVal_08000000_0, = struct.unpack_from('>f', data, offset + 0)
                self.optionalVal_08000000_1, = struct.unpack_from('>f', data, offset + 4)
                self.optionalVal_08000000_2, = struct.unpack_from('>f', data, offset + 8)
                offset += 12

            # Never happens in retail replays
            if flags & 0x04000000:
                self.optionalVal_04000000_0, = struct.unpack_from('>f', data, offset + 0)
                self.optionalVal_04000000_1, = struct.unpack_from('>f', data, offset + 4)
                offset += 8

            # Never happens in retail replays
            if flags & 0x02000000:
                self.optionalVal_02000000_0, = struct.unpack_from('>f', data, offset + 0)
                self.optionalVal_02000000_1, = struct.unpack_from('>f', data, offset + 4)
                offset += 8

            # Never happens in retail replays
            if flags & 0x01000000:
                self.optionalVal_01000000_0, = struct.unpack_from('>f', data, offset + 0)
                self.optionalVal_01000000_1, = struct.unpack_from('>f', data, offset + 4)
                offset += 8

            if flags & 0x00800000:
                self.optionalVal_00800000_0, = struct.unpack_from('>H', data, offset + 0)
                self.optionalVal_00800000_1, = struct.unpack_from('>H', data, offset + 2)
                offset += 4

            if flags & 0x00400000:
                self.rngSeed, = struct.unpack_from('>I', data, offset)
                offset += 4

            # Clear flags that are implied by the states of the optional values
            self.flags = flags & ~self._buildFlagsForOptionalValues()

            return self, (offset - origOffset)


        def save(self) -> bytes:
            """
            Save the frame back to bytes.
            """
            buf = bytearray()

            flags = self.flags | self._buildFlagsForOptionalValues()
            buf += struct.pack('>3I', flags, self.unkVal01, self.inputs)

            if flags & 0x10000000:
                buf += struct.pack('>I', self.optionalVal_10000000_0)

            if flags & 0x08000000:
                buf += struct.pack('>f', self.optionalVal_08000000_0)
                buf += struct.pack('>f', self.optionalVal_08000000_1)
                buf += struct.pack('>f', self.optionalVal_08000000_2)

            if flags & 0x04000000:
                buf += struct.pack('>f', self.optionalVal_04000000_0)
                buf += struct.pack('>f', self.optionalVal_04000000_1)

            if flags & 0x02000000:
                buf += struct.pack('>f', self.optionalVal_02000000_0)
                buf += struct.pack('>f', self.optionalVal_02000000_1)

            if flags & 0x01000000:
                buf += struct.pack('>f', self.optionalVal_01000000_0)
                buf += struct.pack('>f', self.optionalVal_01000000_1)

            if flags & 0x00800000:
                buf += struct.pack('>H', self.optionalVal_00800000_0)
                buf += struct.pack('>H', self.optionalVal_00800000_1)

            if flags & 0x00400000:
                buf += struct.pack('>I', self.rngSeed)

            return bytes(buf)

    # Note: just because a value below is marked as "always 0" doesn't mean
    # it's padding! The game really does read every single one of these
    # into different individual class members (though most of them then go unused)
    world: int = 1        # range 1-256
    level: int = 1        # range 1-256
    area: int = 1         # range 1-4
    entrance_id: int = 0  # range 0-255
    rng_seed: int = 0     # range 0-0xFFFFFFFF
    unk08: int = 0        # range 0-0xFFFFFFFF / used values: {0}
    unk0C: int = 0        # range 0-0xFFFFFFFF / used values: {0}
    character: NSMBWPlayerCharacter = NSMBWPlayerCharacter.MARIO
    powerup: NSMBWPlayerPowerup = NSMBWPlayerPowerup.NONE
    is_invincible: bool = False
    unk1C: int = 0  # range 0-0xFFFFFFFF / used values: {37114, 37282, 37384, 37395, 37444, 37488, 37505, 37544, 37549, 37593, 37603, 37613, 37622}
    unk20: int = 0  # range 0-255        / used values: {76}
    red_switch_pressed: bool = False
    unk22: int = 0  # range 0-255        / used values: {0, 8, 49, 50, 51, 53, 58, 64, 67, 114, 255}
    unk23: int = 0  # range 0-255        / used values: {0, 1, 2, 3, 8, 24, 32, 49, 52, 54, 64, 176, 240}
    unk24: int = 0  # range 0-0xFFFFFFFF / used values: {0, 5, 0x3000, 0x20000000, 0x32383800, 0x34303000, 0x37343400, 0x8020788c, 0x80211bb8, 0x80212820, 0x8044feb0, 0x80450230, 0x80453000, 0x80763000, 0x80765754, 0xe0010302}
    unk28: int = 0  # range 0-0xFFFFFFFF / used values: {0x803e05e8, 0x815e7214, 0x815e7218}
    unk2C: int = 0  # range 0-0xFFFFFFFF / used values: {0, 0x80d1c168}
    unk30: int = 0  # range 0-0xFFFFFFFF / used values: {0x80503520, 0x815f3130, 0x815f3d88, 0x815f5108}
    unk34: int = 0  # range 0-0xFFFFFFFF / used values: {0}
    unk38: int = 0  # range 0-0xFFFFFFFF / used values: {0x815e7214, 0x815e7218}
    unk3C: int = 0  # range 0-0xFFFFFFFF / used values: {0x805025d8, 0x80502cd8, 0x805030d8, 0x805035f8, 0x80504118, 0x80504198, 0x80504398, 0x80504498, 0x80504518, 0x805046d8, 0x80504a18, 0x80504af8, 0x80504b18, 0x80504e38}

    frames: typing.List[Frame] = dataclasses.field(default_factory=list)


    @classmethod
    def load(cls, data: bytes) -> 'NSMBWReplay':
        """
        Load a NSMBW replay file from data.
        """
        self = cls()

        # Read header
        (world_raw, level_raw, area_raw, self.entrance_id, self.rng_seed, self.unk08, self.unk0C,
            character_raw, powerup_raw, is_invincible_raw, self.unk1C,
            self.unk20, red_switch_pressed_raw, self.unk22, self.unk23, self.unk24, self.unk28, self.unk2C,
            self.unk30, self.unk34, self.unk38, self.unk3C,
        ) = struct.unpack_from('>4B7I4B7I', data)

        self.world = world_raw + 1
        self.level = level_raw + 1
        self.area = area_raw + 1

        # (This is correct behavior for OOB character and powerup values)
        if character_raw > max(NSMBWPlayerCharacter): character_raw = 0
        if powerup_raw > max(NSMBWPlayerPowerup): powerup_raw = 0
        self.character = NSMBWPlayerCharacter(character_raw)
        self.powerup = NSMBWPlayerPowerup(powerup_raw)
        self.is_invincible = bool(is_invincible_raw)

        self.red_switch_pressed = bool(red_switch_pressed_raw)

        # Read frames
        offs = 0x40
        while offs < len(data):
            # Check for terminator
            if data[offs : offs+4] == b'\xFF\xFF\xFF\xFF':
                break

            # Read frame
            frame, framelen = cls.Frame.load(data, offs)
            self.frames.append(frame)
            offs += framelen

        return self


    def save(self) -> bytes:
        """
        Save the file back to bytes.
        """
        buf = bytearray(0x40)

        # Save header
        struct.pack_into('>4B7I4B7I', buf, 0,
            self.world - 1, self.level - 1, self.area - 1, self.entrance_id, self.rng_seed, self.unk08, self.unk0C,
            self.character, self.powerup, self.is_invincible, self.unk1C,
            self.unk20, self.red_switch_pressed, self.unk22, self.unk23, self.unk24, self.unk28, self.unk2C,
            self.unk30, self.unk34, self.unk38, self.unk3C,
        )

        # Save frames
        for frame in self.frames:
            buf += frame.save()
        buf += b'\xFF\xFF\xFF\xFF'

        return bytes(buf)


class NSMBWReplay:
    """
    Represents a single replay (which can include more than one file)
    """
    files: typing.List[NSMBWReplayFile]

    def __init__(self, files=None):
        if files is None: files = []
        self.files = files

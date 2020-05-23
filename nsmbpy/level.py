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
Support for level files (both course and bgdat).
"""

import functools
import struct
import typing

from . import Game
from . import VariesPerGame as Varies
from .perGameStructs import (ConcreteBytestring,
    U8, S8, U16, S16, U32, S32, U64, S64, F32,
    StructFieldEnum, PerGameStructField, PerGameStruct)
from . import _common
from . import nsmbe
from . import u8

########################################################################
################################ Shared ################################
########################################################################


def only_in(games):
    """
    Decorator factory that can be applied to functions with an initial
    "game" argument. Raises an exception if the game isn't in the list
    of allowed games.
    """
    def decorator(func):
        """
        The actual decorator function Python sees
        """
        @functools.wraps(func)
        def wrapper(game, *args, **kwargs):
            """
            Wraps the actual function
            """
            if game not in games:
                raise ValueError('This property is only available in the following games: ' + ', '.join(str(g) for g in games))

            return func(game, *args, **kwargs)

        return wrapper

    return decorator


########################################################################
############################ Objects (bgdat) ###########################
########################################################################


class MixinPositionAndSize:
    """
    Mixin that adds position, size, and dimensions properties to a class
    with x, y, width and height attributes
    """

    @property
    def position(self):
        return (self.x, self.y)
    @position.setter
    def position(self, value):
        (self.x, self.y) = value

    @property
    def size(self):
        return (self.width, self.height)
    @size.setter
    def size(self, value):
        (self.width, self.height) = value

    @property
    def dimensions(self):
        return (self.x, self.y, self.width, self.height)
    @dimensions.setter
    def dimensions(self, value):
        (self.x, self.y, self.width, self.height) = value


class LevelObject(PerGameStruct, MixinPositionAndSize):
    """
    A class representing an object in a bgdat file.
    """
    length = Varies(nsmb=10, nsmbw=10, nsmb2=16, like_nsmbu=16)
    block_terminator = b'\xFF\xFF'

    tileset_id: PerGameStructField / U16(0x00).rshift(12)
    type:      PerGameStructField / U16(0x00).mask(0xFFF)
    x:         PerGameStructField / S16(0x02)
    y:         PerGameStructField / S16(0x04)
    width:     PerGameStructField / S16(0x06)
    height:    PerGameStructField / S16(0x08)
    contents:  PerGameStructField / Varies(like_nsmbu=U8(0x0A))


def load_bgdat(game, data):
    """
    Load a bgdat file in the format for the specified game.
    """
    return LevelObject.load_block(game, data)


def save_bgdat(game, objects):
    """
    Save a bgdat file in the format for the specified game.
    """
    return LevelObject.save_block(game, objects)


########################################################################
########################### Blocks (overall) ###########################
########################################################################


def load_course_blocks(data, num_blocks, endianness):
    """
    Split a course.bin file up into its blocks, using the given
    endianness and number of blocks.
    Return the metadata (data between the header and the first block)
    and the list of blocks.
    """

    starts_and_sizes = []
    for i in range(num_blocks):
        starts_and_sizes.append(struct.unpack_from(endianness + 'II', data, i * 8))

    blocks = [data[start : start+size] for start, size in starts_and_sizes]

    metadata = b''
    if num_blocks > 0:
        first_block_start = starts_and_sizes[0][0]
        if first_block_start != num_blocks * 8:
            metadata = data[num_blocks * 8 : first_block_start]

    return blocks, metadata


def save_course_blocks(blocks, metadata, endianness):
    """
    Given a list of block datas and some metadata, put a course.bin
    together using the specified endianness.
    """

    data = bytearray(len(blocks) * 8)

    data.extend(metadata)
    while len(data) % 4: data.append(0)

    for i, b in enumerate(blocks):
        struct.pack_into(endianness + 'II', data, i * 8, len(data), len(b))
        data.extend(b)
        while len(data) % 4: data.append(0)

    return bytes(data)


########################################################################
######################### Level item superclass ########################
########################################################################


class LevelItem(PerGameStruct):
    """
    Generic superclass for all types of items in a level (sprites,
    zones, etc)
    """

    @classmethod
    def get_individual_loader_and_saver(cls, field_name):
        """
        Return block loader and saver functions that treat the block as
        an instance of this level item
        """
        def loader(game, course, data):
            setattr(course, field_name, cls.load(game, data))
        def saver(game, course):
            return getattr(course, field_name).save(game)
        return loader, saver

    @classmethod
    def get_block_loader_and_saver(cls, field_name):
        """
        Return block loader and saver functions that treat the block as
        a block of this level item
        """
        def loader(game, course, data):
            setattr(course, field_name, cls.load_block(game, data))
        def saver(game, course):
            return cls.save_block(game, getattr(course, field_name))
        return loader, saver


########################################################################
########################### Individual blocks ##########################
########################################################################


@only_in(Game.all - set([Game.NEW_SUPER_MARIO_BROS]))
def load_tileset_names_block(game, data):
    """
    Load tileset names from the given block data.
    """
    tileset_0 = data[0x00:0x20].rstrip(b'\0').decode('latin-1')
    tileset_1 = data[0x20:0x40].rstrip(b'\0').decode('latin-1')
    tileset_2 = data[0x40:0x60].rstrip(b'\0').decode('latin-1')
    tileset_3 = data[0x60:0x80].rstrip(b'\0').decode('latin-1')
    return [tileset_0, tileset_1, tileset_2, tileset_3]


@only_in(Game.all - set([Game.NEW_SUPER_MARIO_BROS]))
def save_tileset_names_block(game, tileset_names):
    """
    Save tileset names back to block data.
    """
    if len(tileset_names) != 4:
        raise ValueError(f'Expected 4 tileset names when saving tileset names block, got {len(tileset_names)}')

    return b''.join([tn.encode('latin-1').ljust(32, b'\0') for tn in tileset_names])


class LevelOptions(LevelItem):
    """
    A class representing the "options" block in a course file.
    """
    length = Varies(nsmb=32, nsmbw=20, nsmb2=24, like_nsmbu=24)

    class MegaMarioGroundpoundBehavior(StructFieldEnum):
        SPAWN_GOOMBAS_AND_COINS = Varies(nsmb=0)
        SPAWN_COINS             = Varies(nsmb=1)
        SPAWN_NOTHING           = Varies(nsmb=2)

    class NSMBWLevelType(StructFieldEnum):
        NORMAL            = Varies(nsmbw=0)
        YELLOW_TOAD_HOUSE = Varies(nsmbw=1)
        RED_TOAD_HOUSE    = Varies(nsmbw=2)
        GREEN_TOAD_HOUSE  = Varies(nsmbw=3)

    class NSMB2LevelType1(StructFieldEnum):
        NORMAL                   = Varies(nsmb2=0)
        RED_OR_YELLOW_TOAD_HOUSE = Varies(nsmb2=2)
        GREEN_TOAD_HOUSE         = Varies(nsmb2=3)
        RAINBOW                  = Varies(nsmb2=4)
        CREDITS                  = Varies(nsmb2=5)
        CANNON                   = Varies(nsmb2=6)
        FROZEN_TIMER             = Varies(nsmb2=7)

    class NSMB2LevelType2(StructFieldEnum):
        NORMAL        = Varies(nsmb2=0)
        GHOST_HOUSE   = Varies(nsmb2=1)
        REZNOR_BATTLE = Varies(nsmb2=7)


    initial_event_ids:                  PerGameStructField / Varies(nsmb=U16(0x18), nsmbw=U32(0x00), nsmb2=U64(0x00), like_nsmbu=U64(0x00))
    wrap_across_edges:                  PerGameStructField / Varies(nsmb=U16(0x02).mask_bool(0x20),
                                                                                    nsmbw=U16(0x08).mask_bool(1),
                                                                                                                      like_nsmbu=U16(0x08).mask_bool(1))
    unk_flag_8:                         PerGameStructField / Varies(nsmb=U16(0x02).mask_bool(8),
                                                                                    nsmbw=U16(0x08).mask_bool(8),
                                                                                                     nsmb2=U16(0x08).mask_bool(8),
                                                                                                                      like_nsmbu=U16(0x08).mask_bool(8))
    start_as_mini_mario:                PerGameStructField / Varies(nsmb=U16(0x02).mask_bool(1))
    force_mini_mario_physics:           PerGameStructField / Varies(nsmb=U16(0x02).mask_bool(2))
    initial_time_limit:                 PerGameStructField / Varies(nsmb=S16(0x04), nsmbw=U16(0x0A), nsmb2=U16(0x0A), like_nsmbu=U16(0x0A))
    coin_rush_time_limit:               PerGameStructField / Varies(                                 nsmb2=U16(0x14))
    checkpoint_time_limit_1:            PerGameStructField / Varies(                                                  like_nsmbu=U16(0x14))
    checkpoint_time_limit_2:            PerGameStructField / Varies(                                                  like_nsmbu=U16(0x16))
    is_credits:                         PerGameStructField / Varies(                nsmbw=U8(0x0C).mask_bool(1))
    unk_0D:                             PerGameStructField / Varies(                nsmbw=U8(0x0D),  nsmb2=U8(0x0D),  like_nsmbu=U8(0x0D))
    unk_0E:                             PerGameStructField / Varies(                nsmbw=U8(0x0E),  nsmb2=U8(0x0E),  like_nsmbu=U8(0x0E))
    unk_0F:                             PerGameStructField / Varies(                nsmbw=U8(0x0F),  nsmb2=U8(0x0F),  like_nsmbu=U8(0x0F))
    initial_entrance_id:                PerGameStructField / Varies(nsmb=U8(0x00),  nsmbw=U8(0x10),  nsmb2=U8(0x10),  like_nsmbu=U8(0x10))
    coin_battle_boost_rush_entrance_id: PerGameStructField / Varies(                                                  like_nsmbu=U8(0x13))
    checkpoint_entrance_id:             PerGameStructField / Varies(nsmb=U8(0x01))
    is_ambush:                          PerGameStructField / Varies(                nsmbw=U8(0x11).mask_bool(1))
    level_type_1:                       PerGameStructField / Varies(                nsmbw=U8(0x12).enum(NSMBWLevelType),
                                                                                                     nsmb2=U8(0x12).enum(NSMB2LevelType1))
    level_type_2:                       PerGameStructField / Varies(                                 nsmb2=U8(0x13).enum(NSMB2LevelType2))

    # NSMB-specific stuff
    background_b_id_1:                  PerGameStructField / Varies(nsmb=S16(0x06))
    background_b_id_2:                  PerGameStructField / Varies(nsmb=S16(0x08))
    background_b_id_3:                  PerGameStructField / Varies(nsmb=S16(0x0A))
    tileset_id_1:                       PerGameStructField / Varies(nsmb=S16(0x0C))
    tileset_id_2:                       PerGameStructField / Varies(nsmb=S16(0x0E))
    tileset_id_3:                       PerGameStructField / Varies(nsmb=S16(0x10))
    background_a_id_1:                  PerGameStructField / Varies(nsmb=S16(0x12))
    background_a_id_2:                  PerGameStructField / Varies(nsmb=S16(0x14))
    background_a_id_3:                  PerGameStructField / Varies(nsmb=S16(0x16))
    sound_group:                        PerGameStructField / Varies(nsmb=U16(0x1A))
    two_d_sprite_properties:            PerGameStructField / Varies(nsmb=U16(0x1C))  # TODO: this is very poorly understood
    mega_mario_groundpound_behavior:    PerGameStructField / Varies(nsmb=U16(0x1E).enum(MegaMarioGroundpoundBehavior))

    nsmb2Unk11:                         PerGameStructField / Varies(nsmb2=U8(0x11))


class LevelZoneBounds(LevelItem):
    """
    A class representing a zone-bounds struct in a course file.
    """
    length = Varies(nsmb=24, nsmbw=24, nsmb2=28, like_nsmbu=28)

    upper:                 PerGameStructField / S32(0x00)
    lower:                 PerGameStructField / S32(0x04)

    upper_2:               PerGameStructField / S32(0x08)
    lower_2:               PerGameStructField / S32(0x0C)
    # NSMBDS/NSMB2: used in place of upper/lower when Mario moves
    #     vertically via something other than jumping (e.g. climbing a
    #     vine)
    # NSMBW: seems unused?
    # NSMBU: ??

    id:                    PerGameStructField / U32(0x10)

    vertical_scroll_limit: PerGameStructField / U32(0x12)
    # NSMBDS/NSMB2: values 0-E set a limit of vertical scrolling (measured in tiles), and F means unlimited
    # NSMBW: 0 means no vertical scrolling, 1+ means unlimited
    # NSMBU: ??


class LevelBackgroundLayer(LevelItem):
    """
    A class representing one layer of a two-layered (bgA/bgB) background
    """
    length = Varies(nsmb=20, nsmbw=24)

    class BackgroundScrollRate(StructFieldEnum):
        RATE_0_0:       0.0      = Varies(         nsmbw=0)
        RATE_0_0_ALT:   0.0      = Varies(         nsmbw=9)
        RATE_0_0625:    0.0625   = Varies(nsmb=6)
        RATE_0_09375:   0.09375  = Varies(nsmb=7)
        RATE_0_125:     0.125    = Varies(nsmb=3,  nsmbw=1)
        RATE_0_203125:  0.203125 = Varies(nsmb=8,  nsmbw=1)
        RATE_0_25:      0.25     = Varies(nsmb=2,  nsmbw=2)
        RATE_0_375:     0.375    = Varies(         nsmbw=3)
        RATE_0_5:       0.5      = Varies(nsmb=1,  nsmbw=4)
        RATE_0_625:     0.625    = Varies(         nsmbw=5)
        RATE_0_75:      0.75     = Varies(nsmb=5,  nsmbw=6)
        RATE_0_875:     0.875    = Varies(         nsmbw=7)
        RATE_1_0:       1.0      = Varies(nsmb=0,  nsmbw=8)
        RATE_1_0_ALT_1: 1.0      = Varies(nsmb=9)
        RATE_1_0_ALT_2: 1.0      = Varies(nsmb=10)
        RATE_1_0_ALT_3: 1.0      = Varies(nsmb=11)
        RATE_1_0_ALT_4: 1.0      = Varies(nsmb=12)
        RATE_1_2:       1.2      = Varies(nsmb=4,  nsmbw=10)
        RATE_1_5:       1.5      = Varies(         nsmbw=11)
        RATE_2_0:       2.0      = Varies(nsmb=13, nsmbw=12)
        RATE_4_0:       4.0      = Varies(nsmb=14, nsmbw=13)
        RATE_8_0:       8.0      = Varies(nsmb=15)

        @property
        def rate(self):
            """
            Return the actual scroll rate as a float; i.e.
            BackgroundScrollRate.RATE_0_25.rate -> 0.25
            """
            return type(self).__annotations__[self.name]


    class BackgroundZoom(StructFieldEnum):
        ZOOM_100_0: 100.0 = Varies(nsmbw=0)
        ZOOM_125_0: 125.0 = Varies(nsmbw=1)
        ZOOM_150_0: 150.0 = Varies(nsmbw=2)
        ZOOM_200_0: 200.0 = Varies(nsmbw=3)

        @property
        def zoom(self):
            """
            Return the actual zoom level as a float; i.e.
            BackgroundZoom.ZOOM_125_0.zoom -> 125.0
            """
            return type(self).__annotations__[self.name]


    id:              PerGameStructField / Varies(nsmb=U16(0x00), nsmbw=U16(0x00))

    # NSMB stuff
    tilemap_file_id: PerGameStructField / Varies(nsmb=S16(0x02))
    palette_file_id: PerGameStructField / Varies(nsmb=S16(0x04))
    image_file_id:   PerGameStructField / Varies(nsmb=S16(0x06))

    nsmb_unk_08:     PerGameStructField / Varies(nsmb=S16(0x08))
    nsmb_unk_0E:     PerGameStructField / Varies(nsmb=S16(0x0E))

    # Position, scrolling
    x:               PerGameStructField / Varies(                nsmbw=S16(0x06))
    y:               PerGameStructField / Varies(                nsmbw=S16(0x08))
    x_scroll_rate:   PerGameStructField / Varies(nsmb=U8(0x0A).mask(0xF).enum(BackgroundScrollRate),
                                                                 nsmbw=S16(0x02).enum(BackgroundScrollRate))
    y_scroll_rate:   PerGameStructField / Varies(nsmb=U8(0x0C).mask(0xF).enum(BackgroundScrollRate),
                                                                 nsmbw=S16(0x04).enum(BackgroundScrollRate))
    move_downwards:  PerGameStructField / Varies(nsmb=U8(0x0C).mask_bool(0x80))  # crashes sometimes

    # NSMBW stuff
    file_id_1:       PerGameStructField / Varies(                nsmbw=U16(0x0A))
    file_id_2:       PerGameStructField / Varies(                nsmbw=U16(0x0C))
    file_id_3:       PerGameStructField / Varies(                nsmbw=U16(0x0E))
    zoom:            PerGameStructField / Varies(                nsmbw=U8(0x13).enum(BackgroundZoom))


class LevelTilesetInfo(LevelItem):
    """
    A class representing information about the area's tileset.
    (NSMB-only) (probably mostly unused)
    """
    length = Varies(nsmb=20)

    id:              PerGameStructField / U16(0x00)
    tilemap_file_id: PerGameStructField / S16(0x02)
    palette_file_id: PerGameStructField / S16(0x04)
    image_file_id:   PerGameStructField / S16(0x06)

    # Plus more (unused) stuff maybe?


class LevelBackground(LevelItem):
    """
    A class representing a "DistantView"-style background struct
    """
    length = Varies(nsmb2=28, like_nsmbu=28)

    class NSMB2ParallaxMode(StructFieldEnum):
        """
        "Ignore Y offset" causes the game to ignore the "y" field
        """
        PARALLAX_X_Y_IGNORE_Y_OFFSET = Varies(nsmb2=0)
        PARALLAX_X_Y                 = Varies(nsmb2=1)
        PARALLAX_NONE                = Varies(nsmb2=2)
        PARALLAX_X                   = Varies(nsmb2=3)
        PARALLAX_Y                   = Varies(nsmb2=4)
        UNKNOWN_5                    = Varies(nsmb2=5)  # TODO: document what this value is

    id:            PerGameStructField / U16(0x00)
    x:             PerGameStructField / Varies(nsmb2=U16(0x04))
    y:             PerGameStructField / Varies(nsmb2=U16(0x02))
    name_bytes:    PerGameStructField / ConcreteBytestring(0x08, 0x10)
    parallax_mode: PerGameStructField / Varies(nsmb2=U16(0x18).enum(NSMB2ParallaxMode))

    # TODO: could the first two be x/y offsets like in NSMB2?
    nsmbu_unk_02:  PerGameStructField / Varies(                 nsmbu=U16(0x02))
    nsmbu_unk_04:  PerGameStructField / Varies(                 nsmbu=U16(0x04))
    nsmbu_unk_06:  PerGameStructField / Varies(                 nsmbu=U16(0x06))
    nsmbu_unk_18:  PerGameStructField / Varies(                 nsmbu=U16(0x18))

    @property
    def name(self):
        return self.name_bytes.rstrip(b'\0').decode('latin-1')
    @name.setter
    def name(self, value):
        self.name_bytes = value.encode('latin-1').ljust(16, b'\0')


class LevelEntrance(LevelItem):
    """
    A class representing an entrance in a course file.
    """
    length = Varies(nsmb=20, nsmbw=20, nsmb2=24, like_nsmbu=24)

    class Transition(StructFieldEnum):
        DEFAULT                         = Varies(0)
        FORCE_FADE                      = Varies(        like_nsmbu=1)
        FORCE_MARIO_HEAD                = Varies(        like_nsmbu=2)
        FORCE_CIRCLE_TOWARDS_CENTER     = Varies(        like_nsmbu=3)
        FORCE_BOWSER_HEAD               = Varies(        like_nsmbu=4)
        FORCE_CIRCLE_TOWARDS_ENTRANCE_1 = Varies(        like_nsmbu=5)
        FORCE_WAVES_DOWN                = Varies(nsmb=1, like_nsmbu=6)
        FORCE_WAVES_DOWN_UP             = Varies(        like_nsmbu=7)  # down on fade-out, up on fade-in
        FORCE_WAVES_UP_DOWN             = Varies(        like_nsmbu=8)  # up on fade-out, down on fade-in
        FORCE_MUSHROOM                  = Varies(        like_nsmbu=9)
        FORCE_CIRCLE_TOWARDS_ENTRANCE_2 = Varies(        like_nsmbu=10)
        FORCE_NONE                      = Varies(        like_nsmbu=11)

    x:                           PerGameStructField / U16(0x00)
    y:                           PerGameStructField / U16(0x02)
    camera_x:                    PerGameStructField / Varies(nsmb=S16(0x04),                 nsmb2=S16(0x04), like_nsmbu=S16(0x04))
    camera_y:                    PerGameStructField / Varies(nsmb=S16(0x06),                 nsmb2=S16(0x06), like_nsmbu=S16(0x06))
    id:                          PerGameStructField / U8(0x08)

    destination_area:            PerGameStructField / U8(0x09)  # in NSMB, doubles as "isDirectPipeEnd"
    destination_level:           PerGameStructField / Varies(nsmb=U8(0x0A))  # in NSMB, doubles as "directPipePathID"
    destination_id:              PerGameStructField / Varies(nsmb=U8(0x0C), nsmbw=U8(0x0A), nsmb2=U8(0x0A), like_nsmbu=U8(0x0A))
    destination_world:           PerGameStructField / Varies(nsmb=U8(0x0B))
    destination_world_map_node:  PerGameStructField / Varies(nsmb=U8(0x13))

    type:                        PerGameStructField / Varies(nsmb=U8(0x0E), nsmbw=U8(0x0B), nsmb2=U8(0x0B), like_nsmbu=U8(0x0B))
    zone_id:                     PerGameStructField / Varies(nsmb=U8(0x12), nsmbw=U8(0x0D), nsmb2=U8(0x0D), like_nsmbu=U8(0x0D))
    layer:                       PerGameStructField / Varies(               nsmbw=U8(0x0E))
    zoom:                        PerGameStructField / Varies(nsmb=U8(0x0D))

    suppress_player_1:           PerGameStructField / Varies(like_nsmbu=U8(0x0C).mask_bool(1))
    suppress_player_2:           PerGameStructField / Varies(like_nsmbu=U8(0x0C).mask_bool(2))
    suppress_player_3:           PerGameStructField / Varies(like_nsmbu=U8(0x0C).mask_bool(4))
    suppress_player_4:           PerGameStructField / Varies(like_nsmbu=U8(0x0C).mask_bool(8))

    distance_between_players:    PerGameStructField / Varies(                                               like_nsmbu=U8(0x0F))
    # Number of tiles between each player = 1 + (value / 2)
    # Only works with entrance types 25 and 34

    baby_yoshi_entrance_id:      PerGameStructField / Varies(                                               like_nsmbu=U8(0x12))
    coin_edit_order:             PerGameStructField / Varies(                                               like_nsmbu=U8(0x13))
    autoscroll_path_id:          PerGameStructField / Varies(                                               like_nsmbu=U8(0x14))
    autoscroll_path_node_index:  PerGameStructField / Varies(                                               like_nsmbu=U8(0x15))

    nsmbw_direct_pipe_path_id:   PerGameStructField / Varies(               nsmbw=U8(0x0F))
    nsmbw_direct_pipe_direction: PerGameStructField / Varies(               nsmbw=U8(0x13))  # in NSMB, this is in path node data

    appear_on_bottom_screen:     PerGameStructField / Varies(nsmb=U8(0x0F).mask_bool(1))
    is_direct_pipe:              PerGameStructField / Varies(nsmb=U8(0x0F).mask_bool(8),
                                                             nsmbw=U16(0x10).mask_bool(8))
    transition:                  PerGameStructField / Varies(nsmb=U8(0x0F).rshift(4).mask(1).enum(Transition),
                                                             like_nsmbu=U8(0x16).enum(Transition))
    non_enterable:               PerGameStructField / Varies(nsmb=U8(0x0F).mask_bool(0x80),
                                                             nsmbw=U16(0x10).mask_bool(0x80),
                                                             nsmb2=U16(0x10).mask_bool(0x80),
                                                             like_nsmbu=U16(0x10).mask_bool(0x80))
    nsmbw_is_direct_pipe_end:    PerGameStructField / Varies(nsmbw=U16(0x10).mask_bool(1))
    nsmbw_flags_unk_mask_2:      PerGameStructField / Varies(nsmbw=U16(0x10).mask_bool(2))
    is_forward_pipe:             PerGameStructField / Varies(nsmbw=U16(0x10).mask_bool(4))
    nsmb2_flags_unk_mask_1:      PerGameStructField / Varies(nsmb2=U16(0x10).mask_bool(1))
    return_to_world_map:         PerGameStructField / Varies(nsmb2=U16(0x10).mask_bool(0x10))
    nsmb2_flags_unk_mask_40:     PerGameStructField / Varies(nsmb2=U16(0x10).mask_bool(0x40))
    player_spawns_facing_left:   PerGameStructField / Varies(like_nsmbu=U16(0x10).mask_bool(1))

    # "Flags" value (NSMB: u8 @ 0xF; NSMBW/2/U: u16 @ 0x10):
    #     NSMB:
    #         & 01 -> appear on bottom screen
    #         & 08 -> is direct pipe
    #         & 10 -> use wavy wipe instead of Mario head transition
    #         & 80 -> non-enterable
    #     NSMBW:
    #         & 01 -> direct pipe end
    #         & 02 -> unknown flag
    #         & 04 -> is "forward pipe"
    #         & 08 -> is direct pipe
    #         & 80 -> non-enterable
    #     NSMB2:
    #         & 01 -> unk
    #         & 10 -> return to world map
    #         & 40 -> unk
    #         & 80 -> non-enterable
    #     NSMBU:
    #         & 01 -> player spawns facing left
    #         & 80 -> non-enterable

    nsmb_unk_10:                 PerGameStructField / Varies(nsmb=U8(0x10))
    nsmb_unk_11:                 PerGameStructField / Varies(nsmb=U8(0x11))
    nsmb2_unk_14:                PerGameStructField / Varies(                                   nsmb2=U8(0x14))
    nsmb2_unk_15:                PerGameStructField / Varies(                                   nsmb2=U8(0x15))


    @only_in([Game.NEW_SUPER_MARIO_BROS, Game.NEW_SUPER_MARIO_BROS_WII])
    def get_is_direct_pipe_end(self, game):
        if game is Game.NEW_SUPER_MARIO_BROS:
            return bool(self.destination_area)
        else:
            return self.nsmbw_is_direct_pipe_end

    @only_in([Game.NEW_SUPER_MARIO_BROS, Game.NEW_SUPER_MARIO_BROS_WII])
    def set_is_direct_pipe_end(self, game, value):
        if game is Game.NEW_SUPER_MARIO_BROS:
            self.destination_area = 1 if value else 0
        else:
            self.nsmbw_is_direct_pipe_end = bool(value)

    @property
    def enterable(self):
        return not self.non_enterable
    @enterable.setter
    def enterable(self, value):
        self.non_enterable = not value


class LevelSprite(LevelItem):
    """
    A class representing a sprite in a course file.
    """
    length = Varies(nsmb=12, nsmbw=16, nsmb2=24, like_nsmbu=24)
    block_terminator = b'\xFF\xFF\xFF\xFF'

    type:          PerGameStructField / U16(0x00)
    x:             PerGameStructField / U16(0x02)
    y:             PerGameStructField / U16(0x04)
    data_1:        PerGameStructField / Varies(nsmb=ConcreteBytestring(0x06, 6),
                                                               nsmbw=ConcreteBytestring(0x06, 6),
                                                                                nsmb2=ConcreteBytestring(0x06, 10),
                                                                                                  like_nsmbu=ConcreteBytestring(0x06, 10))
    zone_id:       PerGameStructField / Varies(                nsmbw=U8(0x0C),  nsmb2=U8(0x10),   like_nsmbu=U8(0x10))
    layer:         PerGameStructField / Varies(                nsmbw=U8(0x0D),  nsmb2=U8(0x11),   like_nsmbu=U8(0x11))
    data_2:        PerGameStructField / Varies(                                 nsmb2=ConcreteBytestring(0x12, 2),
                                                                                                  like_nsmbu=ConcreteBytestring(0x12, 2))
    initial_state: PerGameStructField / Varies(                                                   like_nsmbu=U8(0x14))


@only_in(Game.all - set([Game.NEW_SUPER_MARIO_BROS]))
def load_used_sprite_ids_block(game, data):
    """
    Load used sprite IDs from the given block data.
    """
    num_ids = len(data) // 4
    ids = set(struct.unpack_from(game.endianness() + 'Hxx' * num_ids, data, 0))

    return ids


@only_in(Game.all - set([Game.NEW_SUPER_MARIO_BROS]))
def save_used_sprite_ids_block(game, ids):
    """
    Save used sprite IDs back to block data.
    """
    return b''.join([struct.pack(game.endianness() + 'Hxx', x) for x in sorted(ids)])


class LevelZone(LevelItem, MixinPositionAndSize):
    """
    A class representing a zone in a course file.
    """
    length = Varies(nsmb=16, nsmbw=24, nsmb2=28, like_nsmbu=28)

    x:                    PerGameStructField / S16(0x00)
    y:                    PerGameStructField / S16(0x02)
    width:                PerGameStructField / S16(0x04) = 512
    height:               PerGameStructField / S16(0x06) = 256

    theme:                PerGameStructField / Varies(nsmb=U8(0x0E), nsmbw=U16(0x08),                 like_nsmbu=U16(0x08))
    lighting:             PerGameStructField / Varies(               nsmbw=U16(0x0A),                 like_nsmbu=U16(0x0A))
    nsmb2_unk_08:         PerGameStructField / Varies(                               nsmb2=U16(0x0A))

    id:                   PerGameStructField / Varies(nsmb=U8(0x08), nsmbw=U8(0x0C), nsmb2=U8(0x0C), like_nsmbu=U8(0x0C)) = 1
    bounds_id:            PerGameStructField / Varies(nsmb=U8(0x09), nsmbw=U8(0x0D), nsmb2=U8(0x0D), like_nsmbu=U8(0x0D))

    tracking_settings:    PerGameStructField / Varies(               nsmbw=U8(0x0E),                 like_nsmbu=U8(0x0E))
    zoom:                 PerGameStructField / Varies(               nsmbw=U8(0x0F),                 like_nsmbu=U8(0x0F))
    visibility:           PerGameStructField / Varies(               nsmbw=U8(0x11),                 like_nsmbu=U8(0x11))

    bga_block_id:         PerGameStructField / Varies(nsmb=U8(0x0D), nsmbw=U8(0x12))
    bgb_block_id:         PerGameStructField / Varies(nsmb=U8(0x0B), nsmbw=U8(0x13))
    bg_block_id:          PerGameStructField / Varies(                               nsmb2=U8(0x18), like_nsmbu=U8(0x12))
    tileset_block_id:     PerGameStructField / Varies(nsmb=U8(0x0C))

    multiplayer_tracking: PerGameStructField / Varies(               nsmbw=U8(0x14), nsmb2=U8(0x14), like_nsmbu=U8(0x14))
    progress_path_id:     PerGameStructField / Varies(nsmb=U8(0x0F),                 nsmb2=U8(0x15))
    music:                PerGameStructField / Varies(nsmb=U8(0x0A), nsmbw=U8(0x16), nsmb2=U8(0x16), like_nsmbu=U8(0x16))
    sound_modulation:     PerGameStructField / Varies(               nsmbw=U8(0x17),                 like_nsmbu=U8(0x17))

    nsmbu_flags:          PerGameStructField / Varies(                                               like_nsmbu=U8(0x19))
    # & 01 -> Start zoomed out
    # & 02 -> Center camera x upon load
    # & 04 -> Y tracking
    # & 08 -> Camera stops at zone end
    # & 10 -> (Unused)
    # & 20 -> Toad-house related (1)
    # & 40 -> (Unused)
    # & 80 -> Toad-house related (2)


class LevelLocation(LevelItem, MixinPositionAndSize):
    """
    A class representing a location in a course file.
    """
    length = 12

    x:      PerGameStructField / U16(0x00)
    y:      PerGameStructField / U16(0x02)
    width:  PerGameStructField / U16(0x04) = 128
    height: PerGameStructField / U16(0x06) = 128
    id:     PerGameStructField / U8(0x08) = 1


class LevelPath(LevelItem):
    """
    A class representing a path in a course file.
    """
    length = Varies(nsmb=8, nsmbw=8, nsmb2=12, like_nsmbu=12)

    id:               PerGameStructField / U8(0x00) = 1
    start_node_index: PerGameStructField / U16(0x02)
    num_nodes:        PerGameStructField / U16(0x04)
    loop_flag:        PerGameStructField / U16(0x06)
    # loop flag is active if == 2


class LevelPathNode(LevelItem):
    """
    A class representing a path node in a course file.
    """
    length = Varies(nsmb=16, nsmbw=16, nsmb2=20, like_nsmbu=20)

    x:            PerGameStructField / U16(0x00)
    y:            PerGameStructField / U16(0x02)
    speed:        PerGameStructField / Varies(nsmb=S32(0x04), nsmbw=F32(0x04), nsmb2=F32(0x04), like_nsmbu=F32(0x04))
    acceleration: PerGameStructField / Varies(nsmb=S32(0x08), nsmbw=F32(0x08), nsmb2=F32(0x08), like_nsmbu=F32(0x08))
    delay:        PerGameStructField / Varies(nsmb=S16(0x0C), nsmbw=S16(0x0C), nsmb2=S16(0x0C), like_nsmbu=S16(0x0C))

    user_data:    PerGameStructField / Varies(nsmb=S16(0x0E))

    # TODO: this struct is unfinished:
    # NSMB2 has 4 more bytes of random unknown stuff starting at 0xE.
    # NSMBU has 5.


class LevelProgressPath(LevelItem):
    """
    A class representing a progress path in a course file.
    """
    length = Varies(nsmb=8, nsmbw=8, nsmb2=12, like_nsmbu=12)

    id:               PerGameStructField / U8(0x00) = 1
    start_node_index: PerGameStructField / U16(0x02)
    num_nodes:        PerGameStructField / U16(0x04)


class LevelProgressPathNode(LevelItem):
    """
    A class representing a progress path node in a course file.
    """
    length = Varies(nsmb=16, nsmbw=16, nsmb2=20, like_nsmbu=20)

    x: PerGameStructField / U16(0x00)
    y: PerGameStructField / U16(0x02)


########################################################################
########################### Course file class ##########################
########################################################################


def get_raw_loader_and_saver(block_num, split: int = None):
    """
    Return a pair of block loader/saver functions, which put raw bytes
    data into course.unparsed_blocks[block_num].
    If split is not None, the data will be split into a list, where each
    entry if of length split.
    """
    def loader(game, course, data: bytes):
        if split:
            data = _common.divide_block(data, split)
        course.unparsed_blocks[block_num] = data

    def saver(game, course) -> bytes:
        data = course.unparsed_blocks[block_num]
        if split:
            data = b''.join(data)

        return data

    return loader, saver


def get_sprite_sets_loader_and_saver():
    """
    Return a pair of block loader/saver functions, which handle NSMB
    sprite set data.
    """
    def loader(game, course, data: bytes):
        if len(data) != 16:
            raise ValueError('Sprite set data must be of length 16')
        course.sprite_sets = list(data)

    def saver(game, course) -> bytes:
        if len(course.sprite_sets) != 16:
            raise ValueError('Sprite set values list must be of length 16')
        return bytes(course.sprite_sets)

    return loader, saver


def get_tileset_names_loader_and_saver():
    """
    Return a pair of block loader/saver functions, which handle the
    tileset names block (NSMBW/2/U).
    """
    def loader(game, course, data: bytes):
        course.tileset_names = load_tileset_names_block(game, data)

    def saver(game, course) -> bytes:
        return save_tileset_names_block(game, course.tileset_names)

    return loader, saver


def get_used_sprite_ids_loader_and_saver():
    """
    Return a pair of block loader/saver functions, which handle the
    "used sprite IDs" data (NSMBW/2/U).
    """
    def loader(game, course, data: bytes):
        course.used_sprite_ids = load_used_sprite_ids_block(game, data)

    def saver(game, course) -> bytes:
        return save_used_sprite_ids_block(game, course.used_sprite_ids)

    return loader, saver


BLOCK_LOADERS_SAVERS = {}
# Format of BLOCK_LOADERS_SAVERS item values:
# List of 2-tuples (loader, saver), where:
#     loader(game: Game, course: LevelCourse, data: bytes) -> None
#     saver(game: Game, course: LevelCourse) -> bytes

BLOCK_LOADERS_SAVERS[Game.NEW_SUPER_MARIO_BROS] = [
    LevelOptions.get_individual_loader_and_saver('options'),
    LevelZoneBounds.get_block_loader_and_saver('zone_bounds'),
    LevelBackgroundLayer.get_block_loader_and_saver('backgrounds_b'),
    LevelTilesetInfo.get_block_loader_and_saver('tileset_infos'),
    LevelBackgroundLayer.get_block_loader_and_saver('backgrounds_a'),
    LevelEntrance.get_block_loader_and_saver('entrances'),
    LevelSprite.get_block_loader_and_saver('sprites'),
    LevelZone.get_block_loader_and_saver('zones'),
    LevelLocation.get_block_loader_and_saver('locations'),
    LevelProgressPath.get_block_loader_and_saver('progress_paths'),
    LevelPath.get_block_loader_and_saver('paths'),
    LevelProgressPathNode.get_block_loader_and_saver('progress_path_nodes'),
    LevelPathNode.get_block_loader_and_saver('path_nodes'),
    get_sprite_sets_loader_and_saver(),
]
assert len(BLOCK_LOADERS_SAVERS[Game.NEW_SUPER_MARIO_BROS]) == 14

BLOCK_LOADERS_SAVERS[Game.NEW_SUPER_MARIO_BROS_WII] = [
    get_tileset_names_loader_and_saver(),
    LevelOptions.get_individual_loader_and_saver('options'),
    LevelZoneBounds.get_block_loader_and_saver('zone_bounds'),
    get_raw_loader_and_saver(3, 8),
    LevelBackgroundLayer.get_block_loader_and_saver('backgrounds_a'),
    LevelBackgroundLayer.get_block_loader_and_saver('backgrounds_b'),
    LevelEntrance.get_block_loader_and_saver('entrances'),
    LevelSprite.get_block_loader_and_saver('sprites'),
    get_used_sprite_ids_loader_and_saver(),
    LevelZone.get_block_loader_and_saver('zones'),
    LevelLocation.get_block_loader_and_saver('locations'),
    get_raw_loader_and_saver(11),
    LevelPath.get_block_loader_and_saver('paths'),
    LevelPathNode.get_block_loader_and_saver('path_nodes'),
]
assert len(BLOCK_LOADERS_SAVERS[Game.NEW_SUPER_MARIO_BROS_WII]) == 14

BLOCK_LOADERS_SAVERS[Game.NEW_SUPER_MARIO_BROS_2] = [
    get_tileset_names_loader_and_saver(),
    LevelOptions.get_individual_loader_and_saver('options'),
    LevelZoneBounds.get_block_loader_and_saver('zone_bounds'),
    get_raw_loader_and_saver(3, 8),
    LevelBackground.get_block_loader_and_saver('backgrounds'),
    get_raw_loader_and_saver(5),
    LevelEntrance.get_block_loader_and_saver('entrances'),
    LevelSprite.get_block_loader_and_saver('sprites'),
    get_used_sprite_ids_loader_and_saver(),
    LevelZone.get_block_loader_and_saver('zones'),
    LevelLocation.get_block_loader_and_saver('locations'),
    get_raw_loader_and_saver(11),
    get_raw_loader_and_saver(12),
    LevelPath.get_block_loader_and_saver('paths'),
    LevelPathNode.get_block_loader_and_saver('path_nodes'),
    LevelProgressPath.get_block_loader_and_saver('progress_paths'),
    LevelProgressPathNode.get_block_loader_and_saver('progress_path_nodes'),
]
assert len(BLOCK_LOADERS_SAVERS[Game.NEW_SUPER_MARIO_BROS_2]) == 17

NSMBU_LOADERS_SAVERS = [
    get_tileset_names_loader_and_saver(),
    LevelOptions.get_individual_loader_and_saver('options'),
    LevelZoneBounds.get_block_loader_and_saver('zone_bounds'),
    get_raw_loader_and_saver(3, 8),
    LevelBackground.get_block_loader_and_saver('backgrounds'),
    get_raw_loader_and_saver(5, 10),
    LevelEntrance.get_block_loader_and_saver('entrances'),
    LevelSprite.get_block_loader_and_saver('sprites'),
    get_used_sprite_ids_loader_and_saver(),
    LevelZone.get_block_loader_and_saver('zones'),
    LevelLocation.get_block_loader_and_saver('locations'),
    get_raw_loader_and_saver(11),
    get_raw_loader_and_saver(12),
    LevelPath.get_block_loader_and_saver('paths'),
    LevelPathNode.get_block_loader_and_saver('path_nodes'),
]
assert len(NSMBU_LOADERS_SAVERS) == 15

for g in Game.all_like_nsmbu:
    BLOCK_LOADERS_SAVERS[g] = NSMBU_LOADERS_SAVERS
del NSMBU_LOADERS_SAVERS


class LevelCourse:
    """
    Class for a level's course file
    """
    unparsed_blocks: typing.Dict[int, typing.Union[bytes, typing.List[bytes]]]

    def __init__(self):
        """
        Create a new level
        """
        self.unparsed_blocks = {}

        self.tileset_names = ['', '', '', '']
        self.options = None
        self.zone_bounds = []
        self.backgrounds_a = []
        self.backgrounds_b = []
        self.tileset_infos = []
        self.backgrounds = []
        self.entrances = []
        self.sprites = []
        self.used_sprite_ids = set()
        self.zones = []
        self.locations = []
        self.paths = []
        self.path_nodes = []
        self.progress_paths = []
        self.progress_path_nodes = []
        self.sprite_sets = []


    @classmethod
    def load(cls, game, data):
        """
        Load info from course file data, according to the specified game
        """
        loaders_savers = BLOCK_LOADERS_SAVERS.get(game)
        if not loaders_savers:
            raise ValueError(f'No block loaders known for game "{game}"!')

        return cls.load_with_block_loaders(game, data, [x for (x, y) in loaders_savers])


    @classmethod
    def load_with_block_loaders(cls, game, data, loaders):
        """
        Load info from course file data, using the provided list of block loader functions
        """
        self = cls()

        blocks, self.metadata = load_course_blocks(data, len(loaders), game.endianness())

        for block, loader in zip(blocks, loaders):
            loader(game, self, block)

        return self


    def save(self, game):
        """
        Save the level in the correct course file format for the given game.
        Don't forget to call prepare_for_saving() first!
        """
        loaders_savers = BLOCK_LOADERS_SAVERS.get(game)
        if not loaders_savers:
            raise ValueError(f'No block savers known for game "{game}"!')

        return self.save_with_block_savers(game, [y for (x, y) in loaders_savers])


    def save_with_block_savers(self, game, savers):
        """
        Save the level using the provided list of block saver functions.
        Don't forget to call prepare_for_saving() first!
        """
        blocks = [saver(game, self) for saver in savers]
        return save_course_blocks(blocks, self.metadata, game.endianness())


    def prepare_for_saving(self, game, *, update_sprite_zone_ids=True, sort_sprites_by_zone=True, update_used_sprite_ids=True):
        """
        Make some automatic adjustments required for the course to not
        crash the game. Each adjustment can be individually disabled if
        you want.
        """
        if update_sprite_zone_ids:
            if self.zones:
                for s in self.sprites:
                    x, y = s.x, s.y

                    if game == Game.NEW_SUPER_MARIO_BROS:
                        # NSMB measures sprite positions in tiles instead of
                        # 16ths-of-a-tile like the other games.
                        # So we have to multiply by 16 here.
                        x, y = x * 16, y * 16

                    s.zone_id = self.map_position_to_zone(x, y).id

            else:
                # Welp.
                # Could raise an exception, but that'll just manifest as
                # an annoying edge-case crash in the overlying
                # application. I don't want that. Instead, let's just
                # assign zone ID 0.
                for s in self.sprites:
                    s.zone_id = 0

        if sort_sprites_by_zone:
            # Note: this HAS to happen after the sprite zone IDs are
            # updated
            # Note 2: NSMBDS doesn't require sprites to be sorted in the
            # level file -- it does its own bubble sort (!) upon area
            # load. Sorting ahead of time isn't harmful, and might
            # improve load times slightly (because bubble sort), so,
            # might as well.
            self.sprites.sort(key=lambda s: s.zone_id)

        if update_used_sprite_ids:
            self.used_sprite_ids = set(s.type for s in self.sprites)


    def map_position_to_zone(self, x, y):
        """
        Return the LevelZone containing or nearest the specified position
        (measured in zone coordinates -- 16 = one tile).
        If the position is within multiple zones, return the first one in the list.
        If there are no zones at all, return None.
        """
        closest_distance = closest_zone = None

        for z in self.zones:
            # Return immediately if the position is within the zone
            if (z.x <= x <= z.x + z.width) and (z.y <= y <= z.y + z.height):
                return z

            # Calculate horizontal distance
            xdist = 0
            if x <= z.x:
                xdist = z.x - x
            elif x >= z.x + z.width:
                xdist = x - (z.x + z.width)

            # Calculate vertical distance
            ydist = 0
            if y <= z.y:
                ydist = z.y - y
            elif y >= z.y + z.height:
                ydist = y - (z.y + z.height)

            # Total distance (Pythagorean theorem)
            dist = (xdist ** 2 + ydist ** 2) ** 0.5

            # New record?
            if closest_distance is None or dist < closest_distance:
                closest_distance = dist
                closest_zone = z

        return closest_zone


class Area:
    """
    An area
    """
    course: LevelCourse
    layer_0: typing.List[LevelObject]
    layer_1: typing.List[LevelObject]
    layer_2: typing.List[LevelObject]

    def __init__(self, course=None, layer_0=None, layer_1=None, layer_2=None):
        self.course = course
        self.layer_0 = layer_0 if layer_0 else []
        self.layer_1 = layer_1 if layer_1 else []
        self.layer_2 = layer_2 if layer_2 else []


    @classmethod
    def load(cls, game, course_file, layer_0, layer_1, layer_2):
        return cls.load_with_course_and_bgdat_loaders(game, course_file, layer_0, layer_1, layer_2, LevelCourse.load, load_bgdat)


    @classmethod
    def load_with_course_and_bgdat_loaders(cls, game, course_file, layer_0, layer_1, layer_2, course_loader, bgdat_loader):
        self = cls()

        self.course = course_loader(game, course_file)

        if layer_0:
            self.layer_0 = bgdat_loader(game, layer_0)
        if layer_1:
            self.layer_1 = bgdat_loader(game, layer_1)
        if layer_2:
            self.layer_2 = bgdat_loader(game, layer_2)

        # # TEMP: debugging
        # a, b, c, d = self.save()
        # if a != course_file:
        #     with open('TEMP_A.bin', 'wb') as f:
        #         f.write(course_file)
        #     with open('TEMP_B.bin', 'wb') as f:
        #         f.write(a)
        # assert a == course_file
        # assert b == layer_0
        # assert c == layer_1
        # assert d == layer_2

        return self


    def save(self, game):
        """
        Returns None instead of [] for any empty layers, since you
        shouldn't save files for those layers at all
        """
        return self.save_with_bgdat_saver(game, save_bgdat)


    def save_with_bgdat_saver(self, game, bgdat_saver):
        """
        Returns None instead of [] for any empty layers, since you
        shouldn't save files for those layers at all
        """
        layer_0 = layer_1 = layer_2 = None

        if self.layer_0:
            layer_0 = bgdat_saver(game, self.layer_0)
        if self.layer_1:
            layer_1 = bgdat_saver(game, self.layer_1)
        if self.layer_2:
            layer_2 = bgdat_saver(game, self.layer_2)

        self.course.prepare_for_saving(game)

        return self.course.save(game), layer_0, layer_1, layer_2


class Level:
    """
    A full level
    """
    areas: typing.List[Area]

    def __init__(self, areas=None):
        self.areas = areas if areas else []


    @classmethod
    def load(cls, game, data):
        return cls.load_with_area_loader(game, data, Area.load)


    @classmethod
    def load_with_area_loader(cls, game, data, area_loader):
        self = cls()

        if game == Game.NEW_SUPER_MARIO_BROS:
            # NSMB doesn't have an official level file format;
            # currently, the fan-invented NML format is used for that.
            # We can detect that and load it.
            if data.startswith(nsmbe.NML_MAGIC):
                version, other = nsmbe.load_nml(data)
                if version != 1:
                    raise ValueError(f'Unsupported NML version: {version}')

                _, _, course_file, objects_file = other
                self.areas = [area_loader(game, course_file, None, objects_file, None)]

            else:
                raise ValueError(f'Unknown NSMB level format (starts with {data[:8]})')

        elif game == Game.NEW_SUPER_MARIO_BROS_WII:
            arc = u8.load(data)['course']
            for i in range(4):
                if f'course{i+1}.bin' not in arc:
                    break

                self.areas.append(area_loader(
                    game,
                    arc[f'course{i+1}.bin'],
                    arc.get(f'course{i+1}_bgdatL0.bin'),
                    arc.get(f'course{i+1}_bgdatL1.bin'),
                    arc.get(f'course{i+1}_bgdatL2.bin')))

        else:
            raise NotImplementedError

        return self


    def save(self, game):
        if game == Game.NEW_SUPER_MARIO_BROS:
            assert len(self.areas) == 1
            course, _, L1, _ = self.areas[0].save()
            return nsmbe.save_nml(1, (0, 0, course, L1))

        elif game == Game.NEW_SUPER_MARIO_BROS_WII:
            course_folder = {}
            for i, area in enumerate(self.areas):
                course, L0, L1, L2 = area.save(game)

                course_folder[f'course{i+1}.bin'] = course

                if L0:
                    course_folder[f'course{i+1}_bgdatL0.bin'] = L0
                if L1:
                    course_folder[f'course{i+1}_bgdatL1.bin'] = L1
                if L2:
                    course_folder[f'course{i+1}_bgdatL2.bin'] = L2

            return u8.save({'course': course_folder})

        else:
            raise NotImplementedError

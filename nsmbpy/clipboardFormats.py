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
Support for the various "Clip" clipboard text formats used by popular
NSMB-series level editors.
"""

import enum
import typing as ty

from . import Game
from . import level


# FORMAT DOCUMENTATION =================================================

# NSMBeClip format -----------------------------------------------------
# (see: Editor/ObjectsEditionMode.cs/ObjectsEditionMode:EditionMode.paste())
#
# "NSMBeClip|ITEMS|"
#
# Positions and sizes are measured in units of 1 tile for objects and
#     sprites, 1/16 of a tile for everything else
# Positions are absolute, but NSMBe centers the selection upon paste,
#     so the origin doesn't really matter
# Items are separated by ":" (not "|" as in the other clipboard formats)
#
# Item types:
#     Object (bgdat):
#         OBJ:X:Y:Width:Height:Tileset:ID
#     Sprite:
#         SPR:X:Y:ID:Spritedata
#         Spritedata is given as an uppercase hex string of length 12,
#         in in-editor byte order (i.e. byte indices 1, 0, 5, 4, 3, 2)
#     Entrance:
#         ENT:X:Y:CamX:CamY:ID:DestArea:DestLevel:DestEntrance:Type:Flags:Byte0x10:ZoneID:DestWorldMapNode
#     Zone:
#         VIW:X:Y:Width:Height:ID:MusicID:ZoneValue0x0B:ZoneValue0x0C:ZoneValue0x0D
#             :Lighting:ProgressPathID:UpperBounds:UpperBounds2:LowerBounds:LowerBounds2:BoundsValue0x12
#     Location:
#         ZON:X:Y:Width:Height:ID
#     [Progress] Path node:
#         NOTE: NSMBe copies path nodes, but ignores them when pasting.
#         Also, regular path nodes and progress path nodes are both present, but indistinguishable.
#         Also, there's no way to tell how to group them into paths. Have fun.
#         PTH:X:Y:a:b:c:d:Delay:UserData
#         speed = (b << 16) | a
#         acceleration = (d << 16) | c


# ReggieClip format ----------------------------------------------------
# (see: reggie.py/ReggieWindow.encodeObjects())
#
# "ReggieClip|ITEMS|%"
#
# Positions and sizes are measured in units of 1 tile for objects, 1/16
#     of a tile for sprites
# Positions are absolute, but Reggie centers the selection upon paste,
#     so the origin doesn't really matter
# Items are separated by "|"
#
# Item types:
#     Object (bgdat):
#         0:Tileset:ID:Layer:X:Y:Width:Height
#         Layer: 0 = Layer 0, 1 = Layer 1, 2 = Layer 2
#     Sprite:
#         1:ID:X:Y:Spritedata0:Spritedata1:...:Spritedata5
#         Spritedata is big-endian, so no byte swapping to worry about


# CoinKillerClip format ------------------------------------------------
# (see: objectseditionmode.cpp/ObjectsEditonMode::paste())
#
# "CoinKillerClip|Width:Height|ITEMS"
#
# Width:Height in the header include the full sizes of items as
#     displayed in the editor UI, such as sprite images.
#     This is just used to pick a good origin point when pasting, so
#     that it'll be centered in the current viewport.
# ALL positions and sizes (including for objects) are measured in units
#     of 1/20 of a tile
# CK's logic for calculating the selection origin point when copying is
#     not very good, so negative positions can happen (for example, try
#     copypasting a Pipe Piranha Plant Up)
# Items are separated by "|"
#
# Item types:
#     Object (bgdat):
#         0:ID:Layer:X:Y:Width:Height
#         Layer: 0 = Layer 1; 1 = Layer 2 (load_coinkillerclip() normalizes this to 1=1, 2=2)
#         X/Y/Width/Height are measured in 1/20 tile
#         If there's at least one object anywhere in the selection, the
#             selection origin point will be snapped to tile boundaries.
#             So objects will always have positions that are integer
#             multiples of 20
#     Sprite:
#         1:ID:X:Y:Layer:Spritedata0:Spritedata1:...:Spritedata11
#         X/Y are measured in 1/20 tile
#         Spritedata is given in in-editor byte order
#         (i.e. byte indices 0, 1, 5, 4, 3, 2, 9, 8, 7, 6)
#     Entrance:
#         2:ID:Type:X:Y:DestArea:DestEntr:CamX:CamY:Flags:Unk14:Unk15
#     Zone:
#         3:X:Y:W:H:ID:ProgressPathID:MusicID:MultiplayerTracking:Unk1:BoundID:BGID
#         Width/Height are in units of 1/20 tile
#     Location:
#         4:ID:X:Y:Width:Height
#         Width/Height are in units of 1/20 tile
#     Path:
#         5:ID:LoopFlag:Node1;Node2;...
#         LoopFlag: (& 2 == 0) = no, (& 2 == 2) = yes
#         Path node:
#             Index,X,Y,Speed,Accel,Delay,Rotation,UserData,NextPathID
#             X/Y are given as the center of the green box in the editor,
#             which is the actual position as saved to the level file
#             (I checked)
#     Progress path:
#         6:ID:AltPathFlag:Node1;Node2;...
#         AltPathFlag: (& 2 == 0) = no, (& 2 == 2) = yes
#         Progress path node:
#             Index,X,Y
#             X/Y are given as the center of the yellow box in the editor,
#             which is the actual position as saved to the level file
#             (I checked)


# Miyamoto format as of v28.0 ------------------------------------------
# (see: miyamoto.py/MiyamotoWindow.encodeObjects())
#
# "MiyamotoClip|ITEMS|%"
#
# Almost identical to ReggieClip. There's just a few additional fields
#     added.
#
# Item types:
#     Object (bgdat):
#         0:Tileset:ID:Layer:X:Y:Width:Height:Contents
#         Layer: 0 = Layer 0, 1 = Layer 1, 2 = Layer 2
#     Sprite:
#         1:ID:X:Y:Spritedata0:Spritedata1:...:Spritedata12:Layer:InitialState
#         Spritedata is big-endian, so no byte swapping to worry about
#         (ignoring NSMBUDX for now)


_MAX_SPRITE_NSMBE = 325
_MAX_SPRITE_REGGIE = 482


def _resize_bytes(b, size):
    """
    Make b match the required size, by either padding it with zeros or
    truncating it
    """
    if not isinstance(b, bytes):
        return b'\0' * size

    if len(b) < size:
        return b + b'\0' * (len(b) - size)
    elif len(b) > size:
        return b[:size]
    else:
        return b


class ClipboardFormat(enum.Enum):
    """
    Enum representing various supported clipboard formats
    """
    NSMBE_CLIP = 'NSMBeClip'
    REGGIE_CLIP = 'ReggieClip'
    COINKILLER_CLIP = 'CoinKillerClip'
    MIYAMOTO_CLIP = 'MiyamotoClip'

    def game(self):
        if self is self.NSMBE_CLIP:
            return Game.NEW_SUPER_MARIO_BROS
        if self is self.REGGIE_CLIP:
            return Game.NEW_SUPER_MARIO_BROS_WII
        elif self is COINKILLER_CLIP:
            return Game.NEW_SUPER_MARIO_BROS_2
        elif self is MIYAMOTO_CLIP:
            return Game.NEW_SUPER_MARIO_BROS_U


def detect_format(s: str) -> ClipboardFormat:
    """
    Attempt to auto-detect the clipboard format for the given string.
    Return None if it doesn't match any.
    """
    if s.startswith('NSMBeClip|') and s.endswith('|'):
        return ClipboardFormat.NSMBE_CLIP

    if s.startswith('ReggieClip|') and s.endswith('|%'):
        return ClipboardFormat.REGGIE_CLIP

    if s.startswith('CoinKillerClip|'):
        return ClipboardFormat.COINKILLER_CLIP

    if s.startswith('MiyamotoClip|') and s.endswith('|%'):
        return ClipboardFormat.MIYAMOTO_CLIP


def load_nsmbeclip(s: str):
    """
    Load a NSMBeClip from a string.

    Return a 6-tuple: objects, sprites, entrances, zones and bounds, locations, path nodes.
    - objects: dict {layer_num: [list of LevelObject]}
        NSMBDS only supports one layer, so this will only ever be zero
        or one element long. It's like this for consistency with the
        other clipboard functions
    - sprites: list of LevelSprite
    - entrances: list of LevelEntrance
    - zones and bounds: list of 2-tuples: (LevelZone, LevelZoneBounds)
    - locations: list of LevelLocation
    - path nodes: list of LevelPathNode
        This represents both path nodes and progress-path nodes together
        They're also not grouped into paths -- NSMBeClip doesn't provide that info.
    """
    if not (s.startswith('NSMBeClip|') and s.endswith('|')):
        raise ValueError('Invalid NSMBeClip')

    objects = {}
    sprites = []
    entrances = []
    zones_and_bounds = []
    locations = []
    path_nodes = []

    parts = s.split('|')[1].split(':')
    i = 0
    while i < len(parts):
        if parts[i] == 'OBJ':  # Object
            objects.setdefault(1, []).append(level.LevelObject(
                x=int(parts[i + 1]),
                y=int(parts[i + 2]),
                width=int(parts[i + 3]),
                height=int(parts[i + 4]),
                tileset_id=int(parts[i + 5]),
                type=int(parts[i + 6]),
            ))
            i += 7

        elif parts[i] == 'SPR':  # Sprite
            raw_data = bytes.fromhex(parts[i + 4])
            sprites.append(level.LevelSprite(
                x=int(parts[i + 1]),
                y=int(parts[i + 2]),
                type=int(parts[i + 3]),
                data_1=bytes(raw_data[idx] for idx in [1, 0, 5, 4, 3, 2]),
            ))
            i += 5

        elif parts[i] == 'ENT':  # Entrance
            entrances.append(level.LevelEntrance(
                x=int(parts[i + 1]),
                y=int(parts[i + 2]),
                camera_x=int(parts[i + 3]),
                camera_y=int(parts[i + 4]),
                id=int(parts[i + 5]),
                destination_area=int(parts[i + 6]),
                destination_level=int(parts[i + 7]),
                destination_id=int(parts[i + 8]),
                type=int(parts[i + 9]),
                appear_on_bottom_screen=bool(int(parts[i + 10]) & 1),
                is_direct_pipe=bool(int(parts[i + 10]) & 8),
                transition=level.LevelEntrance.Transition.load(Game.NEW_SUPER_MARIO_BROS, (int(parts[i + 10]) >> 4) & 1),
                non_enterable=bool(int(parts[i + 10]) & 0x80),
                nsmb_unk_10=int(parts[i + 11]),
                zone_id=int(parts[i + 12]),
                destination_world_map_node=int(parts[i + 13]),
            ))
            i += 14

        elif parts[i] == 'VIW':  # Zone
            zone = level.LevelZone(
                x=int(parts[i + 1]),
                y=int(parts[i + 2]),
                width=int(parts[i + 3]),
                height=int(parts[i + 4]),
                id=int(parts[i + 5]),
                music=int(parts[i + 6]),
                bgb_block_id=int(parts[i + 7]),
                tileset_block_id=int(parts[i + 8]),
                bga_block_id=int(parts[i + 9]),
                theme=int(parts[i + 10]),
                progress_path_id=int(parts[i + 11]),
            )
            bounds = level.LevelZoneBounds(
                upper=int(parts[i + 12]),
                upper_2=int(parts[i + 13]),
                lower=int(parts[i + 14]),
                lower_2=int(parts[i + 15]),
                vertical_scroll_limit=int(parts[i + 16]),
            )
            zones_and_bounds.append((zone, bounds))
            i += 17

        elif parts[i] == 'ZON':  # Location
            locations.append(level.LevelLocation(
                x=int(parts[i + 1]),
                y=int(parts[i + 2]),
                width=int(parts[i + 3]),
                height=int(parts[i + 4]),
                id=int(parts[i + 5]),
            ))
            i += 6

        elif parts[i] == 'PTH':  # Path node
            path_nodes.append(level.LevelPathNode(
                x=int(parts[i + 1]),
                y=int(parts[i + 2]),
                speed=(int(parts[i + 4]) << 16) | int(parts[i + 3]),
                acceleration=(int(parts[i + 6]) << 16) | int(parts[i + 5]),
                delay=int(parts[i + 7]),
                user_data=int(parts[i + 8]),
            ))
            i += 9

        else:
            # should never happen, but let's move on and hope we get re-aligned soon
            i += 1

    return objects, sprites, entrances, zones_and_bounds, locations, path_nodes


def save_nsmbeclip(objects, sprites, entrances, zones_and_bounds, locations, path_nodes, *, allow_unsafe=False, unsafe_list=None) -> str:
    """
    Save items back to a NSMBeClip.

    If allow_unsafe is True (default False), sanity checks will be
    skipped, which might result in a clip that crashes the editor when
    pasted. If allow_unsafe is False, you can provide a list in the
    unsafe_list parameter, which will be populated with all items that
    were omitted from the clip for safety reasons.
    """
    if unsafe_list is None: unsafe_list = []

    clip = []

    for layer_num, layer in objects.items():
        for o in layer:
            if not allow_unsafe and (layer_num != 1 or o.tileset_id > 2):
                # NSMBe cancels the entire paste if an object is invalid
                unsafe_list.append(o)
                continue

            clip.append(f'OBJ:{o.x}:{o.y}:{o.width}:{o.height}:{o.tileset_id}:{o.type}')

    for s in sprites:
        if not allow_unsafe and s.type > _MAX_SPRITE_NSMBE:
            # Crashes NSMBe
            unsafe_list.append(s)
            continue

        sdata = bytes(_resize_bytes(s.data_1, 6)[idx] for idx in [1, 0, 5, 4, 3, 2]).hex().upper()
        clip.append(f'SPR:{s.x}:{s.y}:{s.type}:{sdata}')

    for e in entrances:
        flags = e.save(Game.NEW_SUPER_MARIO_BROS)[0xF]
        clip.append(f'ENT:{e.x}:{e.y}:{e.camera_x}:{e.camera_y}:{e.id}:{e.destination_area}:{e.destination_level}:{e.destination_id}:{e.type}:{flags}:{e.nsmb_unk_10}:{e.zone_id}:{e.destination_world_map_node}')

    for z, b in zones_and_bounds:
        clip.append(f'VIW:{z.x}:{z.y}:{z.width}:{z.height}:{z.id}:{z.music}:{z.bgb_block_id}:{z.tileset_block_id}:{z.bga_block_id}:{z.theme}:{z.progress_path_id}:{b.upper}:{b.upper_2}:{b.lower}:{b.lower_2}:{b.vertical_scroll_limit}')

    for L in locations:
        clip.append(f'ZON:{L.x}:{L.y}:{L.width}:{L.height}:{L.id}')

    for n in path_nodes:
        clip.append(f'PTH:{n.x}:{n.y}:{n.speed & 0xffff}:{n.speed >> 16}:{n.acceleration & 0xffff}:{n.acceleration >> 16}:{n.delay}:{n.user_data}')

    return f'NSMBeClip|{":".join(clip)}|'


def load_reggieclip(s: str):
    """
    Load a ReggieClip from a string.

    Return a 2-tuple: objects, sprites.
    - objects: dict {layer_num: [list of LevelObject]}
    - sprites: list of LevelSprite
    """
    if not (s.startswith('ReggieClip|') and s.endswith('|%')):
        raise ValueError('Invalid ReggieClip')

    objects = {}
    sprites = []

    for part in s.split('|')[1:-1]:
        numbers = [int(n) for n in part.split(':')]

        if numbers[0] == 0:  # Object
            objects.setdefault(numbers[3], []).append(level.LevelObject(
                tileset_id=numbers[1],
                type=numbers[2],
                # [3] is layer number (used above)
                x=numbers[4],
                y=numbers[5],
                width=numbers[6],
                height=numbers[7],
            ))

        elif numbers[0] == 1:  # Sprite
            sprites.append(level.LevelSprite(
                type=numbers[1],
                x=numbers[2],
                y=numbers[3],
                data_1=bytes(numbers[4:10]),
                layer=numbers[10],
            ))

    return objects, sprites


def save_reggieclip(objects, sprites, *, allow_unsafe=False, unsafe_list=None) -> str:
    """
    Save items back to a ReggieClip.

    If allow_unsafe is True (default False), sanity checks will be
    skipped, which might result in a clip that crashes the editor when
    pasted. If allow_unsafe is False, you can provide a list in the
    unsafe_list parameter, which will be populated with all items that
    were omitted from the clip for safety reasons.
    """
    if unsafe_list is None: unsafe_list = []

    clip = ['ReggieClip']

    for layer_num, layer in objects.items():
        for o in layer:
            # No need to verify the layer number -- Reggie handles it fine
            clip.append(f'0:{o.tileset_id}:{o.type}:{layer_num}:{o.x}:{o.y}:{o.width}:{o.height}')

    for s in sprites:
        if not allow_unsafe and s.type > _MAX_SPRITE_REGGIE:
            # Crashes some versions of Reggie
            unsafe_list.append(s)
            continue

        sdata = ':'.join(str(b) for b in _resize_bytes(s.data_1, 6))
        clip.append(f'1:{s.type}:{s.x}:{s.y}:{sdata}:{s.layer}')

    clip.append('%')
    return '|'.join(clip)


def load_coinkillerclip_raw(s: str):
    """
    Load a CoinKillerClip from a string.
    Positions and sizes are left in the raw "1/20 of a tile" units.

    Return value format is the same as load_coinkillerclip(); see that
    docstring for details.
    """
    if not s.startswith('CoinKillerClip|'):
        raise ValueError('Invalid CoinKillerClip')

    parts = s.split('|')

    full_width, full_height = (int(x) for x in parts[1].split(':'))

    objects = {}
    sprites = []
    entrances = []
    zones = []
    locations = []
    paths = []
    progress_paths = []

    for part in parts[2:]:
        item_type = int(part[0])

        if item_type <= 4:  # object, sprite, entrance, zone, location
            numbers = [int(n) for n in part.split(':')]

        if item_type == 0:  # Object
            objects.setdefault(numbers[2] + 1, []).append(level.LevelObject(
                tileset_id=numbers[1] >> 12,
                type=numbers[1] & 0xFFF,
                # [2] is layer number (used above)
                x=numbers[3],
                y=numbers[4],
                width=numbers[5],
                height=numbers[6],
            ))

        elif item_type == 1:  # Sprite
            # Don't forget to account for endian flipping!
            # CoinKiller reads the 10 bytes of spritedata_1 as u8, u8, u32, u32.
            byte_numbers_1 = [5, 6, 10, 9, 8, 7, 14, 13, 12, 11]
            sprites.append(level.LevelSprite(
                type=numbers[1],
                x=numbers[2],
                y=numbers[3],
                data_1=bytes([numbers[i] for i in byte_numbers_1]),
                layer=numbers[4],
                data_2=bytes(numbers[15:17]),
            ))

        elif item_type == 2:  # Entrance
            entrances.append(level.LevelEntrance(
                id=numbers[1],
                type=numbers[2],
                x=numbers[3],
                y=numbers[4],
                destination_area=numbers[5],
                destination_id=numbers[6],
                camera_x=numbers[7],
                camera_y=numbers[8],
                nsmb2_flags_unk_mask_1=bool(numbers[9] & 1),
                return_to_world_map=bool(numbers[9] & 0x10),
                nsmb2_flags_unk_mask_40=bool(numbers[9] & 0x40),
                non_enterable=bool(numbers[9] & 0x80),
                nsmb2_unk_14=numbers[10],
                nsmb2_unk_15=numbers[11],
            ))

        elif item_type == 3:  # Zone
            zones.append(level.LevelZone(
                x=numbers[1],
                y=numbers[2],
                width=numbers[3],
                height=numbers[4],
                id=numbers[5],
                progress_path_id=numbers[6],
                music=numbers[7],
                multiplayer_tracking=numbers[8],
                nsmb2_unk_08=numbers[9],
                bounds_id=numbers[10],
                bg_block_id=numbers[11],
            ))

        elif item_type == 4:  # Location
            locations.append(level.LevelLocation(
                id=numbers[1],
                x=numbers[2],
                y=numbers[3],
                width=numbers[4],
                height=numbers[5],
            ))

        elif item_type == 5:  # Path
            part_split = part.split(':')

            node_parts = part_split[3].split(';')

            nodes = []
            for node_part in node_parts:
                node_part_split = node_part.split(',')

                node_idx = int(node_part_split[0])
                node = level.LevelPathNode(
                    x=int(node_part_split[1]),
                    y=int(node_part_split[2]),
                    speed=float(node_part_split[3]),
                    acceleration=float(node_part_split[4]),
                    delay=int(node_part_split[5]),
                    rotation=int(node_part_split[6]),
                    user_data=int(node_part_split[7]),
                    next_path_id=int(node_part_split[8]),
                )
                nodes.append((node_idx, node))

            nodes.sort()

            path = level.LevelPath(
                id=int(part_split[1]),
                loop_flag=bool(int(part_split[2]) & 2),
                num_nodes=len(nodes),
            )

            paths.append((path, [n for idx, n in nodes]))

        elif item_type == 6:  # Progress path
            part_split = part.split(':')

            node_parts = part_split[3].split(';')

            nodes = []
            for node_part in node_parts:
                node_part_split = node_part.split(',')

                node_idx = int(node_part_split[0])
                node = level.LevelProgressPathNode(
                    x=int(node_part_split[1]),
                    y=int(node_part_split[2]),
                )
                nodes.append((node_idx, node))

            nodes.sort()

            ppath = level.LevelProgressPath(
                id=int(part_split[1]),
                alternate_path_flag=bool(int(part_split[2]) & 1),
                num_nodes=len(nodes),
            )

            progress_paths.append((ppath, [n for idx, n in nodes]))

    return (full_width, full_height), objects, sprites, entrances, zones, locations, paths, progress_paths


def load_coinkillerclip(s: str):
    """
    Load a CoinKillerClip from a string.

    Return an 8-tuple: size, objects, sprites, entrances, zones,
        locations, paths, progress paths.
    - size: (width, height) of the entire selection
    - objects: dict {layer_num: [list of LevelObject]}
    - sprites: list of LevelSprite
    - entrances: list of LevelEntrance
    - zones: list of LevelZone
    - locations: list of LevelLocation
    - paths: list of 2-tuples (path, nodes)
        - path: LevelPath
        - nodes: list of LevelPathNode
    - progress paths: list of 2-tuples (progress path, nodes)
        - progress path: LevelProgressPath
        - nodes: list of LevelProgressPathNode
    """
    (width, height), objects, sprites, entrances, zones, locations, paths, progress_paths = load_coinkillerclip_raw(s)

    def conv_20_to_16(v):
        return round(v * 16/20)

    width = conv_20_to_16(width)
    height = conv_20_to_16(height)

    for layer in objects.values():
        for obj in layer:
            # If there's at least one object anywhere in the selection,
            # the selection origin point will be snapped to tile
            # boundaries. So objects will always have positions that are
            # integer multiples of 20, so //= 20 is a safe operation
            obj.x //= 20
            obj.y //= 20
            obj.width //= 20
            obj.height //= 20

    for spr in sprites:
        spr.x = conv_20_to_16(spr.x)
        spr.y = conv_20_to_16(spr.y)

    for ent in entrances:
        ent.x = conv_20_to_16(ent.x)
        ent.y = conv_20_to_16(ent.y)

    for zone in zones:
        zone.x = conv_20_to_16(zone.x)
        zone.y = conv_20_to_16(zone.y)
        zone.width = conv_20_to_16(zone.width)
        zone.height = conv_20_to_16(zone.height)

    for loc in locations:
        loc.x = conv_20_to_16(loc.x)
        loc.y = conv_20_to_16(loc.y)
        loc.width = conv_20_to_16(loc.width)
        loc.height = conv_20_to_16(loc.height)

    for path, nodes in paths:
        for node in nodes:
            node.x = conv_20_to_16(node.x)
            node.y = conv_20_to_16(node.y)

    for path, nodes in progress_paths:
        for node in nodes:
            node.x = conv_20_to_16(node.x)
            node.y = conv_20_to_16(node.y)

    return (width, height), objects, sprites, entrances, zones, locations, paths, progress_paths


def save_coinkillerclip_raw(size, objects, sprites, entrances, zones, locations, paths, progress_paths, *, allow_unsafe=False, unsafe_list=None) -> str:
    """
    Save items to a CoinKillerClip.
    Positions and sizes are not scaled or transposed, and just left as-is.
    """
    if unsafe_list is None: unsafe_list = []

    clip = ['CoinKillerClip', f'{size[0]}:{size[1]}']

    for layer_num, layer in objects.items():
        for o in layer:
            if not allow_unsafe and layer_num not in {1, 2}:
                # CK crashes if the layer number is OOB
                unsafe_list.append(o)
                continue

            clip.append(f'0:{(o.tileset_id << 12) | o.type}:{layer_num - 1}:{o.x}:{o.y}:{o.width}:{o.height}')

    for s in sprites:
        # No need to verify that the sprite ID is in bounds -- CK handles it fine

        clip_parts = [f'1:{s.type}:{s.x}:{s.y}:{s.layer}']

        # Don't forget to account for endian flipping!
        # CoinKiller reads the 10 bytes of spritedata_1 as u8, u8, u32, u32.
        for idx in [0, 1, 5, 4, 3, 2, 9, 8, 7, 6]:
            clip_parts.append(str(_resize_bytes(s.data_1, 10)[idx]))

        for idx in [0, 1]:
            clip_parts.append(str(_resize_bytes(s.data_2, 2)[idx]))

        clip.append(':'.join(clip_parts))

    for e in entrances:
        flags = e.save(Game.NEW_SUPER_MARIO_BROS_2)[0x10]
        clip.append(f'2:{e.id}:{e.type}:{e.x}:{e.y}:{e.destination_area}:{e.destination_id}:{e.camera_x}:{e.camera_y}:{flags}:{e.nsmb2_unk_14}:{e.nsmb2_unk_15}')

    for z in zones:
        clip.append(f'3:{z.x}:{z.y}:{z.width}:{z.height}:{z.id}:{z.progress_path_id}:{z.music}:{z.multiplayer_tracking}:{z.nsmb2_unk_08}:{z.bounds_id}:{z.bg_block_id}')

    for L in locations:
        clip.append(f'4:{L.id}:{L.x}:{L.y}:{L.width}:{L.height}')

    for p, nodes in paths:
        nodes_clip = []

        for i, n in enumerate(nodes):
            nodes_clip.append(f'{i},{n.x},{n.y},{n.speed},{n.acceleration},{n.delay},{n.rotation},{n.user_data},{n.next_path_id}')

        clip.append(f'5:{p.id}:{2 if p.loop_flag else 0}:{";".join(nodes_clip)}')

    for p, nodes in progress_paths:
        nodes_clip = []

        for i, n in enumerate(nodes):
            nodes_clip.append(f'{i},{n.x},{n.y}')

        clip.append(f'6:{p.id}:{1 if p.alternate_path_flag else 0}:{";".join(nodes_clip)}')


    return '|'.join(clip)


def _calculate_bounding_box(objects, sprites, entrances, zones, locations, paths, progress_paths):
    """
    Helper function to calculate the bounding box around a set of items
    """
    # As a simplifying assumption, I treat everything that doesn't have
    # an explicit width/height as 16x16 (one tile)

    MAX_INT = 99999999999

    min_x = MAX_INT
    min_y = MAX_INT
    max_x = -MAX_INT
    max_y = -MAX_INT

    for layer in objects.values():
        for obj in layer:
            min_x = min(min_x, obj.x * 16)
            min_y = min(min_y, obj.y * 16)
            max_x = max(max_x, (obj.x + obj.width) * 16)
            max_y = max(max_y, (obj.y + obj.height) * 16)

    for spr in sprites:
        min_x = min(min_x, spr.x)
        min_y = min(min_y, spr.y)
        max_x = max(max_x, spr.x + 16)
        max_y = max(max_y, spr.y + 16)

    for ent in entrances:
        min_x = min(min_x, ent.x)
        min_y = min(min_y, ent.y)
        max_x = max(max_x, ent.x + 16)
        max_y = max(max_y, ent.y + 16)

    for zone in zones:
        min_x = min(min_x, zone.x)
        min_y = min(min_y, zone.y)
        max_x = max(max_x, zone.x + zone.width)
        max_y = max(max_y, zone.y + zone.height)

    for loc in locations:
        min_x = min(min_x, loc.x)
        min_y = min(min_y, loc.y)
        max_x = max(max_x, loc.x + loc.width)
        max_y = max(max_y, loc.y + loc.height)

    for path, nodes in paths:
        for node in nodes:
            min_x = min(min_x, node.x)
            min_y = min(min_y, node.y)
            max_x = max(max_x, node.x + 16)
            max_y = max(max_y, node.y + 16)

    for path, nodes in progress_paths:
        for node in nodes:
            min_x = min(min_x, node.x)
            min_y = min(min_y, node.y)
            max_x = max(max_x, node.x + 16)
            max_y = max(max_y, node.y + 16)

    if min_x == MAX_INT:
        # No items at all
        return 0, 0, 0, 0
    else:
        return min_x, min_y, max_x, max_y


def calculate_size_for_coinkillerclip(objects, sprites, entrances, zones, locations, paths, progress_paths):
    """
    Calculate a reasonable "size" tuple for save_coinkillerclip()
    """
    min_x, min_y, max_x, max_y = _calculate_bounding_box(objects, sprites, entrances, zones, locations, paths, progress_paths)
    return max_x - min_x, max_y - min_y


def save_coinkillerclip(size, objects, sprites, entrances, zones, locations, paths, progress_paths, *, allow_unsafe=False, unsafe_list=None) -> str:
    """
    Save items to a CoinKillerClip.
    You can set size to None, in which case it will be auto-calculated
    with calculate_size_for_coinkillerclip().

    If allow_unsafe is True (default False), sanity checks will be
    skipped, which might result in a clip that crashes the editor when
    pasted. If allow_unsafe is False, you can provide a list in the
    unsafe_list parameter, which will be populated with all items that
    were omitted from the clip for safety reasons.
    """
    # This is a little tricky, because we want to change the x/y/w/h
    # attributes before running save_coinkillerclip_raw(), and then
    # change them back afterwards.

    # Calculate width/height

    if size is None:
        size = calculate_size_for_coinkillerclip(objects, sprites, entrances, zones, locations, paths, progress_paths)

    width, height = size

    # Calculate origin

    min_x, min_y, max_x, max_y = _calculate_bounding_box(objects, sprites, entrances, zones, locations, paths, progress_paths)

    if objects:
        # Snap min_x and min_y to tile boundaries if there are any objects
        min_x -= min_x % 16
        min_y -= min_y % 16

    origin_x, origin_y = min_x, min_y

    # Convert all position/size values for width, height, and all items

    def conv_16_to_20(v):
        return round(v * 20/16)

    orig_attrs = {}

    width = conv_16_to_20(width)
    height = conv_16_to_20(height)

    for layer in objects.values():
        for obj in layer:
            orig_attrs[id(obj)] = {'x': obj.x, 'y': obj.y, 'width': obj.width, 'height': obj.height}
            obj.x = (obj.x - origin_x // 16) * 20
            obj.y = (obj.y - origin_y // 16) * 20
            obj.width *= 20
            obj.height *= 20

    for spr in sprites:
        orig_attrs[id(spr)] = {'x': spr.x, 'y': spr.y}
        spr.x = conv_16_to_20(spr.x - origin_x)
        spr.y = conv_16_to_20(spr.y - origin_y)

    for ent in entrances:
        orig_attrs[id(ent)] = {'x': ent.x, 'y': ent.y}
        ent.x = conv_16_to_20(ent.x - origin_x)
        ent.y = conv_16_to_20(ent.y - origin_y)

    for zone in zones:
        orig_attrs[id(zone)] = {'x': zone.x, 'y': zone.y, 'width': zone.width, 'height': zone.height}
        zone.x = conv_16_to_20(zone.x - origin_x)
        zone.y = conv_16_to_20(zone.y - origin_y)
        zone.width = conv_16_to_20(zone.width)
        zone.height = conv_16_to_20(zone.height)

    for loc in locations:
        orig_attrs[id(loc)] = {'x': loc.x, 'y': loc.y, 'width': loc.width, 'height': loc.height}
        loc.x = conv_16_to_20(loc.x - origin_x)
        loc.y = conv_16_to_20(loc.y - origin_y)
        loc.width = conv_16_to_20(loc.width)
        loc.height = conv_16_to_20(loc.height)

    for path, nodes in paths:
        for node in nodes:
            orig_attrs[id(node)] = {'x': node.x, 'y': node.y}
            node.x = conv_16_to_20(node.x - origin_x)
            node.y = conv_16_to_20(node.y - origin_y)

    for path, nodes in progress_paths:
        for node in nodes:
            orig_attrs[id(node)] = {'x': node.x, 'y': node.y}
            node.x = conv_16_to_20(node.x - origin_x)
            node.y = conv_16_to_20(node.y - origin_y)

    try:
        s = save_coinkillerclip_raw(
            (width, height), objects, sprites, entrances, zones, locations, paths, progress_paths, allow_unsafe=allow_unsafe, unsafe_list=unsafe_list)

    finally:
        # Restore all modified attributes back to their original values

        def restore_attrs(item):
            for name, value in orig_attrs[id(item)].items():
                setattr(item, name, value)

        for layer in objects.values():
            for obj in layer:
                restore_attrs(obj)

        for spr in sprites:
            restore_attrs(spr)

        for ent in entrances:
            restore_attrs(ent)

        for zone in zones:
            restore_attrs(zone)

        for loc in locations:
            restore_attrs(loc)

        for path, nodes in paths:
            for node in nodes:
                restore_attrs(node)

        for path, nodes in progress_paths:
            for node in nodes:
                restore_attrs(node)

    return s


def load_miyamotoclip(s: str):
    """
    Load a MiyamotoClip from a string.

    Return a 2-tuple: objects, sprites.
    - objects: dict {layer_num: [list of LevelObject]}
    - sprites: list of LevelSprite
    """
    if not (s.startswith('MiyamotoClip|') and s.endswith('|%')):
        raise ValueError('Invalid MiyamotoClip')

    objects = {}
    sprites = []

    for part in s.split('|')[1:-1]:
        numbers = [int(n) for n in part.split(':')]

        if numbers[0] == 0:  # Object
            objects.setdefault(numbers[3], []).append(level.LevelObject(
                tileset_id=numbers[1],
                type=numbers[2],
                # [3] is layer number (used above)
                x=numbers[4],
                y=numbers[5],
                width=numbers[6],
                height=numbers[7],
                contents=numbers[8],
            ))

        elif numbers[0] == 1:  # Sprite
            sprites.append(level.LevelSprite(
                type=numbers[1],
                x=numbers[2],
                y=numbers[3],
                data_1=bytes(numbers[4:14]),
                data_2=bytes(numbers[14:16]),
                layer=numbers[16],
                initial_state=numbers[17],
            ))

    return objects, sprites


def save_miyamotoclip(objects, sprites, *, allow_unsafe=False, unsafe_list=None) -> str:
    """
    Save items back to a MiyamotoClip.

    If allow_unsafe is True (default False), sanity checks will be
    skipped, which might result in a clip that crashes the editor when
    pasted. If allow_unsafe is False, you can provide a list in the
    unsafe_list parameter, which will be populated with all items that
    were omitted from the clip for safety reasons.
    """
    if unsafe_list is None: unsafe_list = []

    clip = ['MiyamotoClip']

    for layer_num, layer in objects.items():
        for o in layer:
            # No need to verify the layer number -- Miyamoto handles it fine
            clip.append(f'0:{o.tileset_id}:{o.type}:{layer_num}:{o.x}:{o.y}:{o.width}:{o.height}:{o.contents}')

    for s in sprites:
        # No need to verify the sprite ID -- Miyamoto handles it fine

        clip_parts = [f'1:{s.type}:{s.x}:{s.y}']

        clip_parts.extend(str(b) for b in (_resize_bytes(s.data_1, 10) + _resize_bytes(s.data_2, 2)))
        clip_parts.append(f'{s.layer}:{s.initial_state}')
        clip.append(':'.join(clip_parts))

    clip.append('%')
    return '|'.join(clip)

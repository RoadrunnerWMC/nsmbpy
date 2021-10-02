"""
The real implementation of nsmbpy2.level
"""
import struct
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple, Union

from . import Game
from . import base_struct
from . import _abstract_json_versioned_api
from . import u8


PathLike = Union[str, 'pathlib.Path']


class PositionMixin:
    """
    Mixin that adds a position property to a class with x and y attributes
    """
    @property
    def position(self) -> Tuple[int, int]:
        return (self.x, self.y)
    @position.setter
    def position(self, value: Tuple[int, int]) -> None:
        (self.x, self.y) = value


class SizeMixin:
    """
    Mixin that adds a size property to a class with width and height attributes
    """
    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)
    @size.setter
    def size(self, value: Tuple[int, int]) -> None:
        (self.width, self.height) = value


class DimensionsMixin:
    """
    Mixin that adds a dimensions properties to a class with x, y, width
    and height attributes
    It's recommended to also add PositionMixin and SizeMixin, too
    """
    @property
    def dimensions(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)
    @dimensions.setter
    def dimensions(self, value: Tuple[int, int, int, int]) -> None:
        (self.x, self.y, self.width, self.height) = value


class EntranceMixin:
    """
    Mixin for entrances, to add an "enterable" property that tracks the
    opposite of non_enterable
    """
    @property
    def enterable(self) -> bool:
        return not self.non_enterable
    @enterable.setter
    def enterable(self, value: bool) -> None:
        self.non_enterable = not value


MixinsPerClassName = {
    'BackgroundLayer': [PositionMixin],
    'Entrance': [PositionMixin, EntranceMixin],
    'Sprite': [PositionMixin],
    'Zone': [PositionMixin, SizeMixin, DimensionsMixin],
    'Location': [PositionMixin, SizeMixin, DimensionsMixin],
    'PathNode': [PositionMixin],
    'Object': [PositionMixin, SizeMixin, DimensionsMixin],
}


class CourseTilesetNamesProxy:
    """
    A class that provides a list-like interface for accessing/modifying
    tileset names
    """
    _course: 'Course'
    def __init__(self, course):
        self._course = course

    def _get(self, id: int) -> Optional[str]:
        """
        Get a tileset name
        """
        block = self._course.blocks[0]
        if id == 0:
            name = block.tileset_0
        elif id == 1:
            name = block.tileset_1
        elif id == 2:
            name = block.tileset_2
        elif id == 3:
            name = block.tileset_3
        else:
            raise IndexError
        if name:
            return name
        else:
            return None

    def _set(self, id: int, value: str) -> None:
        """
        Set a tileset name
        """
        if value is None:
            value = ''
        block = self._course.blocks[0]
        if id == 0:
            block.tileset_0 = value
        elif id == 1:
            block.tileset_1 = value
        elif id == 2:
            block.tileset_2 = value
        elif id == 3:
            block.tileset_3 = value
        else:
            raise IndexError

    def __getitem__(self, key) -> str:
        if isinstance(key, slice):
            retval = []
            for idx in range(*key.indices(4)):
                retval.append(self._get(idx))
            return retval
        elif isinstance(key, int):
            if key < 0:
                key += 4
            return self._get(key)

        raise ValueError

    def __setitem__(self, key, value: str) -> None:
        if isinstance(key, slice):
            for idx, value_there in zip(range(*key.indices(4)), value):
                self._set(idx, value_there)
        elif isinstance(key, int):
            if key < 0:
                key += 4
            self._set(key)

        raise ValueError

    def __str__(self):
        strs_list = []
        for name in self:
            if name is None:
                strs_list.append('None')
            else:
                strs_list.append(f'"{name}"')
        names_str = ', '.join(strs_list)
        return f'<tileset names: {names_str}>'

    def __repr__(self):
        strs_list = []
        for name in self:
            if name is None:
                strs_list.append('None')
            else:
                strs_list.append(f"'{name}'")
        names_str = ', '.join(strs_list)
        return f'{type(self).__name__}({names_str})'


def load_block_using_json_definition(api: 'LevelAPI', block_def: dict, data: bytes) -> Any:
    """
    Given a LevelAPI and a block definition from the json, load block data
    """

    block_struct_type = api.structs[block_def['struct']]
    block_item_size = block_struct_type.raw_data_length

    terminator = bytes.fromhex(block_def.get('terminator', ''))

    if block_def.get('single', False):
        if terminator:
            data = data[:-len(terminator)]
        return block_struct_type(data)

    return base_struct.load_struct_array(data, block_struct_type, terminator=terminator)


def save_block_using_json_definition(api: 'LevelAPI', block_def: dict, contents: Any) -> bytes:
    """
    Given a LevelAPI and a block definition from the json, save block data
    """

    if block_def.get('single', False):
        return bytes(contents)

    terminator = bytes.fromhex(block_def.get('terminator', ''))
    return base_struct.save_struct_array(contents, terminator=terminator)


class Course:
    """
    Represents course{X}.bin from a level file.
    """
    _api: 'LevelAPI'
    blocks: List[List[base_struct.BaseStruct]]
    metadata: bytes

    _block_name_to_index: Dict[str, int]

    def __init__(self):
        """
        Create a new course
        """
        self.blocks = []
        self._block_name_to_index = {}
        for idx, block_def in enumerate(self._api.api_definition['course_blocks']):
            if block_def.get('single', False):
                self.blocks.append(self._api.structs[block_def['struct']]())
            else:
                self.blocks.append([])
            if 'name' in block_def:
                self._block_name_to_index[block_def['name']] = idx

        self.metadata = b''


    def __getattr__(self, name: int) -> Any:
        """
        Attribute resolution order:
        - (actual attributes)
        - block names (e.g. self.sprites)
        - attributes on self.settings
        """
        idx = self._block_name_to_index.get(name)
        if idx is not None:
            return self.blocks[idx]
        return getattr(self.settings, name)


    @classmethod
    def load(cls, data: bytes, *,
            num_blocks:int=None,
            custom_block_loaders:Dict[int, Callable[[bytes], Any]]=None) -> 'Course':
        """
        Load from course file data
        """
        self = cls()

        if custom_block_loaders is None:
            custom_block_loaders = {}

        course_blocks_definition = self._api.api_definition['course_blocks']

        if num_blocks is None:
            num_blocks = len(course_blocks_definition)

        if self._api.api_definition['default_endianness'] == 'big':
            header_pair_struct = struct.Struct('>II')
        else:
            header_pair_struct = struct.Struct('<II')

        min_block_offset = 9999999999999999

        self.blocks.clear()
        for block_num in range(num_blocks):

            start, size = header_pair_struct.unpack_from(data, block_num * 8)
            min_block_offset = min(min_block_offset, start)

            block_data = data[start : start + size]

            if block_num in custom_block_loaders:
                block_contents = custom_block_loaders[block_num](block_data)

            else:
                if block_num >= len(course_blocks_definition):
                    raise ValueError(
                        f"Trying to load block {block_num}, which isn't in the original game,"
                        ' but no custom block loader was provided for it')

                block_contents = load_block_using_json_definition(
                    self._api, course_blocks_definition[block_num], block_data)

            self.blocks.append(block_contents)

        header_end = len(self.blocks) * 8
        if min_block_offset > header_end:
            self.metadata = data[header_end : min_block_offset]

        return self


    def save(self, *,
            auto_prepare=True,
            custom_block_savers:Dict[int, Callable[[Any], bytes]]=None) -> bytes:
        """
        Save to course file data.
        In most cases, you'll want to leave auto_prepare set to True,
        which adds a call to auto_prepare_for_saving(). You can disable
        it if you know what you're doing.
        """
        if auto_prepare:
            self.auto_prepare_for_saving()

        if custom_block_savers is None:
            custom_block_savers = {}

        course_blocks_definition = self._api.api_definition['course_blocks']

        if self._api.api_definition['default_endianness'] == 'big':
            header_pair_struct = struct.Struct('>II')
        else:
            header_pair_struct = struct.Struct('<II')

        data = bytearray(len(self.blocks) * 8)

        data.extend(self.metadata)
        while len(data) % 4: data.append(0)

        for block_num, block_contents in enumerate(self.blocks):

            if block_num in custom_block_savers:
                block_data = custom_block_savers[block_num](block_contents)
            else:
                if block_num >= len(course_blocks_definition):
                    raise ValueError(
                        f"Trying to save block {block_num}, which isn't in the original game,"
                        ' but no custom block saver was provided for it')

                block_data = save_block_using_json_definition(
                    self._api, course_blocks_definition[block_num], block_contents)

            header_pair_struct.pack_into(data, block_num * 8, len(data), len(block_data))

            data.extend(block_data)
            while len(data) % 4: data.append(0)

        return bytes(data)


    def auto_prepare_for_saving(self, **kwargs) -> None:
        """
        Make some automatic adjustments required for the course to not
        crash the game. Each adjustment can be individually disabled if
        you want.
        """
        # In cases where we're trying to update zone IDs but self.zones
        # is empty, we set the zone IDs to 0 instead. Raising an
        # exception would just end up being an annoying edge-case crash
        # in the application.
        if kwargs.get('update_sprite_zone_ids', True):
            if self.zones:
                for s in self.sprites:
                    x, y = s.x, s.y

                    if self._api.game == Game.NEW_SUPER_MARIO_BROS:
                        # NSMB measures sprite positions in tiles instead of
                        # 16ths-of-a-tile like the other games.
                        # So we have to multiply by 16 here.
                        x, y = x * 16, y * 16

                    s.zone_id = self.map_position_to_zone(x, y).id

            else:
                for s in self.sprites:
                    s.zone_id = 0


        if kwargs.get('update_entrance_zone_ids', True):
            if self.zones:
                for e in self.entrances:
                    e.zone_id = self.map_position_to_zone(e.x, e.y).id

            else:
                for e in self.entrances:
                    e.zone_id = 0


    def map_position_to_zone(self, x: int, y: int) -> Optional['Zone']:
        """
        Return the Zone containing or nearest the specified position
        (measured in zone coordinates -- 16 = one tile).
        If the position is within multiple zones, return the first one
        in the list.
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


    @staticmethod
    def _get_by_id(items_list: List[Any], id: int) -> Optional[Any]:
        """
        Given a list of things that have an "id" attribute, return the
        one with the given id
        """
        for item in items_list:
            if item.id == id:
                return item

    def get_zone_bounds_by_id(self, id: int) -> Optional['ZoneBounds']:
        """
        Get a zone bounds struct by ID
        """
        return self._get_by_id(self.zone_bounds, id)

    def get_entrance_by_id(self, id: int) -> Optional['Entrance']:
        """
        Get an entrance by ID
        """
        return self._get_by_id(self.entrances, id)

    def get_zone_by_id(self, id: int) -> Optional['Zone']:
        """
        Get a zone by ID
        """
        return self._get_by_id(self.zones, id)

    def get_location_by_id(self, id: int) -> Optional['Location']:
        """
        Get a location by ID
        """
        return self._get_by_id(self.locations, id)

    def get_path_by_id(self, id: int) -> Optional['Path']:
        """
        Get a path by ID
        """
        return self._get_by_id(self.paths, id)


class PostNSMBDSCourse(Course):
    """
    Course subclass that adds stuff that applies to all games after NSMBDS
    """

    def __init__(self):
        super().__init__()
        self._tileset_names = CourseTilesetNamesProxy(self)

    @property
    def tileset_names(self) -> CourseTilesetNamesProxy:
        return self._tileset_names
    @tileset_names.setter
    def tileset_names(self, value: List[str]) -> None:
        if len(value) != 4:
            raise ValueError
        self._tileset_names[:4] = value


    def auto_prepare_for_saving(self, **kwargs) -> None:
        """
        Make some automatic adjustments required for the course to not
        crash the game. Each adjustment can be individually disabled if
        you want.
        """
        super().auto_prepare_for_saving(**kwargs)

        if kwargs.get('sort_sprites_by_zone', True):
            # Note: this HAS to happen after the sprite zone IDs are
            # updated
            # Note 2: NSMBDS doesn't require sprites to be sorted in the
            # level file -- it does its own bubble sort (!) upon area
            # load. With that said, sorting ahead of time anyway isn't
            # harmful, and might improve load times slightly (because
            # bubble sort), so, might as well.
            self.sprites.sort(key=lambda s: s.zone_id)

        if kwargs.get('update_used_sprite_types', True):
            self.set_used_sprite_type_values(set(s.type for s in self.sprites))


    def get_used_sprite_type_values(self) -> FrozenSet[int]:
        """
        Return a frozenset of values from self.used_sprite_types
        """
        return frozenset(ust.value for ust in self.used_sprite_types)


    def set_used_sprite_type_values(self, types: FrozenSet[int]) -> None:
        """
        Replace self.used_sprite_types with new entries reflecting the
        provided set of sprite types
        """
        self.used_sprite_types.clear()
        for t in sorted(types):
            self.used_sprite_types.append(self._api.structs['UsedSpriteType'](value=t))


class NSMBWCourse(PostNSMBDSCourse):
    """
    Course subclass that adds stuff specific to NSMBW
    """

    def get_background_a_by_id(self, id: int) -> Optional['BackgroundLayer']:
        """
        Get a bgA by ID
        """
        return self._get_by_id(self.backgrounds_a, id)

    def get_background_b_by_id(self, id: int) -> Optional['BackgroundLayer']:
        """
        Get a bgB by ID
        """
        return self._get_by_id(self.backgrounds_b, id)


class Area:
    """
    An area (course + layers)
    """
    _api: 'LevelAPI'
    course: Course
    layers: Dict[str, List['Object']]
    bgdat_terminator: bytes

    def __init__(self, course=None, layers=None, *, bgdat_terminator:bytes=None):
        self.course = course
        self.layers = layers if layers else {}

        if bgdat_terminator is None:
            self.bgdat_terminator = bytes.fromhex(self._api.api_definition['bgdat_terminator'])
        else:
            self.bgdat_terminator = bgdat_terminator


    def __getattr__(self, name: str) -> Any:
        """
        Attribute resolution order:
        - (actual attributes)
        - attributes on self.course
        """
        return getattr(self.course, name)


    @classmethod
    def load(cls, course_data: bytes, layers_data: Dict[int, bytes], *,
            bgdat_loader:Callable[[bytes], List['Object']]=None,
            course_load_kwargs:Dict[str, Any]=None) -> 'Area':
        """
        Load from course and bgdat file data
        """
        self = cls()

        if course_load_kwargs is None:
            course_load_kwargs = {}

        self.course = self._api.Course.load(course_data, **course_load_kwargs)

        if bgdat_loader is None:
            def bgdat_loader(data: bytes) -> List['Object']:
                return base_struct.load_struct_array(data, self._api.structs['Object'], terminator=self.bgdat_terminator)

        for layer_id, layer_data in layers_data.items():
            self.layers[layer_id] = bgdat_loader(layer_data)

        return self


    def save(self, *,
            bgdat_saver:Callable[[List['Object']], bytes]=None,
            course_save_kwargs:Dict[str, Any]=None) -> (bytes, Dict[int, bytes]):
        """
        Save course and layers back to file data.
        Skips saving empty layers, since you shouldn't save any files
        for those layers at all
        """

        if course_save_kwargs is None:
            course_save_kwargs = {}

        course_data = self.course.save(**course_save_kwargs)

        if bgdat_saver is None:
            def bgdat_saver(layer: List['Object']) -> bytes:
                return base_struct.save_struct_array(layer, terminator=self.bgdat_terminator)

        layer_datas = {}
        for layer_id, layer in self.layers.items():
            if layer:
                layer_datas[layer_id] = bgdat_saver(layer)

        return course_data, layer_datas


class Level:
    """
    A full level
    """
    _api: 'LevelAPI'
    areas: List[Area]

    def __init__(self, areas=None):
        self.areas = areas if areas else []


    @classmethod
    def load_from_file(cls, path: PathLike, *,
            area_load_kwargs:Dict[str, Any]=None) -> 'Level':
        """
        Load the level from a path on the filesystem
        """
        with open(path, 'rb') as f:
            return cls.load(f.read(), area_load_kwargs=area_load_kwargs)


    @classmethod
    def load(cls, data: bytes, *,
            area_load_kwargs:Dict[str, Any]=None) -> 'Level':
        """
        Load the level from a bytes object
        """
        raise NotImplementedError


    def save_to_file(self, path: PathLike, *,
            area_save_kwargs:Dict[str, Any]=None) -> None:
        """
        Save the level to a path on the filesystem
        """
        data = self.save(area_save_kwargs=area_save_kwargs)
        with open(path, 'wb') as f:
            f.write(data)


    def save(self, *,
            area_save_kwargs:Dict[str, Any]=None) -> bytes:
        """
        Save the level to a bytes object
        """
        raise NotImplementedError


class NSMBWLevel(Level):
    """
    U8 level archive for NSMBW
    """

    @classmethod
    def load(cls, data: bytes, *,
            area_load_kwargs:Dict[str, Any]=None) -> 'Level':
        """
        load() implementation for NSMBW U8 archives
        """
        self = cls()

        if area_load_kwargs is None:
            area_load_kwargs = {}

        arc_course = u8.load(data)['course']
        for i in range(4):
            if f'course{i+1}.bin' not in arc_course:
                break

            layers = {}
            for j in range(3):
                fn = f'course{i+1}_bgdatL{j}.bin'
                if fn in arc_course:
                    layers[j] = arc_course[fn]

            self.areas.append(self._api.Area.load(arc_course[f'course{i+1}.bin'], layers, **area_load_kwargs))

        return self


    def save(self, *,
            pad_to_length:int=None,
            error_if_longer_than_pad_length:bool=True,
            area_save_kwargs:Dict[str, Any]=None) -> bytes:
        """
        save() implementation for NSMBW U8 archives
        """

        if area_save_kwargs is None:
            area_save_kwargs = {}

        arc_course = {}
        for i, area in enumerate(self.areas):
            course, layers = area.save(**area_save_kwargs)

            arc_course[f'course{i+1}.bin'] = course
            for j, layer in layers.items():
                arc_course[f'course{i+1}_bgdatL{j}.bin'] = layer

        arc_data = u8.save({'course': arc_course})

        if pad_to_length is not None:
            if len(arc_data) <= pad_to_length:
                arc_data += b'\0' * (pad_to_length - len(arc_data))
            elif error_if_longer_than_pad_length:
                raise ValueError(
                    f'Requested to pad NSMBW level to 0x{pad_to_length:x}, but the unpadded level data is 0x{len(arc_data):x} long')

        return arc_data



class LevelAPI(_abstract_json_versioned_api.VersionedAPI):
    """
    Class representing the entire API -- a set of classes you can use to
    represent a level
    """
    game: Game

    Level: type
    Area: type
    Course: type

    @classmethod
    def build(cls, game: Game, api_version: str) -> 'LevelAPI':
        """
        Create a level API corresponding to a Game and a version string
        """
        game_name = {
            Game.NEW_SUPER_MARIO_BROS: 'NSMB',
            Game.NEW_SUPER_MARIO_BROS_WII: 'NSMBW',
            Game.NEW_SUPER_MARIO_BROS_2: 'NSMB2',
            Game.NEW_SUPER_MARIO_BROS_U: 'NSMBU',
            # NSLU has the same level format as NSMBU, so they share JSONs
            Game.NEW_SUPER_LUIGI_U: 'NSMBU',
            Game.NEW_SUPER_MARIO_BROS_U_DELUXE: 'NSMBUDX',
        }.get(game)
        if game is None:
            raise ValueError(f'Unsupported game: {game}')

        self = super().build(f'{game_name}_{api_version}')
        self.game = game

        course_superclass, level_superclass = {
            'NSMB': (Course, Level),
            'NSMBW': (NSMBWCourse, NSMBWLevel),
            'NSMB2': (Course, Level),
            'NSMBU': (Course, Level),
            'NSMBUDX': (Course, Level),
        }[game_name]

        self.Course = type('Course', (course_superclass,), {'_api': self})
        self.Area = type('Area', (Area,), {'_api': self})
        self.Level = type('Level', (level_superclass,), {'_api': self})

        return self


    def _get_mixins_for_struct(self, name: str) -> List[type]:
        """
        Given a struct name, return any mixin classes that should be
        applied to it when it's being created
        """
        if name in MixinsPerClassName:
            return MixinsPerClassName[name]
        else:
            return super()._get_mixins_for_struct(name)

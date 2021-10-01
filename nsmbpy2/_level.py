"""
The real implementation of nsmbpy2.level
"""

from typing import List, Tuple

from . import Game
from . import abstract_json_versioned_api



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


MixinsPerClassName = {
    'Zone': [PositionMixin, SizeMixin, DimensionsMixin],
}



class LevelAPI(abstract_json_versioned_api.VersionedAPIWithStructs):
    """
    Class representing the entire API -- a set of classes you can use to
    represent a level
    """
    game: Game

    # Level: type
    # Area: type
    # Course: type

    # LevelItem: type
    # AreaSettings: type
    # ZoneBounds: type
    # BackgroundLayer: type
    # DSTilesetInfo: type
    # DistantViewBackground: type
    # Entrance: type
    # Sprite: type
    # UsedSpriteID: type
    # Zone: type
    # Location: type
    # CameraProfile: type
    # Path: type
    # PathNode: type
    # ProgressPath: type
    # ProgressPathNode: type

    @classmethod
    def build(cls, api_version: str, game: Game) -> 'LevelAPI':
        self = super().build(api_version)
        self.game = game
        return self

    def get_mixins_for_struct(self, name: str) -> List[type]:
        if name in MixinsPerClassName:
            return MixinsPerClassName[name]
        else:
            return super().get_mixins_for_struct(name)

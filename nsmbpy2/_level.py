import json
from pathlib import Path
from typing import List

from . import Game
from . import base_struct
from . import base_struct_from_json


DATA_FOLDER = Path(__file__).parent / 'data'
API_VERSIONS_WHITELIST_FP = DATA_FOLDER / 'api_versions_whitelist.txt'


def load_api_versions_whitelist() -> List[str]:
    """
    Load the api_versions_whitelist.txt file
    """
    whitelist = []
    with API_VERSIONS_WHITELIST_FP.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                whitelist.append(line)
    return whitelist

api_versions_whitelist = load_api_versions_whitelist()

def load_api_definition(name: str) -> dict:
    """
    Load the JSON API definition with the given name
    """
    global api_versions_whitelist

    if name not in api_versions_whitelist:
        raise ValueError(f'Unrecognized API version: "{name}"')

    fp = DATA_FOLDER / f'api_{name}.json'
    with fp.open('r', encoding='utf-8') as f:
        return json.load(f)


class Api:
    """
    Class representing the entire API -- a set of classes you can use to
    represent a level
    """
    fields_api_version: str
    game: Game

    Level: type
    Area: type
    Course: type

    LevelItem: type
    AreaSettings: type
    ZoneBounds: type
    BackgroundLayer: type
    DSTilesetInfo: type
    DistantViewBackground: type
    Entrance: type
    Sprite: type
    UsedSpriteID: type
    Zone: type
    Location: type
    CameraProfile: type
    Path: type
    PathNode: type
    ProgressPath: type
    ProgressPathNode: type

    @classmethod
    def build(cls, fields_api_version: str, game: Game) -> 'Api':
        self = cls()

        self.fields_api_version = fields_api_version
        self.fields_api = load_api_definition(fields_api_version)
        self.game = game

        for struct_name, struct_def in self.fields_api['structs'].items():
            new_cls = base_struct_from_json.create_struct_class(struct_name, struct_def)
            setattr(self, struct_name, new_cls)

        return self

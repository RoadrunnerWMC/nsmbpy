"""
This file implements a system for defining an "API" containing various
structs loaded from a JSON file keyed by a version ID.
"""

import json
from pathlib import Path
from typing import List, Dict

from . import base_struct_from_json


APIVersion = str


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


def load_api_definition(name: APIVersion) -> dict:
    """
    Load the JSON API definition with the given name
    """
    global api_versions_whitelist

    if name not in api_versions_whitelist:
        raise ValueError(f'Unrecognized API version: "{name}"')

    fp = DATA_FOLDER / f'api_{name}.json'
    with fp.open('r', encoding='utf-8') as f:
        return json.load(f)


class VersionedAPI:
    """
    Class representing an API (set of classes) instantiated from a JSON
    file indicated by a version string
    """
    api_version: APIVersion

    @classmethod
    def build(cls, api_version: APIVersion) -> 'VersionedAPI':
        self = cls()
        self.api_version = api_version

        api_definition = load_api_definition(api_version)
        self.process_api_definition(api_definition)

        return self

    def process_api_definition(self, definition: dict) -> None:
        pass


class VersionedAPIWithStructs(VersionedAPI):
    """
    VersionedAPI including a dict of BaseStruct subclasses
    """
    structs: Dict[str, type]

    def get_mixins_for_struct(self, name: str) -> List[type]:
        return []

    def process_api_definition(self, definition: dict) -> None:
        self.structs = {}
        for struct_name, struct_def in definition['structs'].items():
            mixins = self.get_mixins_for_struct(struct_name)
            new_cls = base_struct_from_json.create_struct_class(struct_name, struct_def, mixins=mixins)
            self.structs[struct_name] = new_cls

    def __getattr__(self, key: str) -> object:
        if key in self.structs:
            return self.structs[key]
        raise AttributeError

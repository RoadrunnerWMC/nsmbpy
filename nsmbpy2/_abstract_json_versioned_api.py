"""
This file implements a system for defining an "API" containing various
structs loaded from a JSON file keyed by a version ID.
"""
import enum
import json
from pathlib import Path
from typing import Any, List, Dict, Optional

from . import _base_struct_from_json


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
    Load the JSON API definition file with the given name, and return
    its contents
    """
    global api_versions_whitelist

    if name not in api_versions_whitelist:
        raise ValueError(f'Unrecognized API version: "{name}"')

    fp = DATA_FOLDER / f'api_{name}.json'
    with fp.open('r', encoding='utf-8') as f:
        return json.load(f)


class IntEnumWithSemanticValues(enum.IntEnum):
    """
    IntEnum subclass that adds a ".semantic_value" property (like the
    existing .name and .value attributes) that returns entries from a
    monkeypatched _semantic_values dict
    """
    _semantic_values: Dict[str, Any]

    @property
    def semantic_value(self) -> Optional[Any]:
        """
        Get the semantic value of this enum member, or None if none is
        available
        """
        return self._semantic_values.get(self.name)


class VersionedAPI:
    """
    Class representing an API (set of classes) instantiated from a JSON
    file indicated by a version string
    """
    api_definition: dict
    api_version: APIVersion

    enums: Dict[str, type]
    structs: Dict[str, type]

    @classmethod
    def build(cls, api_version: APIVersion) -> 'VersionedAPI':
        """
        Create a new VersionedAPI object
        """
        self = cls()
        self.api_version = api_version
        self.enums = {}
        self.structs = {}

        self.api_definition = load_api_definition(api_version)
        self._process_api_definition(self.api_definition)

        return self

    def _process_api_definition(self, definition: dict) -> None:
        """
        Initialize stuff based on an API definition dict.
        This can be overridden (please call the super() version too) in
        subclasses that add additional stuff to the API dict.
        """
        for enum_name, enum_def in definition.get('enums', {}).items():
            members_list = []
            semantic_values = {}
            for member_name, member in enum_def.items():
                if isinstance(member, dict):
                    if 'semantic_value' in member:
                        semantic_values[member_name] = member['semantic_value']
                    member_value = member['struct_value']
                else:
                    member_value = member
                members_list.append((member_name, member_value))
            en = IntEnumWithSemanticValues(enum_name, members_list)
            en._semantic_values = semantic_values
            self.enums[enum_name] = en

        for struct_name, struct_def in definition.get('structs', {}).items():
            mixins = self._get_mixins_for_struct(struct_name)
            new_cls = _base_struct_from_json.create_struct_class(
                struct_name, struct_def,
                mixins=mixins, enums=self.enums,
                default_endianness=definition.get('default_endianness'))
            self.structs[struct_name] = new_cls

    def _get_mixins_for_struct(self, name: str) -> List[type]:
        """
        Given a struct name, return any mixin classes that should be
        applied to it when it's being created
        """
        return []

    def __getattr__(self, key: str) -> object:
        """
        Attribute resolution order:
        - (actual attributes)
        - struct names
        - enum names
        """
        if key in self.structs:
            return self.structs[key]
        if key in self.enums:
            return self.enums[key]
        raise AttributeError(key)

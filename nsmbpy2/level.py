"""
A module for loading and saving level data.

This module only defines one function, get(version, game), which returns
an API object that provides access to the remainder of the API.
The API object you get depends on the API version string you request,
for backward compatibility.
"""

from . import Game
from ._level import LevelAPI


def get(api_version: str, game: Game) -> LevelAPI:
    return LevelAPI.build(api_version, game)

from . import Game
from ._level import Api


def get(fields_api_version: str, game: Game) -> Api:
    return Api.build(fields_api_version, game)

from __future__ import annotations

from pydantic import BaseModel


class Player(BaseModel):
    id: str
    summonerName: str = ""
    firstName: str = ""
    lastName: str = ""
    image: str = ""
    role: str = ""


class HomeLeague(BaseModel):
    name: str = ""
    region: str = ""


class Team(BaseModel):
    id: str
    slug: str
    name: str
    code: str
    image: str = ""
    alternativeImage: str | None = None
    homeLeague: HomeLeague | None = None
    players: list[Player] = []

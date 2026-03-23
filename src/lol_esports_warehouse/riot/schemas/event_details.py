from __future__ import annotations

from pydantic import BaseModel


class Vod(BaseModel):
    parameter: str
    locale: str = ""
    provider: str = ""
    offset: int = 0


class Stream(BaseModel):
    parameter: str
    locale: str = ""
    provider: str = ""
    offset: int = 0


class GameTeam(BaseModel):
    id: str
    side: str | None = None


class Game(BaseModel):
    id: str
    state: str
    number: int
    vods: list[Vod] = []
    teams: list[GameTeam] = []


class EventDetailTeamResult(BaseModel):
    gameWins: int = 0


class EventDetailTeam(BaseModel):
    id: str
    code: str
    image: str
    name: str
    result: EventDetailTeamResult | None = None


class EventDetailStrategy(BaseModel):
    count: int


class EventDetailMatch(BaseModel):
    teams: list[EventDetailTeam]
    games: list[Game]
    strategy: EventDetailStrategy


class EventDetailLeague(BaseModel):
    name: str
    slug: str
    id: str
    image: str


class EventDetail(BaseModel):
    id: str
    type: str
    league: EventDetailLeague
    match: EventDetailMatch
    streams: list[Stream] = []

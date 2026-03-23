from __future__ import annotations

from pydantic import BaseModel


class TeamResult(BaseModel):
    gameWins: int = 0
    outcome: str | None = None


class TeamRecord(BaseModel):
    wins: int = 0
    losses: int = 0


class EventTeam(BaseModel):
    code: str
    image: str
    name: str
    result: TeamResult | None = None
    record: TeamRecord | None = None


class MatchStrategy(BaseModel):
    count: int
    type: str


class Match(BaseModel):
    id: str
    teams: list[EventTeam]
    strategy: MatchStrategy


class EventLeague(BaseModel):
    name: str
    slug: str


class ScheduleEvent(BaseModel):
    startTime: str
    blockName: str
    state: str
    type: str
    league: EventLeague
    match: Match


class SchedulePages(BaseModel):
    older: str | None = None
    newer: str | None = None


class Schedule(BaseModel):
    updated: str | None = None
    pages: SchedulePages
    events: list[ScheduleEvent]

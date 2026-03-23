from __future__ import annotations

from pydantic import BaseModel


class ParticipantMetadata(BaseModel):
    participantId: int
    summonerName: str = ""
    championId: str = ""
    role: str = ""


class TeamMetadata(BaseModel):
    esportsTeamId: str
    participantMetadata: list[ParticipantMetadata] = []


class GameMetadata(BaseModel):
    patchVersion: str = ""
    blueTeamMetadata: TeamMetadata
    redTeamMetadata: TeamMetadata


class WindowTeamStats(BaseModel):
    totalGold: int = 0
    inhibitors: int = 0
    towers: int = 0
    barons: int = 0
    totalKills: int = 0
    dragons: list[str] = []


class WindowFrame(BaseModel):
    rfc460Timestamp: str
    gameState: str = ""
    blueTeam: WindowTeamStats
    redTeam: WindowTeamStats


class WindowResponse(BaseModel):
    esportsGameId: str
    esportsMatchId: str
    gameMetadata: GameMetadata
    frames: list[WindowFrame] = []

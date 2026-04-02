from __future__ import annotations

from pydantic import BaseModel


class PerkMetadata(BaseModel):
    styleId: int = 0
    subStyleId: int = 0
    perks: list[int] = []


class DetailsParticipant(BaseModel):
    participantId: int
    level: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    creepScore: int = 0
    totalGold: int = 0
    currentHealth: int = 0
    maxHealth: int = 0
    totalGoldEarned: int = 0
    killParticipation: float = 0.0
    championDamageShare: float = 0.0
    wardsPlaced: int = 0
    wardsDestroyed: int = 0
    attackDamage: int = 0
    abilityPower: int = 0
    criticalChance: float = 0.0
    attackSpeed: float = 0.0
    lifeSteal: float = 0.0
    armor: int = 0
    magicResistance: int = 0
    tenacity: float = 0.0
    items: list[int] = []
    perkMetadata: PerkMetadata = PerkMetadata()
    abilities: str = ""


class DetailsFrame(BaseModel):
    rfc460Timestamp: str
    participants: list[DetailsParticipant] = []


class DetailsResponse(BaseModel):
    frames: list[DetailsFrame] = []

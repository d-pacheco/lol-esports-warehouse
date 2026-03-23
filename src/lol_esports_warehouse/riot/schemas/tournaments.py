from pydantic import BaseModel


class Tournament(BaseModel):
    id: str
    slug: str
    startDate: str
    endDate: str

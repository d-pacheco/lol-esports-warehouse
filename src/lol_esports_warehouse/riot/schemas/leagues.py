from pydantic import BaseModel


class League(BaseModel):
    id: str
    slug: str
    name: str
    image: str
    region: str

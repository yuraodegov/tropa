"""Request/response schemas shared by the API and the Android client."""
from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    city: str = Field(min_length=2, max_length=80, examples=["Rome"])
    days: int = Field(ge=1, le=5, examples=[2])
    interests: list[str] = Field(default_factory=list, max_length=8,
                                 examples=[["history", "food"]])
    lang: str = Field(default="ru", pattern="^[a-z]{2}$")


class Place(BaseModel):
    id: str          # OSM id, e.g. "node/123" — the only key the LLM may use
    name: str
    category: str    # sight | museum | viewpoint | park | restaurant | cafe
    lat: float
    lon: float
    tags: dict[str, str] = Field(default_factory=dict)


class Stop(BaseModel):
    place: Place
    note: str                     # LLM tip: why go, what to see/order
    walk_from_prev_m: int = 0     # computed by code, not by the LLM
    walk_from_prev_min: int = 0


class Day(BaseModel):
    day: int
    title: str
    stops: list[Stop]
    total_walk_km: float = 0.0


class PlanResponse(BaseModel):
    city: str
    center_lat: float
    center_lon: float
    days: list[Day]
    candidates_count: int

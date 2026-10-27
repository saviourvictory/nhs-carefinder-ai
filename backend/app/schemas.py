from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    service: str = Field(min_length=2, max_length=100)
    postcode: str = Field(min_length=5, max_length=10)
    radius_miles: float = Field(default=10, ge=1, le=100)
    limit: int = Field(default=10, ge=1, le=25)

class Provider(BaseModel):
    name: str
    organisation_code: str | None = None
    service: str
    address: str
    postcode: str | None = None
    phone: str | None = None
    website: str | None = None
    distance_miles: float | None = None
    source: str
    demo: bool = False

class SearchResponse(BaseModel):
    results: list[Provider]
    notice: str

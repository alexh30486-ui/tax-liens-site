"""
Response schemas. Previously the API returned raw dicts with no
validation — using these as response_model catches shape mismatches
before they reach the client, and gives you free OpenAPI docs at /docs.
"""

from typing import Optional

from pydantic import BaseModel


class Listing(BaseModel):
    property_id: str
    parcel_id: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: str
    county: str
    assessed_value: Optional[float] = None
    lien_id: str
    lien_amount: float
    interest_rate: Optional[float] = None
    lien_status: str
    value_to_lien_ratio: Optional[float] = None


class ListingsResponse(BaseModel):
    count: int
    listings: list[Listing]


class EnrichedListing(Listing):
    ai_summary: Optional[str] = None

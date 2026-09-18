"""Pydantic request/response models."""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class Listing(BaseModel):
    property_id: str
    parcel_id: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: str
    county: str
    zip: Optional[str] = None
    assessed_value: Optional[float] = None
    property_type: Optional[str] = None
    lien_id: str
    lien_amount: float
    interest_rate: Optional[float] = None
    auction_date: Optional[date] = None
    lien_status: str
    source_county_url: Optional[str] = None
    value_to_lien_ratio: Optional[float] = None


class ListingsResponse(BaseModel):
    count: int
    listings: list[Listing]


class EnrichedListing(Listing):
    ai_summary: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    count: int
    estimated_total: int = 0
    listings: list[dict[str, Any]]


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime

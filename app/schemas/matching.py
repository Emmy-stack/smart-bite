from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.match import MatchStatus

class NGOMatchResult(BaseModel):
    ngo_id: int = Field(..., description="ID of the matched NGO")
    ngo_name: str = Field(..., description="Name of the NGO")
    ngo_address: str = Field(..., description="Physical address of the NGO")
    match_score: float = Field(..., ge=0.0, le=100.0, description="Overall weighted compatibility score (0-100)")
    match_tier: str = Field(..., description="Classification: Excellent (85-100), Good (70-84), Fair (50-69), Low (<50)")
    
    # Factor breakdown for frontend explainability
    distance_km: float = Field(..., ge=0.0, description="Haversine distance between restaurant and NGO in kilometers")
    distance_score: float = Field(..., ge=0.0, le=100.0, description="Proximity score (25% weight)")
    urgency_score: float = Field(..., ge=0.0, le=100.0, description="Time-remaining urgency score (20% weight)")
    food_compatibility_score: float = Field(..., ge=0.0, le=100.0, description="Food category & dietary compatibility score (15% weight)")
    demand_score: float = Field(..., ge=0.0, le=100.0, description="Beneficiary absorption demand score (15% weight)")
    quantity_score: float = Field(..., ge=0.0, le=100.0, description="Quantity vs capacity compatibility score (10% weight)")
    logistics_score: float = Field(..., ge=0.0, le=100.0, description="Transportation and pickup availability score (10% weight)")
    reliability_score: float = Field(..., ge=0.0, le=100.0, description="Historical fulfillment reliability score (5% weight)")
    
    # Additional context
    estimated_people_served: float = Field(..., ge=0.0, description="Estimated beneficiaries that will directly receive meals")
    matched_requirement: Optional[str] = Field(None, description="The specific NGO requirement or category matched")
    pickup_available: bool = Field(..., description="Whether the NGO can dispatch transport to pick up the donation")

    model_config = ConfigDict(from_attributes=True)

class DonationMatchResponse(BaseModel):
    donation_id: int
    food_name: str
    food_category: str
    quantity: float
    restaurant_id: int
    restaurant_name: str
    restaurant_address: str
    available_until: datetime
    hours_remaining: float
    total_ngos_evaluated: int
    matches_returned: int
    matches: List[NGOMatchResult]

    model_config = ConfigDict(from_attributes=True)

class MatchingWeightsConfig(BaseModel):
    distance: float = 0.25
    urgency: float = 0.20
    food_compatibility: float = 0.15
    demand: float = 0.15
    quantity: float = 0.10
    logistics: float = 0.10
    reliability: float = 0.05

class MatchOfferResponse(BaseModel):
    id: int
    donation_id: int
    ngo_id: int
    match_score: float
    status: MatchStatus
    created_at: datetime
    updated_at: datetime
    responded_at: Optional[datetime] = None

    # Contextual fields for frontend convenience
    food_name: Optional[str] = None
    food_category: Optional[str] = None
    quantity: Optional[float] = None
    available_until: Optional[datetime] = None
    restaurant_name: Optional[str] = None
    restaurant_address: Optional[str] = None
    ngo_name: Optional[str] = None
    ngo_address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class MatchActionResponse(BaseModel):
    message: str
    match: MatchOfferResponse
    donation_status: str

class DonationMatchesListResponse(BaseModel):
    donation_id: int
    donation_status: str
    accepted_ngo_id: Optional[int] = None
    accepted_ngo_name: Optional[str] = None
    total_offers: int
    offers: List[MatchOfferResponse]

    model_config = ConfigDict(from_attributes=True)

class BatchOfferRequest(BaseModel):
    top_k: int = Field(3, ge=1, le=20, description="Number of top-ranked NGOs to extend match offers to")
    min_score: float = Field(40.0, ge=0.0, le=100.0, description="Minimum compatibility threshold to generate offer")

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class NGOBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Organization / NGO name")
    address: str = Field(..., min_length=5, max_length=255, description="Physical address of the NGO distribution center")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate between -180 and 180")
    beneficiary_count: int = Field(0, ge=0, description="Number of beneficiaries served daily")
    food_requirements: Optional[str] = Field(None, max_length=500, description="Specific dietary or category requirements (e.g. Vegetarian, Halal, Cooked Meals)")
    capacity: int = Field(0, ge=0, description="Storage or intake capacity (in meals or kg)")
    pickup_available: bool = Field(True, description="Whether the NGO has vehicles/staff available to pick up donations")

class NGOCreate(NGOBase):
    user_id: Optional[int] = Field(None, description="Optional associated user ID")

class NGOUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    address: Optional[str] = Field(None, min_length=5, max_length=255)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    beneficiary_count: Optional[int] = Field(None, ge=0)
    food_requirements: Optional[str] = Field(None, max_length=500)
    capacity: Optional[int] = Field(None, ge=0)
    pickup_available: Optional[bool] = None
    user_id: Optional[int] = None

class NGOResponse(NGOBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

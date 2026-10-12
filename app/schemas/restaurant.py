from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class RestaurantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Restaurant name")
    address: str = Field(..., min_length=5, max_length=255, description="Physical street address")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate between -180 and 180")

class RestaurantCreate(RestaurantBase):
    user_id: Optional[int] = Field(None, description="Optional associated user ID")

class RestaurantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    address: Optional[str] = Field(None, min_length=5, max_length=255)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    user_id: Optional[int] = None

class RestaurantResponse(RestaurantBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

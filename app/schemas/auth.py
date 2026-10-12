from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.user import UserRole
from app.schemas.user import UserResponse
from app.schemas.restaurant import RestaurantResponse
from app.schemas.ngo import NGOResponse

class AuthMeResponse(BaseModel):
    authenticated: bool = True
    clerk_id: str
    is_onboarded: bool
    email: Optional[str] = None
    role: Optional[UserRole] = None
    user: Optional[UserResponse] = None
    restaurant: Optional[RestaurantResponse] = None
    ngo: Optional[NGOResponse] = None

class OnboardRestaurantRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of representative")
    email: Optional[EmailStr] = Field(None, description="Contact email if different from Clerk")
    phone: Optional[str] = Field(None, max_length=50)
    restaurant_name: str = Field(..., min_length=2, max_length=150, description="Restaurant business name")
    address: str = Field(..., min_length=5, max_length=255, description="Street address")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)

class OnboardNGORequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of representative")
    email: Optional[EmailStr] = Field(None, description="Contact email if different from Clerk")
    phone: Optional[str] = Field(None, max_length=50)
    ngo_name: str = Field(..., min_length=2, max_length=150, description="NGO organization name")
    address: str = Field(..., min_length=5, max_length=255, description="Street address")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    beneficiary_count: int = Field(..., ge=1, description="Number of beneficiaries served")
    food_requirements: Optional[str] = Field(None, max_length=255, description="Dietary restrictions or accepted food categories")
    capacity: int = Field(..., ge=1, description="Daily food handling or storage capacity in kg/meals")
    pickup_available: bool = Field(True, description="Whether the NGO has logistics for pickup")

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.user import UserRole

class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of user or organization representative")
    email: EmailStr = Field(..., description="Valid contact email address")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    role: UserRole = Field(..., description="Role: 'restaurant' or 'ngo'")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)

class UserResponse(UserBase):
    id: int
    clerk_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

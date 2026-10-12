from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.models.donation import DonationStatus

class FoodDonationBase(BaseModel):
    restaurant_id: Optional[int] = Field(None, description="ID of the donating restaurant (inferred from session if omitted)")
    food_name: str = Field(..., min_length=2, max_length=150, description="Name or description of food")
    food_category: str = Field(..., min_length=2, max_length=100, description="Category (e.g. Bakery, Cooked Meals, Produce, Dairy)")
    quantity: float = Field(..., gt=0, description="Quantity of food (in portions, servings, or kg; must be greater than 0)")
    prepared_at: Optional[datetime] = Field(None, description="Timestamp when the food was prepared")
    available_until: datetime = Field(..., description="Expiration / pickup cutoff timestamp")
    storage_method: Optional[str] = Field("ambient", max_length=100, description="Storage requirement (e.g. ambient, refrigerated, frozen)")
    pickup_available: bool = Field(True, description="Whether pickup by NGO is available")

    @field_validator("available_until")
    @classmethod
    def validate_available_until(cls, v: datetime, info) -> datetime:
        # If prepared_at is provided, available_until should ideally be after prepared_at
        return v

class FoodDonationCreate(FoodDonationBase):
    pass

class FoodDonationUpdate(BaseModel):
    food_name: Optional[str] = Field(None, min_length=2, max_length=150)
    food_category: Optional[str] = Field(None, min_length=2, max_length=100)
    quantity: Optional[float] = Field(None, gt=0)
    prepared_at: Optional[datetime] = None
    available_until: Optional[datetime] = None
    storage_method: Optional[str] = Field(None, max_length=100)
    pickup_available: Optional[bool] = None
    status: Optional[DonationStatus] = None

class FoodDonationResponse(FoodDonationBase):
    id: int
    status: DonationStatus
    accepted_ngo_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DonationStatusUpdate(BaseModel):
    status: DonationStatus = Field(..., description="Target lifecycle status")

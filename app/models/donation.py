import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class DonationStatus(str, enum.Enum):
    AVAILABLE = "available"
    MATCHED = "matched"
    ACCEPTED = "accepted"
    PICKUP = "pickup"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class FoodDonation(Base):
    __tablename__ = "food_donations"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    food_name = Column(String(150), nullable=False)
    food_category = Column(String(100), nullable=False)
    quantity = Column(Float, nullable=False)
    prepared_at = Column(DateTime(timezone=True), nullable=True)
    available_until = Column(DateTime(timezone=True), nullable=False)
    storage_method = Column(String(100), nullable=True)
    pickup_available = Column(Boolean, default=True, nullable=False)
    status = Column(SQLEnum(DonationStatus), default=DonationStatus.AVAILABLE, nullable=False)
    accepted_ngo_id = Column(Integer, ForeignKey("ngos.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    restaurant = relationship("Restaurant", back_populates="donations")
    accepted_ngo = relationship("NGO", foreign_keys=[accepted_ngo_id])
    matches = relationship("Match", back_populates="donation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FoodDonation id={self.id} food_name={self.food_name} status={self.status}>"

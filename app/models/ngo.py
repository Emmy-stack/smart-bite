from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class NGO(Base):
    __tablename__ = "ngos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(150), nullable=False)
    address = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    beneficiary_count = Column(Integer, default=0, nullable=False)
    food_requirements = Column(Text, nullable=True)
    capacity = Column(Integer, default=0, nullable=False)
    pickup_available = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="ngo")
    matches = relationship("Match", back_populates="ngo", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NGO id={self.id} name={self.name}>"

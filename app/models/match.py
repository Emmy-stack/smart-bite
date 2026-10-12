import enum
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("donation_id", "ngo_id", name="uq_match_donation_ngo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    donation_id = Column(Integer, ForeignKey("food_donations.id", ondelete="CASCADE"), nullable=False, index=True)
    ngo_id = Column(Integer, ForeignKey("ngos.id", ondelete="CASCADE"), nullable=False, index=True)
    match_score = Column(Float, nullable=False)
    status = Column(SQLEnum(MatchStatus), default=MatchStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    donation = relationship("FoodDonation", back_populates="matches")
    ngo = relationship("NGO", back_populates="matches")

    def __repr__(self):
        return f"<Match id={self.id} donation_id={self.donation_id} ngo_id={self.ngo_id} status={self.status}>"

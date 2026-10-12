import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class UserRole(str, enum.Enum):
    RESTAURANT = "restaurant"
    NGO = "ngo"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(SQLEnum(UserRole), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    clerk_id = Column(String(128), unique=True, index=True, nullable=True)

    # Relationships
    restaurant = relationship("Restaurant", back_populates="user", uselist=False, cascade="all, delete-orphan")
    ngo = relationship("NGO", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} clerk_id={self.clerk_id} email={self.email} role={self.role}>"

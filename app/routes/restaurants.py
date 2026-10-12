from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.restaurant import RestaurantCreate, RestaurantResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])

@router.post("/", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED, summary="Create a new restaurant")
def create_restaurant(
    payload: RestaurantCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a new restaurant partner for the authenticated restaurant user.
    """
    if current_user.role != UserRole.RESTAURANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Restaurant role required"
        )

    if current_user.restaurant is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user already has an associated restaurant profile"
        )

    restaurant = Restaurant(
        name=payload.name,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        user_id=current_user.id
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return restaurant

@router.get("/", response_model=List[RestaurantResponse], summary="List all restaurants")
def get_restaurants(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(50, ge=1, le=100, description="Limit"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve registered restaurants with pagination.
    """
    return db.query(Restaurant).offset(skip).limit(limit).all()

@router.get("/{restaurant_id}", response_model=RestaurantResponse, summary="Get restaurant by ID")
def get_restaurant_by_id(
    restaurant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch details of a single restaurant by its ID.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restaurant with id {restaurant_id} not found"
        )
    return restaurant

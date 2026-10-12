from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ngo import NGO
from app.models.user import User, UserRole
from app.schemas.ngo import NGOCreate, NGOResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/ngos", tags=["NGOs"])

@router.post("/", response_model=NGOResponse, status_code=status.HTTP_201_CREATED, summary="Create a new NGO")
def create_ngo(
    payload: NGOCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a new verified NGO organization for the authenticated NGO user.
    """
    if current_user.role != UserRole.NGO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: NGO role required"
        )

    if current_user.ngo is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user already has an associated NGO profile"
        )

    ngo = NGO(
        name=payload.name,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        beneficiary_count=payload.beneficiary_count,
        food_requirements=payload.food_requirements,
        capacity=payload.capacity,
        pickup_available=payload.pickup_available,
        user_id=current_user.id
    )
    db.add(ngo)
    db.commit()
    db.refresh(ngo)
    return ngo

@router.get("/", response_model=List[NGOResponse], summary="List all NGOs")
def get_ngos(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(50, ge=1, le=100, description="Limit"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve registered NGOs with pagination.
    """
    return db.query(NGO).offset(skip).limit(limit).all()

@router.get("/{ngo_id}", response_model=NGOResponse, summary="Get NGO by ID")
def get_ngo_by_id(
    ngo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch details of a single NGO by its ID.
    """
    ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
    if not ngo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NGO with id {ngo_id} not found"
        )
    return ngo

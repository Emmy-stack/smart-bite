from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.donation import FoodDonation, DonationStatus
from app.models.match import Match, MatchStatus
from app.models.ngo import NGO
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.schemas.donation import (
    FoodDonationCreate,
    FoodDonationResponse,
    DonationStatusUpdate,
)
from app.schemas.matching import (
    DonationMatchesListResponse,
    MatchOfferResponse,
)
from app.services.auth import (
    get_current_user,
    get_current_restaurant_user,
)
from app.services.workflow import update_donation_lifecycle_status

router = APIRouter(prefix="/donations", tags=["Donations"])

@router.post("/", response_model=FoodDonationResponse, status_code=status.HTTP_201_CREATED, summary="Create a new food donation")
def create_donation(
    payload: FoodDonationCreate,
    current_user: User = Depends(get_current_restaurant_user),
    db: Session = Depends(get_db)
):
    """
    Publish a new surplus food donation from an authenticated restaurant.
    Enforces that donations are created under the caller's verified restaurant profile.
    """
    # If a restaurant_id is explicitly specified, verify it exists, then verify ownership
    if payload.restaurant_id is not None:
        target_restaurant = db.query(Restaurant).filter(Restaurant.id == payload.restaurant_id).first()
        if not target_restaurant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant with id {payload.restaurant_id} does not exist"
            )
        if target_restaurant.id != current_user.restaurant.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create donation for a restaurant you do not own"
            )

    restaurant_id = current_user.restaurant.id

    donation = FoodDonation(
        restaurant_id=restaurant_id,
        food_name=payload.food_name,
        food_category=payload.food_category,
        quantity=payload.quantity,
        prepared_at=payload.prepared_at,
        available_until=payload.available_until,
        storage_method=payload.storage_method,
        pickup_available=payload.pickup_available,
        status=DonationStatus.AVAILABLE
    )
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return donation

@router.get("/", response_model=List[FoodDonationResponse], summary="List all food donations")
def get_donations(
    status_filter: Optional[DonationStatus] = Query(None, alias="status", description="Filter donations by status"),
    restaurant_id: Optional[int] = Query(None, description="Filter donations by restaurant ID"),
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(50, ge=1, le=100, description="Limit"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve food donations with optional filtering by status and restaurant.
    Requires an authenticated user.
    """
    query = db.query(FoodDonation)
    if status_filter:
        query = query.filter(FoodDonation.status == status_filter)
    if restaurant_id is not None:
        query = query.filter(FoodDonation.restaurant_id == restaurant_id)
    return query.offset(skip).limit(limit).all()

@router.get("/{donation_id}", response_model=FoodDonationResponse, summary="Get donation by ID")
def get_donation_by_id(
    donation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch details of a single food donation by its ID.
    Requires an authenticated user.
    """
    donation = db.query(FoodDonation).filter(FoodDonation.id == donation_id).first()
    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donation with id {donation_id} not found"
        )
    return donation

@router.get(
    "/{donation_id}/matches",
    response_model=DonationMatchesListResponse,
    status_code=status.HTTP_200_OK,
    summary="Restaurant views match offers and accepted NGO",
    description="Retrieves all match offers generated for a donation, their statuses, and identifies the accepted NGO if claimed."
)
def get_donation_match_history(
    donation_id: int,
    current_user: User = Depends(get_current_restaurant_user),
    db: Session = Depends(get_db)
):
    """
    Enables donor restaurants to track match offers for their own donations.
    Rejects unauthorized access from other restaurants.
    """
    donation = db.query(FoodDonation).filter(FoodDonation.id == donation_id).first()
    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donation with id {donation_id} not found"
        )

    if donation.restaurant_id != current_user.restaurant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access match history for another restaurant's donation"
        )

    matches = db.query(Match).filter(Match.donation_id == donation.id).all()
    accepted_ngo_name = None
    if donation.accepted_ngo_id:
        accepted_ngo = db.query(NGO).filter(NGO.id == donation.accepted_ngo_id).first()
        if accepted_ngo:
            accepted_ngo_name = accepted_ngo.name

    offer_responses: List[MatchOfferResponse] = []
    for m in matches:
        ngo = m.ngo
        offer_responses.append(
            MatchOfferResponse(
                id=m.id,
                donation_id=m.donation_id,
                ngo_id=m.ngo_id,
                match_score=m.match_score,
                status=m.status,
                created_at=m.created_at,
                updated_at=m.updated_at,
                responded_at=m.responded_at,
                food_name=donation.food_name,
                food_category=donation.food_category,
                quantity=donation.quantity,
                available_until=donation.available_until,
                ngo_name=ngo.name if ngo else None,
                ngo_address=ngo.address if ngo else None,
            )
        )

    return DonationMatchesListResponse(
        donation_id=donation.id,
        donation_status=donation.status.value,
        accepted_ngo_id=donation.accepted_ngo_id,
        accepted_ngo_name=accepted_ngo_name,
        total_offers=len(matches),
        offers=offer_responses
    )

@router.patch(
    "/{donation_id}/status",
    response_model=FoodDonationResponse,
    status_code=status.HTTP_200_OK,
    summary="Progress donation lifecycle status",
    description="Transitions donation status (available -> matched -> accepted -> pickup -> delivered -> completed, or cancelled). Validates allowable state machine transitions."
)
def update_donation_status(
    donation_id: int,
    payload: DonationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates the lifecycle status of a donation with state-machine and role authorization checks.
    Only the owning restaurant or the accepted NGO recipient may update donation status.
    """
    donation = db.query(FoodDonation).filter(FoodDonation.id == donation_id).first()
    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donation with id {donation_id} not found"
        )

    is_owner = (
        current_user.role == UserRole.RESTAURANT
        and current_user.restaurant is not None
        and donation.restaurant_id == current_user.restaurant.id
    )
    is_accepted_ngo = (
        current_user.role == UserRole.NGO
        and current_user.ngo is not None
        and donation.accepted_ngo_id == current_user.ngo.id
    )

    if not (is_owner or is_accepted_ngo):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update status for this donation"
        )

    return update_donation_lifecycle_status(
        donation_id=donation_id,
        target_status=payload.status,
        db=db
    )

@router.post(
    "/{donation_id}/cancel",
    response_model=FoodDonationResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel an active food donation",
    description="Cancels an eligible donation before pickup/completion and cancels any active pending/accepted match offers."
)
def cancel_donation(
    donation_id: int,
    current_user: User = Depends(get_current_restaurant_user),
    db: Session = Depends(get_db)
):
    """
    Cancels an eligible donation. Only the owning restaurant may cancel.
    """
    donation = db.query(FoodDonation).filter(FoodDonation.id == donation_id).first()
    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donation with id {donation_id} not found"
        )

    if donation.restaurant_id != current_user.restaurant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel another restaurant's donation"
        )

    return update_donation_lifecycle_status(
        donation_id=donation_id,
        target_status=DonationStatus.CANCELLED,
        db=db
    )

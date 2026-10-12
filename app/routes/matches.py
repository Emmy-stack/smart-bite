from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.donation import FoodDonation, DonationStatus
from app.models.ngo import NGO
from app.models.match import Match, MatchStatus
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.matching import (
    DonationMatchResponse,
    MatchOfferResponse,
    MatchActionResponse,
    BatchOfferRequest,
)
from app.services.auth import (
    get_current_restaurant_user,
    get_current_ngo_user,
)
from app.services.matching import rank_ngos_for_donation
from app.services.workflow import (
    create_match_offers,
    accept_match_offer,
    reject_match_offer,
    check_and_apply_donation_expiration,
)

router = APIRouter(prefix="/matches", tags=["Matching & Offers"])


def _build_offer_response(match: Match) -> MatchOfferResponse:
    """Helper to populate contextual donor and NGO fields for an offer."""
    donation = match.donation
    restaurant = donation.restaurant if donation else None
    ngo = match.ngo

    return MatchOfferResponse(
        id=match.id,
        donation_id=match.donation_id,
        ngo_id=match.ngo_id,
        match_score=match.match_score,
        status=match.status,
        created_at=match.created_at,
        updated_at=match.updated_at,
        responded_at=match.responded_at,
        food_name=donation.food_name if donation else None,
        food_category=donation.food_category if donation else None,
        quantity=donation.quantity if donation else None,
        available_until=donation.available_until if donation else None,
        restaurant_name=restaurant.name if restaurant else None,
        restaurant_address=restaurant.address if restaurant else None,
        ngo_name=ngo.name if ngo else None,
        ngo_address=ngo.address if ngo else None,
    )


@router.get(
    "/donation/{donation_id}",
    response_model=DonationMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate and rank best-matching NGOs for a donation",
    description="Evaluates all verified NGOs using our 7-factor explainable algorithm. Restricted to owning restaurant."
)
def get_matches_for_donation(
    donation_id: int,
    min_score: float = Query(0.0, ge=0.0, le=100.0, description="Minimum overall match score threshold"),
    limit: Optional[int] = Query(10, ge=1, le=50, description="Maximum number of recommendations to return"),
    persist_offers: bool = Query(False, description="Whether to also generate persistent pending offers for top matches"),
    current_user: User = Depends(get_current_restaurant_user),
    db: Session = Depends(get_db)
):
    """
    Evaluates, ranks, and optionally persists match offers for an active food donation.
    Caller must be the authenticated restaurant owning the donation.
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
            detail="Not authorized to evaluate matches for another restaurant's donation"
        )

    if donation.status in [DonationStatus.EXPIRED, DonationStatus.CANCELLED, DonationStatus.COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Donation status is '{donation.status.value}'. Ineligible for matching."
        )

    now = datetime.now(timezone.utc)
    avail_until = donation.available_until
    if avail_until.tzinfo is None:
        avail_until = avail_until.replace(tzinfo=timezone.utc)

    hours_remaining = (avail_until - now).total_seconds() / 3600.0
    if hours_remaining <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Donation has already expired and is ineligible for matching."
        )

    restaurant = donation.restaurant
    if not restaurant:
        restaurant = db.query(Restaurant).filter(Restaurant.id == donation.restaurant_id).first()

    rest_name = restaurant.name if restaurant else "Unknown Restaurant"
    rest_addr = restaurant.address if restaurant else "Unknown Address"

    ngos = db.query(NGO).all()
    ranked_matches = rank_ngos_for_donation(
        donation=donation,
        ngos=ngos,
        db=db,
        min_score=min_score,
        limit=limit
    )

    if persist_offers and ranked_matches:
        create_match_offers(
            donation_id=donation.id,
            db=db,
            top_k=len(ranked_matches),
            min_score=min_score
        )

    return DonationMatchResponse(
        donation_id=donation.id,
        food_name=donation.food_name,
        food_category=donation.food_category,
        quantity=donation.quantity,
        restaurant_id=donation.restaurant_id,
        restaurant_name=rest_name,
        restaurant_address=rest_addr,
        available_until=donation.available_until,
        hours_remaining=round(hours_remaining, 1),
        total_ngos_evaluated=len(ngos),
        matches_returned=len(ranked_matches),
        matches=ranked_matches
    )


@router.post(
    "/donation/{donation_id}/offers",
    response_model=List[MatchOfferResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate persistent match offers for recommended NGOs",
    description="Evaluates candidates, creates pending match records, and transitions donation status from 'available' to 'matched'."
)
def create_offers_for_donation(
    donation_id: int,
    payload: BatchOfferRequest = BatchOfferRequest(),
    current_user: User = Depends(get_current_restaurant_user),
    db: Session = Depends(get_db)
):
    """
    Creates persistent match offers for the top-k evaluated NGOs.
    Restricted to the authenticated owner of the donation.
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
            detail="Not authorized to create match offers for another restaurant's donation"
        )

    offers = create_match_offers(
        donation_id=donation_id,
        db=db,
        top_k=payload.top_k,
        min_score=payload.min_score
    )
    return [_build_offer_response(o) for o in offers]


@router.get(
    "/pending",
    response_model=List[MatchOfferResponse],
    status_code=status.HTTP_200_OK,
    summary="View pending match offers for an NGO",
    description="Lists all active pending donation offers awaiting the caller's NGO. Excludes or expires past cutoffs."
)
def get_pending_offers_for_ngo(
    ngo_id: Optional[int] = Query(None, description="Optional NGO ID query parameter (must match caller)"),
    current_user: User = Depends(get_current_ngo_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves pending match offers for the authenticated verified NGO.
    Disallows querying another NGO's private offers.
    """
    caller_ngo_id = current_user.ngo.id
    if ngo_id is not None:
        target_ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
        if not target_ngo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NGO with id {ngo_id} not found"
            )
        if ngo_id != caller_ngo_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view pending offers for another NGO"
            )

    offers = db.query(Match).filter(
        Match.ngo_id == caller_ngo_id,
        Match.status == MatchStatus.PENDING
    ).all()

    valid_pending: List[MatchOfferResponse] = []
    now = datetime.now(timezone.utc)

    for offer in offers:
        donation = offer.donation
        if not donation:
            continue

        # Check if donation expired in the interim
        if check_and_apply_donation_expiration(donation, db):
            continue

        # Check if donation was already accepted by another NGO
        if donation.status == DonationStatus.ACCEPTED and donation.accepted_ngo_id != caller_ngo_id:
            offer.status = MatchStatus.CANCELLED
            offer.responded_at = now
            db.commit()
            continue

        valid_pending.append(_build_offer_response(offer))

    return valid_pending


@router.post(
    "/{match_id}/accept",
    response_model=MatchActionResponse,
    status_code=status.HTTP_200_OK,
    summary="NGO accepts a pending match offer",
    description="Atomically accepts the offer, marks donation as 'accepted', and cancels competing pending offers for the same donation."
)
def accept_offer(
    match_id: int,
    current_user: User = Depends(get_current_ngo_user),
    db: Session = Depends(get_db)
):
    """
    Accepts an eligible match offer for the authenticated NGO.
    Rejects attempts by one NGO to accept an offer directed to another NGO.
    """
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match offer with id {match_id} not found"
        )

    if match.ngo_id != current_user.ngo.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to accept a match offer belonging to another NGO"
        )

    accepted_match, updated_donation = accept_match_offer(match_id=match_id, db=db)
    return MatchActionResponse(
        message="Match offer accepted successfully. Donation is now confirmed for pickup.",
        match=_build_offer_response(accepted_match),
        donation_status=updated_donation.status.value
    )


@router.post(
    "/{match_id}/reject",
    response_model=MatchActionResponse,
    status_code=status.HTTP_200_OK,
    summary="NGO rejects a pending match offer",
    description="Marks the offer as 'rejected'. If no other offers remain pending, transitions donation back to 'available'."
)
def reject_offer(
    match_id: int,
    current_user: User = Depends(get_current_ngo_user),
    db: Session = Depends(get_db)
):
    """
    Rejects a pending match offer for the authenticated NGO.
    Rejects attempts by one NGO to reject an offer directed to another NGO.
    """
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match offer with id {match_id} not found"
        )

    if match.ngo_id != current_user.ngo.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reject a match offer belonging to another NGO"
        )

    rejected_match = reject_match_offer(match_id=match_id, db=db)
    donation = rejected_match.donation
    status_val = donation.status.value if donation else "unknown"

    return MatchActionResponse(
        message="Match offer rejected.",
        match=_build_offer_response(rejected_match),
        donation_status=status_val
    )

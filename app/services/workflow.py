"""
Donation & Match Workflow Service
=================================
Manages:
1. Persistent match offers generation and retrieval
2. Concurrency-safe match acceptance and rejection
3. Donation lifecycle state machine transitions
4. Expiration and cancellation handling
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.donation import FoodDonation, DonationStatus
from app.models.ngo import NGO
from app.models.match import Match, MatchStatus
from app.models.restaurant import Restaurant
from app.services.matching import rank_ngos_for_donation

# Valid transitions state machine
VALID_DONATION_TRANSITIONS: Dict[DonationStatus, List[DonationStatus]] = {
    DonationStatus.AVAILABLE: [
        DonationStatus.MATCHED,
        DonationStatus.ACCEPTED,
        DonationStatus.CANCELLED,
        DonationStatus.EXPIRED,
    ],
    DonationStatus.MATCHED: [
        DonationStatus.AVAILABLE,
        DonationStatus.ACCEPTED,
        DonationStatus.CANCELLED,
        DonationStatus.EXPIRED,
    ],
    DonationStatus.ACCEPTED: [
        DonationStatus.PICKUP,
        DonationStatus.CANCELLED,
    ],
    DonationStatus.PICKUP: [
        DonationStatus.DELIVERED,
    ],
    DonationStatus.DELIVERED: [
        DonationStatus.COMPLETED,
    ],
    DonationStatus.COMPLETED: [],
    DonationStatus.CANCELLED: [],
    DonationStatus.EXPIRED: [],
}


def validate_status_transition(current: DonationStatus, target: DonationStatus) -> None:
    """
    Validates that transition from `current` to `target` is permitted.
    Raises HTTPException 400 with a detailed error message if invalid.
    """
    if current == target:
        return

    allowed = VALID_DONATION_TRANSITIONS.get(current, [])
    if target not in allowed:
        allowed_str = ", ".join(f"'{s.value}'" for s in allowed) if allowed else "none (terminal state)"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid donation status transition: cannot change from '{current.value}' to '{target.value}'. "
                f"Allowed next states from '{current.value}': [{allowed_str}]."
            )
        )


def check_and_apply_donation_expiration(donation: FoodDonation, db: Session) -> bool:
    """
    Checks if donation has exceeded available_until timestamp.
    If expired, marks donation as EXPIRED and marks pending matches as EXPIRED.
    Returns True if expired, False otherwise.
    """
    now = datetime.now(timezone.utc)
    avail_until = donation.available_until
    if avail_until.tzinfo is None:
        avail_until = avail_until.replace(tzinfo=timezone.utc)

    if avail_until <= now:
        if donation.status not in [DonationStatus.COMPLETED, DonationStatus.DELIVERED, DonationStatus.CANCELLED, DonationStatus.EXPIRED]:
            donation.status = DonationStatus.EXPIRED
            # Expire any pending offers
            pending_matches = db.query(Match).filter(
                Match.donation_id == donation.id,
                Match.status == MatchStatus.PENDING
            ).all()
            for m in pending_matches:
                m.status = MatchStatus.EXPIRED
                m.responded_at = now
            db.commit()
        return True
    return False


def create_match_offers(
    donation_id: int,
    db: Session,
    top_k: int = 3,
    min_score: float = 40.0,
    specific_ngo_ids: Optional[List[int]] = None
) -> List[Match]:
    """
    Generates and persists match offers for candidate NGOs.
    Prevents duplicate active offers for the same donation and NGO.
    Transitions donation from AVAILABLE to MATCHED.
    """
    # 1. Fetch donation with lock
    donation = db.query(FoodDonation).filter(FoodDonation.id == donation_id).first()
    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donation with id {donation_id} not found"
        )

    # 2. Check status and expiration
    if check_and_apply_donation_expiration(donation, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create match offers: donation has already expired."
        )

    if donation.status in [DonationStatus.ACCEPTED, DonationStatus.PICKUP, DonationStatus.DELIVERED, DonationStatus.COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot create match offers: donation is already in '{donation.status.value}' state."
        )

    if donation.status == DonationStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create match offers: donation is cancelled."
        )

    # 3. Get all NGOs or filter by specific_ngo_ids
    query = db.query(NGO)
    if specific_ngo_ids:
        query = query.filter(NGO.id.in_(specific_ngo_ids))
    ngos = query.all()

    if not ngos:
        return []

    # 4. Rank NGOs via matching engine
    ranked_results = rank_ngos_for_donation(
        donation=donation,
        ngos=ngos,
        db=db,
        min_score=min_score,
        limit=top_k
    )

    created_offers: List[Match] = []
    now = datetime.now(timezone.utc)

    # 5. Persist offers, ensuring uniqueness per donation & NGO
    for res in ranked_results:
        existing = db.query(Match).filter(
            Match.donation_id == donation.id,
            Match.ngo_id == res.ngo_id
        ).first()

        if existing:
            # If already pending, keep existing
            if existing.status == MatchStatus.PENDING:
                created_offers.append(existing)
                continue
            # If rejected/cancelled previously, can update to pending with new score
            existing.status = MatchStatus.PENDING
            existing.match_score = res.match_score
            existing.responded_at = None
            created_offers.append(existing)
        else:
            new_match = Match(
                donation_id=donation.id,
                ngo_id=res.ngo_id,
                match_score=res.match_score,
                status=MatchStatus.PENDING
            )
            db.add(new_match)
            created_offers.append(new_match)

    # 6. Update donation status to MATCHED if still AVAILABLE
    if created_offers and donation.status == DonationStatus.AVAILABLE:
        donation.status = DonationStatus.MATCHED

    db.commit()
    for m in created_offers:
        db.refresh(m)

    return created_offers


def accept_match_offer(match_id: int, db: Session) -> Tuple[Match, FoodDonation]:
    """
    Accepts a pending match offer using a row lock.
    - Ensures donation is available/matched and not expired.
    - Ensures no other NGO has accepted it simultaneously.
    - Marks winning match as ACCEPTED.
    - Marks all other pending matches for this donation as CANCELLED.
    - Updates donation to ACCEPTED and links accepted_ngo_id.
    """
    now = datetime.now(timezone.utc)

    # 1. Fetch match with row lock
    match = db.query(Match).filter(Match.id == match_id).with_for_update().first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match with id {match_id} not found"
        )

    if match.status != MatchStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Match offer cannot be accepted: current status is '{match.status.value}' (only pending offers can be accepted)."
        )

    # 2. Fetch linked donation with row lock
    donation = db.query(FoodDonation).filter(FoodDonation.id == match.donation_id).with_for_update().first()
    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated donation {match.donation_id} not found"
        )

    # 3. Check expiration
    if check_and_apply_donation_expiration(donation, db):
        match.status = MatchStatus.EXPIRED
        match.responded_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot accept offer: donation has expired."
        )

    # 4. Check if already accepted by any NGO
    already_accepted = db.query(Match).filter(
        Match.donation_id == donation.id,
        Match.status == MatchStatus.ACCEPTED
    ).first()

    if already_accepted or donation.status not in [DonationStatus.AVAILABLE, DonationStatus.MATCHED]:
        match.status = MatchStatus.CANCELLED
        match.responded_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot accept offer: this donation has already been accepted by another organization or is no longer available."
        )

    # 5. Accept winning match
    match.status = MatchStatus.ACCEPTED
    match.responded_at = now

    # 6. Cancel other pending offers for this donation
    other_pending = db.query(Match).filter(
        Match.donation_id == donation.id,
        Match.id != match.id,
        Match.status == MatchStatus.PENDING
    ).all()

    for other in other_pending:
        other.status = MatchStatus.CANCELLED
        other.responded_at = now

    # 7. Update donation
    validate_status_transition(donation.status, DonationStatus.ACCEPTED)
    donation.status = DonationStatus.ACCEPTED
    donation.accepted_ngo_id = match.ngo_id

    db.commit()
    db.refresh(match)
    db.refresh(donation)

    return match, donation


def reject_match_offer(match_id: int, db: Session) -> Match:
    """
    Rejects a pending match offer.
    If no other pending offers exist for this donation, can revert donation to AVAILABLE.
    """
    now = datetime.now(timezone.utc)

    match = db.query(Match).filter(Match.id == match_id).with_for_update().first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match with id {match_id} not found"
        )

    if match.status != MatchStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Match offer cannot be rejected: current status is '{match.status.value}' (only pending offers can be rejected)."
        )

    match.status = MatchStatus.REJECTED
    match.responded_at = now

    donation = db.query(FoodDonation).filter(FoodDonation.id == match.donation_id).first()
    if donation and donation.status == DonationStatus.MATCHED:
        # Check if there are other pending matches
        remaining_pending = db.query(Match).filter(
            Match.donation_id == donation.id,
            Match.id != match.id,
            Match.status == MatchStatus.PENDING
        ).count()
        if remaining_pending == 0:
            donation.status = DonationStatus.AVAILABLE

    db.commit()
    db.refresh(match)
    return match


def update_donation_lifecycle_status(
    donation_id: int,
    target_status: DonationStatus,
    db: Session
) -> FoodDonation:
    """
    Transitions donation through lifecycle state machine:
    available -> matched -> accepted -> pickup -> delivered -> completed.
    Also handles cancellation.
    """
    donation = db.query(FoodDonation).filter(FoodDonation.id == donation_id).with_for_update().first()
    if not donation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Donation with id {donation_id} not found"
        )

    # Check expiration if trying to progress
    if target_status not in [DonationStatus.CANCELLED, DonationStatus.EXPIRED]:
        if check_and_apply_donation_expiration(donation, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Donation has expired. Cannot transition to '{target_status.value}'."
            )

    # Validate transition
    validate_status_transition(donation.status, target_status)

    donation.status = target_status

    # If cancelled, cancel any active/pending matches
    if target_status == DonationStatus.CANCELLED:
        now = datetime.now(timezone.utc)
        active_matches = db.query(Match).filter(
            Match.donation_id == donation.id,
            Match.status.in_([MatchStatus.PENDING, MatchStatus.ACCEPTED])
        ).all()
        for m in active_matches:
            m.status = MatchStatus.CANCELLED
            m.responded_at = now

    db.commit()
    db.refresh(donation)
    return donation

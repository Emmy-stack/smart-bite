from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.ngo import NGO
from app.schemas.auth import (
    AuthMeResponse,
    OnboardRestaurantRequest,
    OnboardNGORequest,
)
from app.services.auth import get_current_clerk_claims

router = APIRouter(prefix="/auth", tags=["Authentication & Onboarding"])


@router.get(
    "/me",
    response_model=AuthMeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user identity and onboarding status",
    description="Returns verified Clerk identity, application role, linked profile, and whether onboarding is complete."
)
def get_auth_me(
    claims: Dict[str, Any] = Depends(get_current_clerk_claims),
    db: Session = Depends(get_db)
):
    clerk_id = claims["sub"]
    user = db.query(User).filter(User.clerk_id == clerk_id).first()

    if not user:
        return AuthMeResponse(
            authenticated=True,
            clerk_id=clerk_id,
            is_onboarded=False,
            email=claims.get("email"),
            role=None,
            user=None,
            restaurant=None,
            ngo=None
        )

    return AuthMeResponse(
        authenticated=True,
        clerk_id=user.clerk_id,
        is_onboarded=True,
        email=user.email,
        role=user.role,
        user=user,
        restaurant=user.restaurant,
        ngo=user.ngo
    )


@router.post(
    "/onboard/restaurant",
    response_model=AuthMeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard new user as Restaurant partner",
    description="Associates verified Clerk identity with a local Restaurant user and creates their restaurant profile. Role is permanently locked."
)
def onboard_restaurant(
    payload: OnboardRestaurantRequest,
    claims: Dict[str, Any] = Depends(get_current_clerk_claims),
    db: Session = Depends(get_db)
):
    clerk_id = claims["sub"]

    # 1. Check if this Clerk ID is already onboarded
    existing_by_clerk = db.query(User).filter(User.clerk_id == clerk_id).first()
    if existing_by_clerk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account is already onboarded with role '{existing_by_clerk.role.value}'. Role changes are not permitted."
        )

    # 2. Determine email
    email = payload.email or claims.get("email")
    if not email:
        email = f"{clerk_id}@clerk.user"

    # 3. Check for existing database user by email for safe backfill/linking
    existing_by_email = db.query(User).filter(User.email == email).first()
    if existing_by_email:
        if existing_by_email.role != UserRole.RESTAURANT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An account with this email already exists with role '{existing_by_email.role.value}'."
            )
        if existing_by_email.clerk_id and existing_by_email.clerk_id != clerk_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email is already linked to another Clerk identity."
            )
        # Link Clerk ID to existing user
        existing_by_email.clerk_id = clerk_id
        user = existing_by_email
        # Ensure restaurant profile exists
        if not user.restaurant:
            restaurant = Restaurant(
                name=payload.restaurant_name,
                address=payload.address,
                latitude=payload.latitude,
                longitude=payload.longitude,
                user_id=user.id
            )
            db.add(restaurant)
    else:
        # Create brand-new user and restaurant profile
        user = User(
            name=payload.name,
            email=email,
            phone=payload.phone,
            role=UserRole.RESTAURANT,
            clerk_id=clerk_id
        )
        db.add(user)
        db.flush()

        restaurant = Restaurant(
            name=payload.restaurant_name,
            address=payload.address,
            latitude=payload.latitude,
            longitude=payload.longitude,
            user_id=user.id
        )
        db.add(restaurant)

    db.commit()
    db.refresh(user)

    return AuthMeResponse(
        authenticated=True,
        clerk_id=user.clerk_id,
        is_onboarded=True,
        email=user.email,
        role=user.role,
        user=user,
        restaurant=user.restaurant,
        ngo=None
    )


@router.post(
    "/onboard/ngo",
    response_model=AuthMeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard new user as verified NGO organization",
    description="Associates verified Clerk identity with a local NGO user and creates their NGO profile. Role is permanently locked."
)
def onboard_ngo(
    payload: OnboardNGORequest,
    claims: Dict[str, Any] = Depends(get_current_clerk_claims),
    db: Session = Depends(get_db)
):
    clerk_id = claims["sub"]

    # 1. Check if this Clerk ID is already onboarded
    existing_by_clerk = db.query(User).filter(User.clerk_id == clerk_id).first()
    if existing_by_clerk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account is already onboarded with role '{existing_by_clerk.role.value}'. Role changes are not permitted."
        )

    # 2. Determine email
    email = payload.email or claims.get("email")
    if not email:
        email = f"{clerk_id}@clerk.user"

    # 3. Check for existing database user by email for safe backfill/linking
    existing_by_email = db.query(User).filter(User.email == email).first()
    if existing_by_email:
        if existing_by_email.role != UserRole.NGO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An account with this email already exists with role '{existing_by_email.role.value}'."
            )
        if existing_by_email.clerk_id and existing_by_email.clerk_id != clerk_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email is already linked to another Clerk identity."
            )
        # Link Clerk ID to existing user
        existing_by_email.clerk_id = clerk_id
        user = existing_by_email
        # Ensure NGO profile exists
        if not user.ngo:
            ngo = NGO(
                name=payload.ngo_name,
                address=payload.address,
                latitude=payload.latitude,
                longitude=payload.longitude,
                beneficiary_count=payload.beneficiary_count,
                food_requirements=payload.food_requirements,
                capacity=payload.capacity,
                pickup_available=payload.pickup_available,
                user_id=user.id
            )
            db.add(ngo)
    else:
        # Create brand-new user and NGO profile
        user = User(
            name=payload.name,
            email=email,
            phone=payload.phone,
            role=UserRole.NGO,
            clerk_id=clerk_id
        )
        db.add(user)
        db.flush()

        ngo = NGO(
            name=payload.ngo_name,
            address=payload.address,
            latitude=payload.latitude,
            longitude=payload.longitude,
            beneficiary_count=payload.beneficiary_count,
            food_requirements=payload.food_requirements,
            capacity=payload.capacity,
            pickup_available=payload.pickup_available,
            user_id=user.id
        )
        db.add(ngo)

    db.commit()
    db.refresh(user)

    return AuthMeResponse(
        authenticated=True,
        clerk_id=user.clerk_id,
        is_onboarded=True,
        email=user.email,
        role=user.role,
        user=user,
        restaurant=None,
        ngo=user.ngo
    )

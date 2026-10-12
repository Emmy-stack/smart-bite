from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ngo import NGO
from app.models.user import User, UserRole
from app.schemas.forecasting import (
    NGOForecastResponse,
    AggregateForecastResponse,
    ModelEvaluationResponse,
)
from app.services.auth import get_current_user
from app.services.forecasting import (
    generate_ngo_demand_forecast,
    generate_aggregate_network_forecast,
    evaluate_forecasting_models,
)

router = APIRouter(prefix="/forecasts", tags=["Demand Forecasting"])


@router.get(
    "/ngo/{ngo_id}",
    response_model=NGOForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get 7-day explainable food demand forecast for an NGO",
    description=(
        "Forecasts estimated food demand by food category over the requested horizon. "
        "Strictly restricted to the authorized NGO representative."
    )
)
def get_ngo_forecast(
    ngo_id: int,
    days: int = Query(7, ge=1, le=30, description="Forecast horizon in days (1 to 30)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves demand forecast for a verified NGO.
    
    Enforces Clerk authentication, role authorization, and strict NGO ownership.
    Prevents access by unauthenticated users, restaurants, or other NGOs.
    """
    # Verify NGO role
    if current_user.role != UserRole.NGO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: NGO role required to access NGO demand forecasts"
        )

    # Check NGO existence first: return 404 if NGO does not exist
    target_ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
    if not target_ngo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NGO with id {ngo_id} not found"
        )

    # Verify ownership: caller must own this specific NGO profile
    if not current_user.ngo or current_user.ngo.id != ngo_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access another NGO's private forecast data"
        )

    # Check sufficient profile info
    if (target_ngo.beneficiary_count or 0) <= 0 and not target_ngo.food_requirements:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"NGO with id {ngo_id} lacks sufficient profile information for forecasting "
                "(beneficiary count must be positive and/or food requirements defined)."
            )
        )

    return generate_ngo_demand_forecast(ngo=target_ngo, days=days, db=db)


@router.get(
    "/aggregate",
    response_model=AggregateForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated food demand forecast across the network",
    description=(
        "Provides network-wide projected demand by food category to assist restaurants "
        "and platform coordinators in donation batch planning. Protects individual NGO privacy."
    )
)
def get_aggregate_forecast(
    days: int = Query(7, ge=1, le=30, description="Forecast horizon in days (1 to 30)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves aggregate demand across all active NGOs for donation planning.
    Accessible to authenticated restaurants, NGOs, and platform coordinators.
    """
    return generate_aggregate_network_forecast(days=days, db=db)


@router.get(
    "/evaluation",
    response_model=ModelEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get forecasting model evaluation report",
    description=(
        "Evaluates forecasting models using chronological validation if operational data is sufficient, "
        "or reports data collection criteria if historical data is limited."
    )
)
def get_model_evaluation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns transparency report regarding model evaluation, MAE/RMSE metrics,
    and operational data readiness.
    """
    return evaluate_forecasting_models(db=db)

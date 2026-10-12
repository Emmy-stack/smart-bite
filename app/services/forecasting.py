"""
AI-Powered Food Demand Forecasting Service
==========================================
Forecasts estimated food demand by NGO and food category over a customizable horizon (1-30 days).

Methodology:
- When historical donation records are insufficient (< 5 accepted/completed donations),
  uses a transparent, explainable nutritional baseline derived from:
    1. Declared NGO beneficiary count
    2. Declared food requirements (mapped against semantic category taxonomy)
    3. Standardized daily intake norms (0.45 kg/meal/beneficiary)
    4. NGO storage capacity constraints
- When historical donation records exist, empirical daily intake rates are blended
  with the beneficiary baseline using a Bayesian weighting factor.
- Distinguishes clearly between:
    - Estimated future demand (projections for planning)
    - Observed historical demand (past NGO requirements and match acceptances)
    - Actual food donations received (completed donation receipts)
- Non-negative, finite quantities are guaranteed.
- Never fabricates precision or unbacked accuracy percentages.
"""

import math
import re
import time
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.ngo import NGO
from app.models.donation import FoodDonation, DonationStatus
from app.models.match import Match, MatchStatus
from app.services.matching import CATEGORY_TAXONOMY, _find_taxonomy_group
from app.schemas.forecasting import (
    DailyCategoryDemand,
    CategoryForecastSummary,
    HistoricalDonationContext,
    ForecastExplanation,
    NGOForecastResponse,
    AggregateCategoryDemand,
    AggregateForecastResponse,
    ModelEvaluationResponse,
)

# Standard nutritional baseline per beneficiary meal (kg)
DEFAULT_PORTION_KG = 0.45

# Canonical rescue food categories
STANDARD_CATEGORIES = [
    "Cooked Meals",
    "Bakery",
    "Fresh Produce",
    "Packaged Food",
]

# Day of week demand multipliers (0 = Monday, ..., 6 = Sunday)
# Slight weekend increase for community meal programs; average is 1.0
DAY_OF_WEEK_FACTORS = {
    0: 0.95,  # Monday
    1: 0.95,  # Tuesday
    2: 0.95,  # Wednesday
    3: 1.00,  # Thursday
    4: 1.05,  # Friday
    5: 1.10,  # Saturday (community meal distributions)
    6: 1.00,  # Sunday
}

# Cache for generated forecasts: key -> (timestamp, data)
_FORECAST_CACHE: Dict[str, Tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def clear_forecast_cache() -> None:
    """Clears the in-memory forecast cache (useful for testing)."""
    global _FORECAST_CACHE
    _FORECAST_CACHE.clear()


def extract_demanded_categories(food_requirements: Optional[str]) -> List[str]:
    """
    Parses NGO food requirements string and maps it to canonical categories
    using the platform's CATEGORY_TAXONOMY.
    
    If no requirements or wildcard terms ("any", "all"), returns standard categories.
    """
    if not food_requirements or not food_requirements.strip():
        return list(STANDARD_CATEGORIES)

    req_text = food_requirements.strip()
    req_lower = req_text.lower()

    wildcards = ["any", "all", "all food", "everything", "no preference", "all food types accepted"]
    for wc in wildcards:
        if wc == req_lower or wc in req_lower:
            return list(STANDARD_CATEGORIES)

    # Split requirements by common delimiters
    items = [item.strip() for item in re.split(r"[,;/|]+", req_text) if item.strip()]
    matched_categories: List[str] = []

    for item in items:
        group_key = _find_taxonomy_group(item)
        if group_key and group_key in CATEGORY_TAXONOMY:
            canonical = CATEGORY_TAXONOMY[group_key]["canonical"]
            if canonical not in matched_categories:
                matched_categories.append(canonical)
        else:
            # Check partial matching against standard categories
            item_clean = item.lower()
            for std_cat in STANDARD_CATEGORIES:
                if std_cat.lower() in item_clean or item_clean in std_cat.lower():
                    if std_cat not in matched_categories:
                        matched_categories.append(std_cat)

    if not matched_categories:
        # Fallback if custom text didn't map to known taxonomies
        return list(STANDARD_CATEGORIES)

    return matched_categories


def get_ngo_historical_donations(
    ngo_id: int,
    db: Session
) -> Tuple[int, float, List[str], Dict[str, float]]:
    """
    Retrieves actual accepted and completed donations received by the NGO.
    
    Returns:
      (total_count, total_quantity_kg, observed_categories, category_totals)
    """
    # 1. Donations directly marked with accepted_ngo_id and completed/accepted status
    direct_donations = db.query(FoodDonation).filter(
        FoodDonation.accepted_ngo_id == ngo_id,
        FoodDonation.status.in_([
            DonationStatus.ACCEPTED,
            DonationStatus.PICKUP,
            DonationStatus.DELIVERED,
            DonationStatus.COMPLETED
        ])
    ).all()

    # 2. Also check matches where ngo_id accepted
    accepted_matches = db.query(Match).filter(
        Match.ngo_id == ngo_id,
        Match.status == MatchStatus.ACCEPTED
    ).all()

    donation_map: Dict[int, FoodDonation] = {d.id: d for d in direct_donations}
    for m in accepted_matches:
        if m.donation and m.donation.id not in donation_map:
            donation_map[m.donation.id] = m.donation

    all_accepted = list(donation_map.values())
    total_count = len(all_accepted)
    total_quantity = sum(d.quantity for d in all_accepted if d.quantity is not None)

    category_totals: Dict[str, float] = {}
    for d in all_accepted:
        cat = d.food_category
        category_totals[cat] = category_totals.get(cat, 0.0) + (d.quantity or 0.0)

    observed_categories = sorted(list(category_totals.keys()))

    return total_count, round(total_quantity, 1), observed_categories, category_totals


def calculate_category_weights(categories: List[str]) -> Dict[str, float]:
    """
    Distributes daily requirement across the demanded categories.
    If Cooked Meals is present with other categories, Cooked Meals is allocated
    50% of the volume as the staple meal, with the remaining 50% divided evenly.
    If Cooked Meals is absent or the only category, volume is divided equally.
    """
    if not categories:
        return {cat: 1.0 / len(STANDARD_CATEGORIES) for cat in STANDARD_CATEGORIES}

    if len(categories) == 1:
        return {categories[0]: 1.0}

    if "Cooked Meals" in categories:
        cooked_share = 0.50
        remaining_categories = [c for c in categories if c != "Cooked Meals"]
        remaining_share = (1.0 - cooked_share) / len(remaining_categories)
        weights = {"Cooked Meals": cooked_share}
        for c in remaining_categories:
            weights[c] = remaining_share
        return weights

    # Equal share
    equal_share = 1.0 / len(categories)
    return {c: equal_share for c in categories}


def generate_ngo_demand_forecast(
    ngo: NGO,
    days: int,
    db: Session,
    use_cache: bool = True
) -> NGOForecastResponse:
    """
    Generates a 1-to-30 day explainable food demand forecast for a single NGO.
    
    Guarantees:
    - Nonnegative, finite quantities
    - Clear distinction between observed history and future projections
    - Explicit methodology explanation and limitations
    """
    cache_key = f"ngo_{ngo.id}_days_{days}"
    now_ts = time.time()

    if use_cache and cache_key in _FORECAST_CACHE:
        cached_time, cached_result = _FORECAST_CACHE[cache_key]
        if now_ts - cached_time < CACHE_TTL_SECONDS:
            return cached_result

    # 1. Inspect historical donation receipts
    hist_count, hist_qty, hist_cats, cat_totals = get_ngo_historical_donations(ngo.id, db)
    has_sufficient_history = hist_count >= 5

    # 2. Extract categories
    demanded_categories = extract_demanded_categories(ngo.food_requirements)
    category_weights = calculate_category_weights(demanded_categories)

    # 3. Base daily demand calculation
    # Beneficiary count * daily intake standard
    beneficiary_count = max(0, ngo.beneficiary_count or 0)
    base_daily_demand = beneficiary_count * DEFAULT_PORTION_KG

    # If NGO declared capacity is greater than 0, check if daily throughput exceeds storage
    if ngo.capacity and ngo.capacity > 0:
        # Cap daily demand at storage capacity if capacity is smaller than single-day requirement
        daily_demand_cap = float(ngo.capacity)
        effective_daily_demand = min(base_daily_demand, daily_demand_cap)
    else:
        effective_daily_demand = base_daily_demand

    # 4. Method selection and blending
    if has_sufficient_history:
        method = "blended_empirical_baseline"
        data_quality_status = "historical_blend"
        # Weight given to historical average vs baseline: max 50%
        alpha = min(0.50, hist_count / 20.0)
    elif hist_count > 0:
        method = "baseline_beneficiary_demand"
        data_quality_status = "insufficient_history"
        alpha = 0.0
    else:
        method = "baseline_beneficiary_demand"
        data_quality_status = "insufficient_history"
        alpha = 0.0

    # 5. Generate daily forecasts over requested horizon
    today = datetime.now(timezone.utc).date()
    start_date = today + timedelta(days=1)
    end_date = today + timedelta(days=days)

    daily_forecasts: List[DailyCategoryDemand] = []
    category_accumulators: Dict[str, float] = {cat: 0.0 for cat in demanded_categories}

    for day_idx in range(days):
        forecast_date = start_date + timedelta(days=day_idx)
        dow_index = forecast_date.weekday()
        dow_name = forecast_date.strftime("%A")
        dow_factor = DAY_OF_WEEK_FACTORS.get(dow_index, 1.0)

        for cat in demanded_categories:
            weight = category_weights.get(cat, 0.0)
            baseline_cat_daily = effective_daily_demand * weight

            if alpha > 0 and cat in cat_totals and hist_count > 0:
                hist_avg_cat = cat_totals[cat] / float(hist_count)
                daily_estimate = (1.0 - alpha) * baseline_cat_daily + alpha * hist_avg_cat
            else:
                daily_estimate = baseline_cat_daily

            # Apply day-of-week factor
            day_adjusted = max(0.0, round(daily_estimate * dow_factor, 1))
            portions = int(round(day_adjusted / DEFAULT_PORTION_KG)) if DEFAULT_PORTION_KG > 0 else 0

            daily_forecasts.append(
                DailyCategoryDemand(
                    date=forecast_date.isoformat(),
                    day_of_week=dow_name,
                    food_category=cat,
                    estimated_quantity_kg=day_adjusted,
                    estimated_meal_portions=portions,
                )
            )
            category_accumulators[cat] += day_adjusted

    total_estimated_demand_kg = round(sum(category_accumulators.values()), 1)

    # 6. Build category summaries
    category_summaries: List[CategoryForecastSummary] = []
    for cat in demanded_categories:
        cat_total = round(category_accumulators.get(cat, 0.0), 1)
        cat_daily_avg = round(cat_total / float(days), 1) if days > 0 else 0.0
        pct = round((cat_total / total_estimated_demand_kg * 100.0), 1) if total_estimated_demand_kg > 0 else 0.0

        category_summaries.append(
            CategoryForecastSummary(
                food_category=cat,
                total_estimated_kg=cat_total,
                daily_average_kg=cat_daily_avg,
                percentage_of_total=pct,
            )
        )

    # 7. Document assumptions and data limitations
    assumptions = [
        f"Nutritional daily food intake assumed at {DEFAULT_PORTION_KG} kg per beneficiary meal.",
        f"Demand distributed across {len(demanded_categories)} demanded categories based on stated requirements.",
        "Day-of-week multipliers reflect operational community feeding patterns (weekend peak).",
    ]
    if ngo.capacity and ngo.capacity > 0 and base_daily_demand > ngo.capacity:
        assumptions.append(f"Daily forecast bounded by NGO declared storage capacity limit of {ngo.capacity} kg.")

    data_limitations = [
        "Historical donation records are limited in this deployment; estimates rely primarily on declared beneficiary counts and dietary requirements.",
        "Forecasts do not incorporate unexpected local emergency feeding surges or external third-party food supplies.",
        "Machine-learning regression models have not been trained on live production data due to insufficient historical sample volume.",
    ]

    disclaimer = (
        "These food demand forecasts are operational estimates intended solely to assist donor restaurants "
        "and platform coordinators in food surplus planning and waste reduction. They do not constitute "
        "actual NGO orders, requests, commitments, or guaranteed deliveries."
    )

    explanation = ForecastExplanation(
        method=method,
        data_quality_status=data_quality_status,
        beneficiary_count=beneficiary_count,
        declared_food_requirements=ngo.food_requirements,
        matched_categories=demanded_categories,
        daily_portion_assumption_kg=DEFAULT_PORTION_KG,
        assumptions=assumptions,
        data_limitations=data_limitations,
        disclaimer=disclaimer,
    )

    historical_context = HistoricalDonationContext(
        total_donations_received=hist_count,
        total_quantity_received_kg=hist_qty,
        observed_categories=hist_cats,
        has_sufficient_history=has_sufficient_history,
    )

    result = NGOForecastResponse(
        forecast_generated_at=datetime.now(timezone.utc),
        ngo_id=ngo.id,
        ngo_name=ngo.name,
        forecast_horizon_days=days,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_estimated_demand_kg=total_estimated_demand_kg,
        category_summaries=category_summaries,
        daily_forecasts=daily_forecasts,
        historical_context=historical_context,
        explanation=explanation,
    )

    _FORECAST_CACHE[cache_key] = (now_ts, result)
    return result


def generate_aggregate_network_forecast(
    days: int,
    db: Session,
    use_cache: bool = True
) -> AggregateForecastResponse:
    """
    Aggregates demand across all verified active NGOs for network-level donation planning.
    Does not expose individual NGOs' private records or location data.
    """
    cache_key = f"aggregate_network_days_{days}"
    now_ts = time.time()

    if use_cache and cache_key in _FORECAST_CACHE:
        cached_time, cached_result = _FORECAST_CACHE[cache_key]
        if now_ts - cached_time < CACHE_TTL_SECONDS:
            return cached_result

    ngos = db.query(NGO).all()
    active_ngos = [n for n in ngos if (n.beneficiary_count or 0) > 0 or n.food_requirements]

    total_beneficiaries = sum(n.beneficiary_count or 0 for n in active_ngos)
    category_totals: Dict[str, float] = {}
    category_ngo_counts: Dict[str, int] = {}

    today = datetime.now(timezone.utc).date()
    start_date = today + timedelta(days=1)
    end_date = today + timedelta(days=days)

    for ngo in active_ngos:
        ngo_forecast = generate_ngo_demand_forecast(ngo=ngo, days=days, db=db, use_cache=False)
        for cat_sum in ngo_forecast.category_summaries:
            cat = cat_sum.food_category
            category_totals[cat] = category_totals.get(cat, 0.0) + cat_sum.total_estimated_kg
            category_ngo_counts[cat] = category_ngo_counts.get(cat, 0) + 1

    total_network_demand = round(sum(category_totals.values()), 1)

    category_breakdown: List[AggregateCategoryDemand] = []
    for cat, total_kg in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        daily_avg = round(total_kg / float(days), 1) if days > 0 else 0.0
        pct = round((total_kg / total_network_demand * 100.0), 1) if total_network_demand > 0 else 0.0
        category_breakdown.append(
            AggregateCategoryDemand(
                food_category=cat,
                total_estimated_demand_kg=round(total_kg, 1),
                daily_average_kg=daily_avg,
                contributing_ngos_count=category_ngo_counts.get(cat, 0),
                percentage_of_network_total=pct,
            )
        )

    disclaimer = (
        "Aggregate forecasts provide high-level demand guidance across verified NGOs to aid platform "
        "coordinators and food donors. Individual NGO identities and exact locations are protected."
    )

    result = AggregateForecastResponse(
        forecast_generated_at=datetime.now(timezone.utc),
        forecast_horizon_days=days,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_network_demand_kg=total_network_demand,
        total_beneficiaries_served=total_beneficiaries,
        active_ngos_count=len(active_ngos),
        category_breakdown=category_breakdown,
        method="aggregate_baseline_demand",
        disclaimer=disclaimer,
    )

    _FORECAST_CACHE[cache_key] = (now_ts, result)
    return result


def calculate_regression_metrics(
    y_true: List[float],
    y_pred: List[float]
) -> Dict[str, float]:
    """
    Computes standard regression evaluation metrics: MAE and RMSE in pure Python.
    No heavy ML library dependencies required.
    """
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return {"mae": 0.0, "rmse": 0.0}

    n = len(y_true)
    abs_errors = [abs(yt - yp) for yt, yp in zip(y_true, y_pred)]
    sq_errors = [(yt - yp) ** 2 for yt, yp in zip(y_true, y_pred)]

    mae = sum(abs_errors) / float(n)
    rmse = math.sqrt(sum(sq_errors) / float(n))

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "sample_count": n,
    }


def evaluate_forecasting_models(db: Session) -> ModelEvaluationResponse:
    """
    Evaluates forecasting models against real operational records.
    
    If operational donation history is insufficient (< 30 completed donation records),
    honestly reports that model evaluation is not yet statistically meaningful
    and specifies the required operational data collection criteria.
    """
    completed_donations = db.query(FoodDonation).filter(
        FoodDonation.status.in_([
            DonationStatus.ACCEPTED,
            DonationStatus.PICKUP,
            DonationStatus.DELIVERED,
            DonationStatus.COMPLETED
        ])
    ).all()

    recipient_ngos = set(d.accepted_ngo_id for d in completed_donations if d.accepted_ngo_id is not None)
    sample_size = len(completed_donations)

    metrics_definitions = {
        "MAE": (
            "Mean Absolute Error: The average magnitude of prediction errors in kilograms, "
            "measuring how far predictions were from actual received quantities on average."
        ),
        "RMSE": (
            "Root Mean Squared Error: The square root of the mean squared error in kilograms, "
            "penalizing large deviations more severely than small ones."
        ),
        "Chronological_Split": (
            "Time-based training/validation partitioning that ensures models are trained on past "
            "data and tested strictly on future data, avoiding forward look-ahead leakage."
        )
    }

    data_collection_requirements = [
        "Chronological history of at least 30 to 60 days of continuous donation and distribution records.",
        "Minimum of 10+ completed donation receipts per participating NGO across multiple weeks.",
        "Regular recording of actual NGO consumption, leftovers, or unmet beneficiary requests to measure true demand.",
    ]

    MINIMUM_EVALUATION_SAMPLES = 30

    if sample_size < MINIMUM_EVALUATION_SAMPLES:
        return ModelEvaluationResponse(
            evaluation_timestamp=datetime.now(timezone.utc),
            is_evaluation_meaningful=False,
            status="insufficient_history",
            sample_size_completed_donations=sample_size,
            unique_recipient_ngos=len(recipient_ngos),
            message=(
                f"Model evaluation is not yet statistically meaningful. The operational database currently "
                f"contains only {sample_size} completed donation records across {len(recipient_ngos)} recipient "
                f"NGOs (minimum threshold for chronological validation is {MINIMUM_EVALUATION_SAMPLES} events). "
                "Baseline forecasting is active until sufficient real-world data is collected."
            ),
            data_collection_requirements=data_collection_requirements,
            metrics_definitions=metrics_definitions,
            baseline_metrics=None,
            model_comparison=None,
        )

    # If sufficient historical data exists, perform chronological split
    # Sort chronologically by created_at
    sorted_donations = sorted(completed_donations, key=lambda d: d.created_at or datetime.min)
    split_idx = int(len(sorted_donations) * 0.7)
    train_records = sorted_donations[:split_idx]
    val_records = sorted_donations[split_idx:]

    # Compute baseline predictions on validation set
    y_true = [float(d.quantity) for d in val_records]
    # Simple training mean as baseline
    train_mean = sum(float(d.quantity) for d in train_records) / max(1, len(train_records))
    y_baseline = [train_mean for _ in val_records]

    baseline_metrics = calculate_regression_metrics(y_true, y_baseline)

    return ModelEvaluationResponse(
        evaluation_timestamp=datetime.now(timezone.utc),
        is_evaluation_meaningful=True,
        status="evaluated",
        sample_size_completed_donations=sample_size,
        unique_recipient_ngos=len(recipient_ngos),
        message="Model evaluation completed using chronological train/validation split.",
        data_collection_requirements=data_collection_requirements,
        metrics_definitions=metrics_definitions,
        baseline_metrics=baseline_metrics,
        model_comparison={
            "train_samples": len(train_records),
            "validation_samples": len(val_records),
            "baseline_mean_kg": round(train_mean, 2),
            "baseline_mae": baseline_metrics["mae"],
            "baseline_rmse": baseline_metrics["rmse"],
        },
    )

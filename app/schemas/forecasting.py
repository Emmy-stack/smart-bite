from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DailyCategoryDemand(BaseModel):
    date: str = Field(..., description="Forecast date in ISO format (YYYY-MM-DD)")
    day_of_week: str = Field(..., description="Day of the week (e.g., Monday)")
    food_category: str = Field(..., description="Food category")
    estimated_quantity_kg: float = Field(..., ge=0.0, description="Estimated food demand in kilograms")
    estimated_meal_portions: int = Field(..., ge=0, description="Estimated equivalent meal portions")

class CategoryForecastSummary(BaseModel):
    food_category: str = Field(..., description="Food category")
    total_estimated_kg: float = Field(..., ge=0.0, description="Total projected demand over horizon (kg)")
    daily_average_kg: float = Field(..., ge=0.0, description="Average projected daily demand (kg)")
    percentage_of_total: float = Field(..., ge=0.0, le=100.0, description="Percentage of this NGO's total forecast demand")

class HistoricalDonationContext(BaseModel):
    total_donations_received: int = Field(..., ge=0, description="Actual completed or accepted donations recorded for this NGO")
    total_quantity_received_kg: float = Field(..., ge=0.0, description="Total historical quantity received in kg")
    observed_categories: List[str] = Field(default_factory=list, description="Categories received historically")
    has_sufficient_history: bool = Field(..., description="Whether historical events meet statistical threshold (>= 5 events)")

class ForecastExplanation(BaseModel):
    method: str = Field(..., description="Forecasting method ('baseline_beneficiary_demand', 'blended_empirical_baseline', 'insufficient_history')")
    data_quality_status: str = Field(..., description="Data quality classification ('baseline', 'insufficient_history', 'historical_blend')")
    beneficiary_count: int = Field(..., description="Declared NGO beneficiary count")
    declared_food_requirements: Optional[str] = Field(None, description="Raw declared food requirements string")
    matched_categories: List[str] = Field(..., description="Categories identified from declared requirements")
    daily_portion_assumption_kg: float = Field(..., description="Assumed intake per beneficiary (0.45 kg/meal)")
    assumptions: List[str] = Field(..., description="Key methodological assumptions")
    data_limitations: List[str] = Field(..., description="Documented data constraints and limitations")
    disclaimer: str = Field(..., description="Operational planning disclaimer")

class NGOForecastResponse(BaseModel):
    forecast_generated_at: datetime = Field(..., description="Timestamp of forecast generation")
    ngo_id: int = Field(..., description="NGO identifier")
    ngo_name: str = Field(..., description="NGO organization name")
    forecast_horizon_days: int = Field(..., ge=1, le=30, description="Forecast horizon in days")
    start_date: str = Field(..., description="Start date of forecast horizon (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date of forecast horizon (YYYY-MM-DD)")
    total_estimated_demand_kg: float = Field(..., ge=0.0, description="Total estimated demand over horizon in kg")
    category_summaries: List[CategoryForecastSummary] = Field(..., description="Aggregated category demand summaries")
    daily_forecasts: List[DailyCategoryDemand] = Field(..., description="Day-by-day and category-by-category schedule")
    historical_context: HistoricalDonationContext = Field(..., description="Observed historical donation metrics")
    explanation: ForecastExplanation = Field(..., description="Transparent methodological explanation")

class AggregateCategoryDemand(BaseModel):
    food_category: str = Field(..., description="Food category")
    total_estimated_demand_kg: float = Field(..., ge=0.0, description="Total network demand in kg")
    daily_average_kg: float = Field(..., ge=0.0, description="Daily network average in kg")
    contributing_ngos_count: int = Field(..., ge=0, description="Number of NGOs demanding this category")
    percentage_of_network_total: float = Field(..., ge=0.0, le=100.0, description="Share of total network demand")

class AggregateForecastResponse(BaseModel):
    forecast_generated_at: datetime = Field(..., description="Timestamp of forecast generation")
    forecast_horizon_days: int = Field(..., ge=1, le=30, description="Forecast horizon in days")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    total_network_demand_kg: float = Field(..., ge=0.0, description="Total projected network demand in kg")
    total_beneficiaries_served: int = Field(..., ge=0, description="Total beneficiaries across active NGOs")
    active_ngos_count: int = Field(..., ge=0, description="Number of active NGOs included in aggregate forecast")
    category_breakdown: List[AggregateCategoryDemand] = Field(..., description="Breakdown of network demand by category")
    method: str = Field(..., description="Forecasting method used")
    disclaimer: str = Field(..., description="Operational planning disclaimer")

class ModelEvaluationResponse(BaseModel):
    evaluation_timestamp: datetime = Field(..., description="Timestamp when evaluation was executed")
    is_evaluation_meaningful: bool = Field(..., description="Whether sufficient real chronological records exist for valid evaluation")
    status: str = Field(..., description="Evaluation status ('insufficient_history', 'evaluated', 'demonstration')")
    sample_size_completed_donations: int = Field(..., description="Total completed/accepted donation events in database")
    unique_recipient_ngos: int = Field(..., description="Number of distinct recipient NGOs with history")
    message: str = Field(..., description="Evaluation summary message")
    data_collection_requirements: List[str] = Field(..., description="What operational data must be logged before ML training is viable")
    metrics_definitions: Dict[str, str] = Field(..., description="Explanations of MAE and RMSE metrics")
    baseline_metrics: Optional[Dict[str, Any]] = Field(None, description="Baseline error metrics if data sufficient or demonstration")
    model_comparison: Optional[Dict[str, Any]] = Field(None, description="Comparison between baseline and regressor if available")

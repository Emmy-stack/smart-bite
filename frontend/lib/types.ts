// ==========================================
// SmartBite Domain Types & API Response Models
// Aligned with FastAPI Pydantic v2 schemas
// ==========================================

export type UserRole = "restaurant" | "ngo" | "admin";

export type DonationStatus =
  | "available"
  | "matched"
  | "accepted"
  | "pickup"
  | "delivered"
  | "completed"
  | "expired"
  | "cancelled";

export type MatchStatus = "pending" | "accepted" | "rejected" | "cancelled" | "expired";

// ---------------- User & Identity ----------------
export interface User {
  id: number;
  clerk_id?: string | null;
  name: string;
  email: string;
  phone?: string | null;
  role: UserRole;
  is_active: boolean;
  is_onboarded?: boolean;
  created_at: string;
  updated_at?: string;
}

export interface UserCreate {
  name: string;
  email: string;
  phone?: string | null;
  role: UserRole;
}

export interface AuthMeResponse {
  authenticated: boolean;
  clerk_id?: string | null;
  is_onboarded: boolean;
  email?: string | null;
  role?: UserRole | null;
  user?: User | null;
  restaurant?: Restaurant | null;
  ngo?: NGO | null;
}

export interface OnboardRestaurantRequest {
  name: string;
  restaurant_name: string;
  address: string;
  latitude: number;
  longitude: number;
  phone?: string | null;
  email?: string | null;
}

export interface OnboardNGORequest {
  name: string;
  ngo_name: string;
  address: string;
  latitude: number;
  longitude: number;
  beneficiary_count: number;
  food_requirements?: string | null;
  capacity?: number | null;
  pickup_available?: boolean;
  email?: string | null;
}

// ---------------- Restaurant Profile ----------------
export interface Restaurant {
  id: number;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  phone?: string | null;
  user_id?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface RestaurantCreate {
  name: string;
  address: string;
  latitude: number;
  longitude: number;
}

// ---------------- NGO Profile ----------------
export interface NGO {
  id: number;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  beneficiary_count: number;
  food_requirements?: string | null;
  capacity?: number | null;
  pickup_available: boolean;
  user_id?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface NGOCreate {
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  beneficiary_count: number;
  food_requirements?: string | null;
  capacity?: number | null;
  pickup_available?: boolean;
}

// ---------------- Food Donations ----------------
export interface FoodDonation {
  id: number;
  restaurant_id?: number | null;
  food_name: string;
  food_category: string;
  quantity: number;
  prepared_at?: string | null;
  available_until: string;
  storage_method?: string | null;
  pickup_available: boolean;
  status: DonationStatus;
  accepted_ngo_id?: number | null;
  created_at: string;
}

export interface FoodDonationCreate {
  food_name: string;
  food_category: string;
  quantity: number;
  available_until: string;
  prepared_at?: string | null;
  storage_method?: string | null;
  pickup_available?: boolean;
  restaurant_id?: number | null;
}

export interface DonationStatusUpdate {
  status: DonationStatus;
}

// ---------------- Matching & Offers ----------------
export interface NGOMatchResult {
  ngo_id: number;
  ngo_name: string;
  ngo_address: string;
  match_score: number; // 0 - 100
  match_tier: string;  // "Excellent", "Good", "Fair", "Low"
  distance_km: number;
  distance_score: number;
  urgency_score: number;
  food_compatibility_score: number;
  demand_score: number;
  quantity_score: number;
  logistics_score: number;
  reliability_score: number;
  estimated_people_served: number;
  matched_requirement?: string | null;
  pickup_available: boolean;
}

export interface DonationMatchResponse {
  donation_id: number;
  food_name: string;
  food_category: string;
  quantity: number;
  restaurant_id: number;
  restaurant_name: string;
  restaurant_address: string;
  available_until: string;
  hours_remaining: number;
  total_ngos_evaluated: number;
  matches_returned: number;
  matches: NGOMatchResult[];
}

export interface MatchOfferResponse {
  id: number;
  donation_id: number;
  ngo_id: number;
  match_score: number;
  status: MatchStatus;
  created_at: string;
  updated_at?: string | null;
  responded_at?: string | null;
  food_name?: string | null;
  food_category?: string | null;
  quantity?: number | null;
  available_until?: string | null;
  restaurant_name?: string | null;
  restaurant_address?: string | null;
  ngo_name?: string | null;
  ngo_address?: string | null;
}

export interface DonationMatchesListResponse {
  donation_id: number;
  donation_status: string;
  accepted_ngo_id?: number | null;
  accepted_ngo_name?: string | null;
  total_offers: number;
  offers: MatchOfferResponse[];
}

export interface MatchActionResponse {
  message: string;
  match: MatchOfferResponse;
  donation_status: string;
}

export interface BatchOfferRequest {
  top_k?: number;
  min_score?: number;
}

// ---------------- Demand Forecasting ----------------
export interface AggregateCategoryDemand {
  food_category: string;
  total_estimated_demand_kg: number;
  daily_average_kg: number;
  contributing_ngos_count: number;
  percentage_of_network_total: number;
}

export interface AggregateForecastResponse {
  forecast_generated_at: string;
  forecast_horizon_days: number;
  start_date: string;
  end_date: string;
  total_network_demand_kg: number;
  total_beneficiaries_served: number;
  active_ngos_count: number;
  category_breakdown: AggregateCategoryDemand[];
  method: string;
  disclaimer: string;
}

export interface DailyCategoryDemand {
  date: string;
  day_of_week: string;
  food_category: string;
  estimated_quantity_kg: number;
  estimated_meal_portions: number;
}

export interface CategoryForecastSummary {
  food_category: string;
  total_estimated_kg: number;
  daily_average_kg: number;
  percentage_of_total: number;
}

export interface HistoricalDonationContext {
  total_donations_received: number;
  total_quantity_received_kg: number;
  observed_categories: string[];
  has_sufficient_history: boolean;
}

export interface ForecastExplanation {
  method: string;
  data_quality_status: string;
  beneficiary_count: number;
  declared_food_requirements?: string | null;
  matched_categories: string[];
  daily_portion_assumption_kg: number;
  assumptions: string[];
  data_limitations: string[];
  disclaimer: string;
}

export interface NGOForecastResponse {
  forecast_generated_at: string;
  ngo_id: number;
  ngo_name: string;
  forecast_horizon_days: number;
  start_date: string;
  end_date: string;
  total_estimated_demand_kg: number;
  category_summaries: CategoryForecastSummary[];
  daily_forecasts: DailyCategoryDemand[];
  historical_context: HistoricalDonationContext;
  explanation: ForecastExplanation;
}

export interface ModelEvaluationResponse {
  evaluation_timestamp: string;
  is_evaluation_meaningful: boolean;
  status: string;
  sample_size_completed_donations: number;
  unique_recipient_ngos: number;
  message: string;
  data_collection_requirements: string[];
  metrics_definitions: Record<string, string>;
  baseline_metrics?: Record<string, unknown> | null;
  model_comparison?: Record<string, unknown> | null;
}

// ---------------- Health Check ----------------
export interface HealthCheckResponse {
  status: "healthy" | "degraded";
  database: string;
}

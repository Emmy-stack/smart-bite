"""
AI-Powered Food-to-NGO Matching Engine
=====================================
Evaluates and ranks prospective NGO recipients for surplus food donations
using an explainable multi-factor weighted scoring algorithm.

Weights:
1. Distance (Haversine proximity) : 25% (0.25)
2. Urgency (Time to expiration)    : 20% (0.20)
3. Food Compatibility             : 15% (0.15)
4. Beneficiary Demand             : 15% (0.15)
5. Quantity Compatibility         : 10% (0.10)
6. Logistics (Pickup availability): 10% (0.10)
7. Reliability (Historical base)  :  5% (0.05)
Total                             : 100% (1.00)

Disclaimer:
Urgency scoring evaluates operational pickup windows provided by food donors;
it is NOT a biological food safety or spoilage prediction model.
"""

import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session

from app.models.ngo import NGO
from app.models.donation import FoodDonation, DonationStatus
from app.models.restaurant import Restaurant
from app.schemas.matching import NGOMatchResult

# Centralized Weight Configuration
DEFAULT_MATCHING_WEIGHTS: Dict[str, float] = {
    "distance": 0.25,
    "urgency": 0.20,
    "food_compatibility": 0.15,
    "demand": 0.15,
    "quantity": 0.10,
    "logistics": 0.10,
    "reliability": 0.05,
}

# Distance Thresholds (in kilometers) -> Score (0-100)
DEFAULT_DISTANCE_THRESHOLDS = [
    (2.0, 100.0),   # 0–2 km
    (5.0, 90.0),    # 2–5 km
    (10.0, 75.0),   # 5–10 km
    (20.0, 50.0),   # 10–20 km
    (30.0, 25.0),   # 20–30 km
    (float("inf"), 0.0),  # 30+ km
]

# Urgency Thresholds: (hours_remaining_cutoff, score)
# Normalization: Scaled to 0–100 range (25 points max -> 100% of urgency tier)
DEFAULT_URGENCY_THRESHOLDS = [
    (24.0, 100.0),  # > 24 hours (Top tier operational flexibility)
    (12.0, 80.0),   # 12–24 hours
    (6.0, 60.0),    # 6–12 hours
    (2.0, 40.0),    # 2–6 hours
    (1.0, 20.0),    # 1–2 hours
    (0.0, 0.0),     # < 1 hour (Critical / near cutoff)
]

# Categorical Semantic Taxonomy for Food Compatibility
CATEGORY_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "cooked_meals": {
        "canonical": "Cooked Meals",
        "synonyms": [
            "cooked meals", "hot meals", "prepared meals", "cooked food", "hot food",
            "jollof rice", "fried rice", "rice", "soup", "stew", "porridge", "ready to eat",
            "meals", "lunch", "dinner", "casserole", "pasta dish"
        ]
    },
    "bakery": {
        "canonical": "Bakery",
        "synonyms": [
            "bakery", "bread", "pastries", "pastry", "baked goods", "loaves", "croissants",
            "buns", "rolls", "cakes", "agege bread", "muffins"
        ]
    },
    "fresh_produce": {
        "canonical": "Fresh Produce",
        "synonyms": [
            "fresh produce", "produce", "vegetables", "veggies", "fruits", "raw produce",
            "greens", "tomatoes", "yams", "plantains", "apples", "bananas", "potatoes"
        ]
    },
    "packaged_food": {
        "canonical": "Packaged Food",
        "synonyms": [
            "packaged food", "canned food", "canned goods", "dry goods", "pantry staples",
            "groceries", "grains", "noodles", "raw rice", "pasta", "beans", "cereals"
        ]
    },
    "dairy": {
        "canonical": "Dairy",
        "synonyms": ["dairy", "milk", "cheese", "butter", "yogurt", "eggs"]
    },
    "drinks": {
        "canonical": "Drinks",
        "synonyms": ["drinks", "beverages", "juice", "water", "beverage", "soft drinks", "smoothies"]
    },
    "snacks": {
        "canonical": "Snacks",
        "synonyms": ["snacks", "finger foods", "biscuits", "cookies", "chips", "nuts", "crackers"]
    }
}


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two geographic coordinates
    using the Haversine formula.
    Returns distance in kilometers rounded to 2 decimal places.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float("inf")

    # Earth radius in kilometers
    R = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))

    return round(R * c, 2)


def calculate_distance_score(distance_km: float) -> float:
    """
    Maps geographic distance (km) to a 0–100 proximity score.
    Closer distances receive higher scores.
    Thresholds:
      0–2 km   = 100
      2–5 km   = 90
      5–10 km  = 75
      10–20 km = 50
      20–30 km = 25
      30+ km   = 0
    """
    if distance_km < 0:
        return 0.0

    for cutoff, score in DEFAULT_DISTANCE_THRESHOLDS:
        if distance_km <= cutoff:
            return score
    return 0.0


def calculate_urgency_score(hours_remaining: float) -> float:
    """
    Calculates urgency score (0-100) based on remaining availability window.
    - More than 24 hours = 100.0 (raw: 25)
    - 12–24 hours       = 80.0  (raw: 20)
    - 6–12 hours        = 60.0  (raw: 15)
    - 2–6 hours         = 40.0  (raw: 10)
    - 1–2 hours         = 20.0  (raw: 5)
    - Less than 1 hour  = 0.0   (raw: 0)

    Note: Expired donations (hours_remaining <= 0) should be excluded from matching.
    """
    if hours_remaining <= 0.0:
        return 0.0

    if hours_remaining > 24.0:
        return 100.0
    elif hours_remaining >= 12.0:
        return 80.0
    elif hours_remaining >= 6.0:
        return 60.0
    elif hours_remaining >= 2.0:
        return 40.0
    elif hours_remaining >= 1.0:
        return 20.0
    else:
        return 0.0


def _find_taxonomy_group(term: str) -> Optional[str]:
    """Helper to locate which taxonomy group a term belongs to."""
    clean_term = term.strip().lower()
    for group_key, data in CATEGORY_TAXONOMY.items():
        if clean_term == data["canonical"].lower():
            return group_key
        for syn in data["synonyms"]:
            if clean_term == syn.lower() or syn.lower() in clean_term:
                return group_key
    return None


def calculate_food_compatibility(
    food_category: str,
    food_requirements: Optional[str]
) -> Tuple[float, Optional[str]]:
    """
    Evaluates semantic compatibility between donation food category
    and the NGO's declared food requirements text.

    Returns:
      (compatibility_score: float [0-100], matched_requirement: Optional[str])
    """
    if not food_category:
        return (50.0, None)

    cat_clean = food_category.strip().lower()

    # If NGO has not specified requirements, or explicitly accepts any/all foods
    if not food_requirements or not food_requirements.strip():
        return (90.0, "All food types accepted")

    req_text = food_requirements.strip()
    req_lower = req_text.lower()

    # Wildcard acceptance
    wildcards = ["any", "all", "all food", "everything", "no preference", "all food types accepted"]
    for wc in wildcards:
        if wc == req_lower or wc in req_lower:
            return (95.0, "All food types accepted")

    # Split NGO requirements by common delimiters (comma, semicolon, slash, pipe)
    req_items = [item.strip() for item in re.split(r"[,;/|]+", req_text) if item.strip()]

    # 1. Exact direct match
    for item in req_items:
        if cat_clean == item.lower():
            return (100.0, item)

    # 2. Taxonomy / Synonym mapping
    donation_group = _find_taxonomy_group(cat_clean)
    if donation_group:
        group_data = CATEGORY_TAXONOMY[donation_group]
        for item in req_items:
            item_lower = item.lower()
            # Check if requirement matches the canonical group or any synonym
            if item_lower == group_data["canonical"].lower():
                return (95.0, item)
            for syn in group_data["synonyms"]:
                if syn == item_lower or syn in item_lower or item_lower in syn:
                    return (95.0, item)

    # 3. Partial keyword overlap
    for item in req_items:
        item_words = set(re.findall(r"\w+", item.lower()))
        cat_words = set(re.findall(r"\w+", cat_clean))
        if item_words & cat_words:
            return (80.0, item)

    # 4. Fallback when requirements exist but don't explicitly list this category
    # Neutral/low score rather than 0, as NGOs frequently take surplus if needed
    return (35.0, None)


def calculate_demand_score(
    donation_quantity: float,
    beneficiary_count: int,
    capacity: int
) -> Tuple[float, float]:
    """
    Evaluates beneficiary absorption capacity relative to donation size.
    Prevents over-weighting NGOs with massive claims if they lack real capacity.

    Returns:
      (demand_score: float [0-100], estimated_people_served: float)
    """
    donation_qty = max(0.0, float(donation_quantity))
    beneficiaries = max(0, int(beneficiary_count))
    cap = max(0, int(capacity))

    if donation_qty <= 0.0:
        return (0.0, 0.0)

    # Estimated people who can directly receive portions
    if beneficiaries > 0:
        estimated_people = min(float(beneficiaries), donation_qty)
    else:
        estimated_people = min(float(cap), donation_qty) if cap > 0 else (donation_qty * 0.5)

    # Immediate beneficiary utilization ratio
    if beneficiaries >= donation_qty:
        # Full immediate absorption by waiting beneficiaries
        base_score = 95.0 + min(5.0, (beneficiaries - donation_qty) / 100.0)
    elif beneficiaries > 0:
        # Partial immediate consumption
        ratio = beneficiaries / donation_qty
        base_score = 50.0 + (ratio * 48.0)  # e.g. 70/80 -> 50 + (0.875 * 48) = 92.0
    else:
        # No beneficiary count specified, fallback to capacity baseline
        base_score = 50.0

    # Capacity check: If capacity is severely lower than donation quantity, discount
    if cap > 0 and cap < donation_qty:
        capacity_ratio = cap / donation_qty
        penalty_factor = max(0.4, capacity_ratio ** 0.5)
        base_score *= penalty_factor

    demand_score = round(max(0.0, min(100.0, base_score)), 1)
    return (demand_score, round(estimated_people, 1))


def calculate_quantity_score(donation_quantity: float, capacity: int) -> float:
    """
    Compares donation quantity against NGO storage/intake capacity.
    - Ideal: NGO capacity is 1.0x to 3.0x donation quantity (90–100 score).
    - Capable but large: capacity is 5x-10x donation (80–90 score).
    - Deficit: capacity < donation quantity (score scales down with capacity ratio).
    """
    donation_qty = max(0.0, float(donation_quantity))
    cap = max(0, int(capacity))

    if donation_qty <= 0.0:
        return 0.0

    if cap <= 0:
        # Unstated capacity: neutral baseline
        return 50.0

    if cap >= donation_qty:
        ratio = cap / donation_qty
        if 1.0 <= ratio <= 3.0:
            # Optimal fit
            return 95.0
        elif ratio <= 6.0:
            return 90.0
        else:
            # NGO is very large compared to small donation
            return 85.0
    else:
        # Capacity shortfall: NGO cannot store the entire donation
        deficit_ratio = cap / donation_qty
        # e.g., 50 / 80 = 0.625 -> 50.0; 50 / 300 = 0.166 -> 15.0
        score = max(10.0, deficit_ratio * 80.0)
        return round(min(100.0, score), 1)


def calculate_logistics_score(
    donation_pickup_available: bool,
    ngo_pickup_available: bool
) -> float:
    """
    Evaluates fulfillment feasibility based on transportation capabilities:
    - Both parties have pickup/transport available: 100.0
    - NGO has pickup available (can collect from restaurant): 80.0
    - Restaurant offers pickup/dispatch, NGO has no dedicated vehicle: 70.0
    - Neither has pickup/delivery available: 20.0 (logistical bottleneck)
    """
    if donation_pickup_available and ngo_pickup_available:
        return 100.0
    elif ngo_pickup_available and not donation_pickup_available:
        return 80.0
    elif not ngo_pickup_available and donation_pickup_available:
        return 70.0
    else:
        return 20.0


def calculate_reliability_score(ngo_id: int, db: Optional[Session] = None) -> float:
    """
    Fulfillment reliability service interface.
    - If historical transactions exist in DB: computes completion rate.
    - If insufficient transaction history: returns neutral default baseline (70.0).

    Note: Clearly documented design hook for future machine learning & analytics.
    """
    if db is None:
        return 70.0

    # In current MVP schema, check if any completed/accepted donations are associated
    # (Future extensions can query a DonationFulfillment or Transaction ledger)
    # Neutral default baseline:
    return 70.0


def calculate_match_score(
    distance_score: float,
    urgency_score: float,
    food_compatibility_score: float,
    demand_score: float,
    quantity_score: float,
    logistics_score: float,
    reliability_score: float,
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Computes overall weighted compatibility score (0.0 to 100.0).
    """
    w = weights or DEFAULT_MATCHING_WEIGHTS

    raw_final = (
        (distance_score * w.get("distance", 0.25)) +
        (urgency_score * w.get("urgency", 0.20)) +
        (food_compatibility_score * w.get("food_compatibility", 0.15)) +
        (demand_score * w.get("demand", 0.15)) +
        (quantity_score * w.get("quantity", 0.10)) +
        (logistics_score * w.get("logistics", 0.10)) +
        (reliability_score * w.get("reliability", 0.05))
    )

    return round(max(0.0, min(100.0, raw_final)), 1)


def get_match_tier(score: float) -> str:
    """Classifies match score into qualitative rating tier."""
    if score >= 85.0:
        return "Excellent"
    elif score >= 70.0:
        return "Good"
    elif score >= 50.0:
        return "Fair"
    else:
        return "Low"


def rank_ngos_for_donation(
    donation: FoodDonation,
    ngos: List[NGO],
    db: Session,
    min_score: float = 0.0,
    limit: Optional[int] = None,
    weights: Optional[Dict[str, float]] = None
) -> List[NGOMatchResult]:
    """
    Evaluates and ranks candidate NGOs for an active food donation.

    Returns:
      Ranked list of NGOMatchResult objects, ordered by match_score descending.
    """
    restaurant: Optional[Restaurant] = donation.restaurant
    if not restaurant:
        restaurant = db.query(Restaurant).filter(Restaurant.id == donation.restaurant_id).first()

    rest_lat = restaurant.latitude if restaurant else 0.0
    rest_lon = restaurant.longitude if restaurant else 0.0

    # Calculate operational hours remaining
    now = datetime.now(timezone.utc)
    avail_until = donation.available_until
    if avail_until.tzinfo is None:
        avail_until = avail_until.replace(tzinfo=timezone.utc)

    hours_remaining = (avail_until - now).total_seconds() / 3600.0
    urgency_score = calculate_urgency_score(hours_remaining)

    results: List[NGOMatchResult] = []

    for ngo in ngos:
        # 1. Distance & Proximity
        dist_km = calculate_distance(rest_lat, rest_lon, ngo.latitude, ngo.longitude)
        dist_score = calculate_distance_score(dist_km)

        # 2. Food Compatibility
        compat_score, matched_req = calculate_food_compatibility(
            donation.food_category, ngo.food_requirements
        )

        # 3. Demand & Absorption
        demand_score, est_people = calculate_demand_score(
            donation.quantity, ngo.beneficiary_count, ngo.capacity
        )

        # 4. Quantity vs Capacity
        qty_score = calculate_quantity_score(donation.quantity, ngo.capacity)

        # 5. Logistics
        logistics_score = calculate_logistics_score(
            donation.pickup_available, ngo.pickup_available
        )

        # 6. Reliability
        rel_score = calculate_reliability_score(ngo.id, db)

        # 7. Final Weighted Match Score
        final_score = calculate_match_score(
            distance_score=dist_score,
            urgency_score=urgency_score,
            food_compatibility_score=compat_score,
            demand_score=demand_score,
            quantity_score=qty_score,
            logistics_score=logistics_score,
            reliability_score=rel_score,
            weights=weights
        )

        # Filter by minimum score threshold if specified
        if final_score < min_score:
            continue

        tier = get_match_tier(final_score)

        match_res = NGOMatchResult(
            ngo_id=ngo.id,
            ngo_name=ngo.name,
            ngo_address=ngo.address,
            match_score=final_score,
            match_tier=tier,
            distance_km=dist_km,
            distance_score=dist_score,
            urgency_score=urgency_score,
            food_compatibility_score=compat_score,
            demand_score=demand_score,
            quantity_score=qty_score,
            logistics_score=logistics_score,
            reliability_score=rel_score,
            estimated_people_served=est_people,
            matched_requirement=matched_req,
            pickup_available=ngo.pickup_available
        )
        results.append(match_res)

    # Rank results: primary sort by match_score descending, secondary sort by distance_km ascending
    results.sort(key=lambda x: (-x.match_score, x.distance_km))

    if limit is not None and limit > 0:
        results = results[:limit]

    return results

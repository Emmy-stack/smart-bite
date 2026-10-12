import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import engine, Base, SessionLocal
from app.models import Restaurant, NGO, FoodDonation, DonationStatus
from app.services.matching import (
    DEFAULT_MATCHING_WEIGHTS,
    calculate_distance,
    calculate_distance_score,
    calculate_urgency_score,
    calculate_food_compatibility,
    calculate_demand_score,
    calculate_quantity_score,
    calculate_logistics_score,
    calculate_reliability_score,
    calculate_match_score,
    get_match_tier,
    rank_ngos_for_donation,
)

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def init_db():
    Base.metadata.create_all(bind=engine)
    yield

# ==============================================================
# 1. UNIT TESTS: INDIVIDUAL SCORING CRITERIA
# ==============================================================

def test_distance_calculation():
    # Same coordinate should be 0.0 km
    assert calculate_distance(6.5954, 3.3431, 6.5954, 3.3431) == 0.0

    # Ikeja (6.5954, 3.3431) to Maryland, Lagos (6.5722, 3.3686) is approximately 3.8 km
    dist = calculate_distance(6.5954, 3.3431, 6.5722, 3.3686)
    assert 3.5 <= dist <= 4.2

    # Ikeja to Victoria Island, Lagos (6.4281, 3.4219) is approximately 20-22 km
    dist_vi = calculate_distance(6.5954, 3.3431, 6.4281, 3.4219)
    assert 18.0 <= dist_vi <= 23.0

def test_distance_scoring():
    assert calculate_distance_score(1.2) == 100.0   # 0–2 km
    assert calculate_distance_score(2.0) == 100.0   # boundary
    assert calculate_distance_score(3.5) == 90.0    # 2–5 km
    assert calculate_distance_score(5.0) == 90.0    # boundary
    assert calculate_distance_score(8.0) == 75.0    # 5–10 km
    assert calculate_distance_score(15.0) == 50.0   # 10–20 km
    assert calculate_distance_score(25.0) == 25.0   # 20–30 km
    assert calculate_distance_score(35.0) == 0.0    # 30+ km
    assert calculate_distance_score(-5.0) == 0.0    # invalid negative

def test_urgency_scoring():
    # More than 24 hours
    assert calculate_urgency_score(30.0) == 100.0
    # 12–24 hours
    assert calculate_urgency_score(18.0) == 80.0
    assert calculate_urgency_score(12.0) == 80.0
    # 6–12 hours
    assert calculate_urgency_score(8.0) == 60.0
    assert calculate_urgency_score(6.0) == 60.0
    # 2–6 hours
    assert calculate_urgency_score(3.5) == 40.0
    assert calculate_urgency_score(2.0) == 40.0
    # 1–2 hours
    assert calculate_urgency_score(1.5) == 20.0
    assert calculate_urgency_score(1.0) == 20.0
    # Less than 1 hour
    assert calculate_urgency_score(0.5) == 0.0
    # Expired / negative
    assert calculate_urgency_score(0.0) == 0.0
    assert calculate_urgency_score(-2.0) == 0.0

def test_food_compatibility():
    # Exact match
    score, matched = calculate_food_compatibility("Bakery", "Fresh produce, Bakery, Dairy")
    assert score == 100.0
    assert matched == "Bakery"

    # Semantic synonym match: "Cooked Meals" matches "Hot meals"
    score, matched = calculate_food_compatibility("Cooked Meals", "Fresh produce, Bread, Hot meals")
    assert score == 90.0 or score == 95.0
    assert matched == "Hot meals"

    # Semantic synonym match: "Agege Bread" matches Bakery group
    score, matched = calculate_food_compatibility("Bakery", "Agege bread, Fruit")
    assert score >= 90.0

    # Wildcard / All food accepted
    score, matched = calculate_food_compatibility("Prepared Food", "All food types accepted")
    assert score >= 90.0
    assert "All food" in matched

    # Empty NGO requirements implies willingness to accept any surplus
    score, matched = calculate_food_compatibility("Cooked Meals", None)
    assert score >= 90.0

    # Non-matching category
    score, matched = calculate_food_compatibility("Drinks", "Cooked Meals, Bakery")
    assert score < 50.0

def test_demand_scoring():
    # Case A: Donation = 80 meals, NGO beneficiaries = 100 (can absorb 100% of donation)
    score_a, people_a = calculate_demand_score(donation_quantity=80.0, beneficiary_count=100, capacity=120)
    assert score_a >= 95.0
    assert people_a == 80.0

    # Case B: Donation = 80 meals, NGO beneficiaries = 70 (high utilization)
    score_b, people_b = calculate_demand_score(donation_quantity=80.0, beneficiary_count=70, capacity=100)
    assert 85.0 <= score_b <= 95.0
    assert people_b == 70.0

    # Case C: Donation = 80 meals, NGO beneficiaries = 10 (low utilization)
    score_c, people_c = calculate_demand_score(donation_quantity=80.0, beneficiary_count=10, capacity=20)
    assert score_c < 55.0
    assert people_c == 10.0

def test_quantity_scoring():
    # Optimal fit: capacity is 1x - 3x donation quantity
    score_opt = calculate_quantity_score(donation_quantity=80.0, capacity=100)
    assert score_opt >= 90.0

    # Excess capacity: NGO is 10x larger than donation (still handles easily)
    score_large = calculate_quantity_score(donation_quantity=50.0, capacity=500)
    assert score_large >= 85.0

    # Deficit: NGO capacity is lower than donation
    score_deficit = calculate_quantity_score(donation_quantity=300.0, capacity=50)
    assert score_deficit < 30.0

def test_logistics_scoring():
    assert calculate_logistics_score(True, True) == 100.0
    assert calculate_logistics_score(False, True) == 80.0
    assert calculate_logistics_score(True, False) == 70.0
    assert calculate_logistics_score(False, False) == 20.0

def test_final_weighted_score():
    # Perfect scores across all 7 factors
    score = calculate_match_score(
        distance_score=100.0,
        urgency_score=100.0,
        food_compatibility_score=100.0,
        demand_score=100.0,
        quantity_score=100.0,
        logistics_score=100.0,
        reliability_score=100.0,
    )
    assert score == 100.0

    # Test formula with example from specification:
    # distance: 100, urgency: 80, food: 95, demand: 92, qty: 90, log: 100, rel: 70
    score_ex = calculate_match_score(
        distance_score=100.0,
        urgency_score=80.0,
        food_compatibility_score=95.0,
        demand_score=92.0,
        quantity_score=90.0,
        logistics_score=100.0,
        reliability_score=70.0,
    )
    # Expected: (100*0.25) + (80*0.20) + (95*0.15) + (92*0.15) + (90*0.10) + (100*0.10) + (70*0.05)
    # = 25.0 + 16.0 + 14.25 + 13.80 + 9.0 + 10.0 + 3.5 = 91.55 -> 91.6
    assert 90.0 <= score_ex <= 93.0
    assert get_match_tier(score_ex) == "Excellent"

def test_match_tiers():
    assert get_match_tier(95.0) == "Excellent"
    assert get_match_tier(85.0) == "Excellent"
    assert get_match_tier(84.9) == "Good"
    assert get_match_tier(70.0) == "Good"
    assert get_match_tier(65.0) == "Fair"
    assert get_match_tier(50.0) == "Fair"
    assert get_match_tier(45.0) == "Low"

# ==============================================================
# 2. INTEGRATION TESTS: LAGOS NIGERIA REALISTIC SCENARIO
# ==============================================================

def test_matching_endpoint_lagos_scenario():
    """
    Realistic Lagos Scenario:
    Restaurant: 'Green Bowl Kitchen' in Ikeja (lat: 6.5954, lon: 3.3431)
    Donation: 80 portions of Jollof Rice & Chicken (Cooked Meals, available for 14 hours)

    NGOs:
    1. 'Hope Community Foundation', Ikeja (~1.1 km, capacity: 100, needs: Hot meals) -> TOP MATCH
    2. 'Food Support Initiative', Maryland (~3.8 km, capacity: 150, needs: Cooked meals) -> STRONG MATCH
    3. 'Lagos Food Relief Network', Yaba (~10.0 km, capacity: 300, needs: All food) -> GOOD MATCH
    4. 'Island Charity Mission', Lekki (~21.5 km, capacity: 20, needs: Snacks only) -> LOW MATCH
    """
    db = SessionLocal()
    try:
        # Create Restaurant in Ikeja
        restaurant = Restaurant(
            name="Green Bowl Kitchen",
            address="15 Allen Avenue, Ikeja, Lagos",
            latitude=6.5954,
            longitude=3.3431
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)

        # Create NGOs across Lagos
        ngo_ikeja = NGO(
            name="Hope Community Foundation",
            address="2 Oba Akran Way, Ikeja, Lagos",
            latitude=6.6018,
            longitude=3.3515,
            beneficiary_count=70,
            food_requirements="Fresh produce, Bread, Hot meals",
            capacity=100,
            pickup_available=True
        )
        ngo_maryland = NGO(
            name="Food Support Initiative",
            address="45 Ikorodu Road, Maryland, Lagos",
            latitude=6.5722,
            longitude=3.3686,
            beneficiary_count=120,
            food_requirements="Cooked Meals, Rice, Grains",
            capacity=150,
            pickup_available=True
        )
        ngo_yaba = NGO(
            name="Lagos Food Relief Network",
            address="12 Commercial Avenue, Yaba, Lagos",
            latitude=6.5095,
            longitude=3.3711,
            beneficiary_count=200,
            food_requirements="All food types accepted",
            capacity=300,
            pickup_available=False
        )
        ngo_lekki = NGO(
            name="Island Charity Mission",
            address="8 Admiralty Way, Lekki Phase 1, Lagos",
            latitude=6.4474,
            longitude=3.4731,
            beneficiary_count=15,
            food_requirements="Packaged Snacks, Bottled Water only",
            capacity=25,
            pickup_available=False
        )
        db.add_all([ngo_ikeja, ngo_maryland, ngo_yaba, ngo_lekki])
        db.commit()

        # Create Active Donation: Jollof Rice (Cooked Meals, available for 14 hours)
        avail = datetime.now(timezone.utc) + timedelta(hours=14)
        donation = FoodDonation(
            restaurant_id=restaurant.id,
            food_name="80 portions of Jollof Rice & Chicken",
            food_category="Cooked Meals",
            quantity=80.0,
            available_until=avail,
            storage_method="insulated containers",
            pickup_available=True,
            status=DonationStatus.AVAILABLE
        )
        db.add(donation)
        db.commit()
        db.refresh(donation)

        # Save IDs for verification
        ikeja_id = ngo_ikeja.id
        maryland_id = ngo_maryland.id
        yaba_id = ngo_yaba.id
        lekki_id = ngo_lekki.id
        donation_id = donation.id
    finally:
        db.close()

    # Call Matching API with limit=50 so all evaluated NGOs are returned
    response = client.get(f"/matches/donation/{donation_id}?limit=50")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["donation_id"] == donation_id
    assert data["food_name"] == "80 portions of Jollof Rice & Chicken"
    assert data["quantity"] == 80.0
    assert data["restaurant_name"] == "Green Bowl Kitchen"
    assert data["hours_remaining"] >= 13.0
    assert len(data["matches"]) >= 4

    # Verify scores are monotonically descending
    scores = [m["match_score"] for m in data["matches"]]
    assert scores == sorted(scores, reverse=True)

    # Locate our specific test NGOs by ID
    m_ikeja = next(m for m in data["matches"] if m["ngo_id"] == ikeja_id)
    m_maryland = next(m for m in data["matches"] if m["ngo_id"] == maryland_id)
    m_yaba = next(m for m in data["matches"] if m["ngo_id"] == yaba_id)
    m_lekki = next(m for m in data["matches"] if m["ngo_id"] == lekki_id)

    # Verify Relative Ranking:
    # Hope (Ikeja, 1.1km) > Maryland (3.8km) > Yaba (10km) > Lekki (21.5km, mismatched food)
    assert m_ikeja["match_score"] > m_maryland["match_score"]
    assert m_maryland["match_score"] > m_yaba["match_score"]
    assert m_yaba["match_score"] > m_lekki["match_score"]

    # Verify Hope Community Foundation is an Excellent match and closest
    assert m_ikeja["match_tier"] == "Excellent"
    assert m_ikeja["match_score"] >= 90.0
    assert m_ikeja["distance_km"] <= 2.0
    assert m_ikeja["distance_score"] == 100.0
    assert m_ikeja["matched_requirement"] == "Hot meals"
    assert m_ikeja["estimated_people_served"] == 70.0

    # Lekki NGO should be penalized for high distance (~21.5km) and mismatched category
    assert m_lekki["distance_km"] > 18.0
    assert m_lekki["food_compatibility_score"] < 50.0
    assert m_lekki["match_score"] < m_ikeja["match_score"] - 20.0

def test_expired_donation_handling():
    """Expired donations must be rejected with 400 Bad Request."""
    db = SessionLocal()
    try:
        rest = db.query(Restaurant).first()
        # Create expired donation (expired 2 hours ago)
        expired_donation = FoodDonation(
            restaurant_id=rest.id,
            food_name="Leftover Salads",
            food_category="Fresh Produce",
            quantity=15.0,
            available_until=datetime.now(timezone.utc) - timedelta(hours=2),
            pickup_available=True,
            status=DonationStatus.AVAILABLE
        )
        db.add(expired_donation)
        db.commit()
        db.refresh(expired_donation)
        expired_id = expired_donation.id
    finally:
        db.close()

    res = client.get(f"/matches/donation/{expired_id}")
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()

def test_completed_donation_handling():
    """Completed/Cancelled donations must be rejected with 400 Bad Request."""
    db = SessionLocal()
    try:
        rest = db.query(Restaurant).first()
        closed_donation = FoodDonation(
            restaurant_id=rest.id,
            food_name="Claimed Pastries",
            food_category="Bakery",
            quantity=20.0,
            available_until=datetime.now(timezone.utc) + timedelta(hours=5),
            pickup_available=True,
            status=DonationStatus.COMPLETED
        )
        db.add(closed_donation)
        db.commit()
        db.refresh(closed_donation)
        closed_id = closed_donation.id
    finally:
        db.close()

    res = client.get(f"/matches/donation/{closed_id}")
    assert res.status_code == 400
    assert "ineligible" in res.json()["detail"].lower()

def test_nonexistent_donation():
    """Non-existent donation ID returns 404 Not Found."""
    res = client.get("/matches/donation/999999")
    assert res.status_code == 404

def test_min_score_filter():
    """Filtering by min_score should only return matches exceeding the threshold."""
    db = SessionLocal()
    try:
        active_donation = db.query(FoodDonation).filter(
            FoodDonation.status == DonationStatus.AVAILABLE,
            FoodDonation.available_until > datetime.now(timezone.utc)
        ).first()
        donation_id = active_donation.id
    finally:
        db.close()

    # Query with strict min_score = 80.0
    res = client.get(f"/matches/donation/{donation_id}?min_score=80.0")
    assert res.status_code == 200
    data = res.json()
    for match in data["matches"]:
        assert match["match_score"] >= 80.0

def test_missing_coordinates_fallback():
    """Edge case: Missing or invalid NGO coordinates handles safely."""
    dist = calculate_distance(6.5244, 3.3792, None, None)
    assert dist == float("inf")
    score = calculate_distance_score(dist)
    assert score == 0.0

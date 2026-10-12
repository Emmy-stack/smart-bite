import time
import math
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.main import app
from app.config import settings
from app.database import get_db
import app.database as app_db
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.ngo import NGO
from app.models.donation import FoodDonation, DonationStatus
from app.models.match import Match, MatchStatus
import app.services.auth as auth_service
from app.services.forecasting import (
    calculate_regression_metrics,
    extract_demanded_categories,
    calculate_category_weights,
    clear_forecast_cache,
    DEFAULT_PORTION_KG,
    STANDARD_CATEGORIES,
)

client = TestClient(app)

# Test RSA key pairs for Clerk JWT simulation
_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_test_private_pem = _test_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
_test_public_key = _test_private_key.public_key()
_test_public_pem = _test_public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

_untrusted_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_untrusted_private_pem = _untrusted_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

class MockSigningKey:
    def __init__(self, key):
        self.key = key

class MockJWKClient:
    def __init__(self, public_key):
        self._key = public_key

    def get_signing_key_from_jwt(self, token: str):
        jwt.get_unverified_header(token)
        return MockSigningKey(self._key)

@pytest.fixture(autouse=True)
def mock_clerk_jwks(monkeypatch):
    mock_client = MockJWKClient(_test_public_pem)
    monkeypatch.setattr(auth_service, "get_jwks_client", lambda: mock_client)

@pytest.fixture(autouse=True)
def reset_cache():
    clear_forecast_cache()
    yield
    clear_forecast_cache()

def create_token(
    sub: str,
    email: str = None,
    exp_in_seconds: int = 3600,
    issuer: str = None,
    use_untrusted_key: bool = False
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": issuer or settings.issuer or "https://real-corgi-5864.clerk.accounts.dev",
        "exp": now + exp_in_seconds,
        "iat": now,
        "nbf": now
    }
    if email:
        payload["email"] = email
    key = _untrusted_private_pem if use_untrusted_key else _test_private_pem
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": "test-key-id"})

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Helper fixtures to create test users and entities
# ==============================================================================

@pytest.fixture
def db_session():
    db = app_db.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_ngo_a(db_session):
    uid = uuid.uuid4().hex[:8]
    user = User(
        name=f"NGO Rep A {uid}",
        email=f"ngo_a_{uid}@test.org",
        role=UserRole.NGO,
        clerk_id=f"clerk_ngo_a_{uid}"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    ngo = NGO(
        user_id=user.id,
        name=f"Community Food Bank {uid}",
        address="10 Marina Street, Lagos",
        latitude=6.45,
        longitude=3.40,
        beneficiary_count=100,
        food_requirements="Cooked meals, Fresh fruits",
        capacity=300,
        pickup_available=True
    )
    db_session.add(ngo)
    db_session.commit()
    db_session.refresh(ngo)
    db_session.refresh(user)
    return user, ngo


@pytest.fixture
def sample_ngo_b(db_session):
    uid = uuid.uuid4().hex[:8]
    user = User(
        name=f"NGO Rep B {uid}",
        email=f"ngo_b_{uid}@test.org",
        role=UserRole.NGO,
        clerk_id=f"clerk_ngo_b_{uid}"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    ngo = NGO(
        user_id=user.id,
        name=f"Hope Shelter {uid}",
        address="25 Broad Street, Lagos",
        latitude=6.46,
        longitude=3.41,
        beneficiary_count=50,
        food_requirements="All food types accepted",
        capacity=150,
        pickup_available=True
    )
    db_session.add(ngo)
    db_session.commit()
    db_session.refresh(ngo)
    db_session.refresh(user)
    return user, ngo


@pytest.fixture
def sample_restaurant_user(db_session):
    uid = uuid.uuid4().hex[:8]
    user = User(
        name=f"Chef Luigi {uid}",
        email=f"luigi_{uid}@restaurant.test",
        role=UserRole.RESTAURANT,
        clerk_id=f"clerk_rest_{uid}"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    restaurant = Restaurant(
        user_id=user.id,
        name=f"Luigi Bistro {uid}",
        address="44 Adeola Odeku, VI, Lagos",
        latitude=6.43,
        longitude=3.42
    )
    db_session.add(restaurant)
    db_session.commit()
    db_session.refresh(restaurant)
    db_session.refresh(user)
    return user, restaurant


# ==============================================================================
# 1. AUTHENTICATION & AUTHORIZATION TESTS
# ==============================================================================

def test_forecast_endpoint_requires_authentication(sample_ngo_a):
    """Calling /forecasts/ngo/{id} without token returns 401."""
    _, ngo = sample_ngo_a
    res = client.get(f"/forecasts/ngo/{ngo.id}")
    assert res.status_code == 401
    assert "Authorization Bearer token required" in res.json()["detail"]


def test_forecast_endpoint_invalid_token(sample_ngo_a):
    """Calling with untrusted or expired token returns 401."""
    _, ngo = sample_ngo_a
    bad_token = create_token("clerk_hacker", use_untrusted_key=True)
    res = client.get(f"/forecasts/ngo/{ngo.id}", headers=auth_headers(bad_token))
    assert res.status_code == 401


def test_forecast_unonboarded_user_forbidden(sample_ngo_a):
    """Authenticated Clerk user who has not completed onboarding receives 403."""
    _, ngo = sample_ngo_a
    unonboarded_token = create_token("clerk_not_onboarded_user")
    res = client.get(f"/forecasts/ngo/{ngo.id}", headers=auth_headers(unonboarded_token))
    assert res.status_code == 403
    assert "onboarding" in res.json()["detail"].lower()


def test_forecast_restaurant_user_forbidden(sample_ngo_a, sample_restaurant_user):
    """Restaurant users are forbidden from viewing private NGO demand forecasts."""
    _, ngo = sample_ngo_a
    rest_user, _ = sample_restaurant_user
    rest_token = create_token(rest_user.clerk_id)

    res = client.get(f"/forecasts/ngo/{ngo.id}", headers=auth_headers(rest_token))
    assert res.status_code == 403
    assert "NGO role required" in res.json()["detail"]


def test_forecast_ngo_cannot_access_another_ngo_data(sample_ngo_a, sample_ngo_b):
    """NGO A is strictly forbidden from viewing NGO B's private demand forecast."""
    _, ngo_a = sample_ngo_a
    user_b, ngo_b = sample_ngo_b

    token_b = create_token(user_b.clerk_id)

    # NGO B queries NGO A's endpoint
    res = client.get(f"/forecasts/ngo/{ngo_a.id}", headers=auth_headers(token_b))
    assert res.status_code == 403
    assert "Not authorized to access another NGO's private forecast data" in res.json()["detail"]


# ==============================================================================
# 2. VALID FORECAST REQUESTS & DATA INTEGRITY
# ==============================================================================

def test_valid_forecast_request_for_owning_ngo(sample_ngo_a):
    """Owning NGO retrieves 7-day demand forecast successfully."""
    user_a, ngo_a = sample_ngo_a
    token_a = create_token(user_a.clerk_id)

    res = client.get(f"/forecasts/ngo/{ngo_a.id}?days=7", headers=auth_headers(token_a))
    assert res.status_code == 200
    data = res.json()

    assert data["ngo_id"] == ngo_a.id
    assert data["ngo_name"] == ngo_a.name
    assert data["forecast_horizon_days"] == 7
    assert data["total_estimated_demand_kg"] > 0
    assert len(data["category_summaries"]) > 0
    assert len(data["daily_forecasts"]) == 7 * len(data["category_summaries"])

    # Verify historical context structure
    assert "historical_context" in data
    assert data["historical_context"]["has_sufficient_history"] is False
    assert data["historical_context"]["total_donations_received"] == 0

    # Verify transparent explanation
    explanation = data["explanation"]
    assert explanation["method"] == "baseline_beneficiary_demand"
    assert explanation["data_quality_status"] == "insufficient_history"
    assert explanation["beneficiary_count"] == ngo_a.beneficiary_count
    assert explanation["daily_portion_assumption_kg"] == DEFAULT_PORTION_KG
    assert len(explanation["assumptions"]) > 0
    assert len(explanation["data_limitations"]) > 0
    assert "disclaimer" in explanation


def test_nonnegative_and_finite_predicted_quantities(sample_ngo_a):
    """Ensures all forecasted daily and summary quantities are nonnegative and finite."""
    user_a, ngo_a = sample_ngo_a
    token_a = create_token(user_a.clerk_id)

    res = client.get(f"/forecasts/ngo/{ngo_a.id}?days=7", headers=auth_headers(token_a))
    assert res.status_code == 200
    data = res.json()

    assert not math.isnan(data["total_estimated_demand_kg"])
    assert not math.isinf(data["total_estimated_demand_kg"])
    assert data["total_estimated_demand_kg"] >= 0.0

    for cat_sum in data["category_summaries"]:
        assert cat_sum["total_estimated_kg"] >= 0.0
        assert cat_sum["daily_average_kg"] >= 0.0
        assert not math.isnan(cat_sum["total_estimated_kg"])
        assert not math.isinf(cat_sum["total_estimated_kg"])

    for daily in data["daily_forecasts"]:
        assert daily["estimated_quantity_kg"] >= 0.0
        assert daily["estimated_meal_portions"] >= 0
        assert not math.isnan(daily["estimated_quantity_kg"])
        assert not math.isinf(daily["estimated_quantity_kg"])


def test_correct_food_category_handling(sample_ngo_a, sample_ngo_b):
    """
    NGO A specifies 'Cooked meals, Fresh fruits' -> should only forecast Cooked Meals & Fresh Produce.
    NGO B specifies 'All food types accepted' -> should forecast all 4 standard categories.
    """
    user_a, ngo_a = sample_ngo_a
    token_a = create_token(user_a.clerk_id)
    res_a = client.get(f"/forecasts/ngo/{ngo_a.id}?days=7", headers=auth_headers(token_a))
    data_a = res_a.json()
    cats_a = [c["food_category"] for c in data_a["category_summaries"]]
    assert set(cats_a) == {"Cooked Meals", "Fresh Produce"}

    user_b, ngo_b = sample_ngo_b
    token_b = create_token(user_b.clerk_id)
    res_b = client.get(f"/forecasts/ngo/{ngo_b.id}?days=7", headers=auth_headers(token_b))
    data_b = res_b.json()
    cats_b = [c["food_category"] for c in data_b["category_summaries"]]
    assert set(cats_b) == set(STANDARD_CATEGORIES)


# ==============================================================================
# 3. HORIZON VALIDATION & ERROR HANDLING
# ==============================================================================

def test_invalid_forecast_horizons(sample_ngo_a):
    """Testing invalid horizon parameters (0, negative, >30, non-integer)."""
    user_a, ngo_a = sample_ngo_a
    token_a = create_token(user_a.clerk_id)

    # days = 0
    res = client.get(f"/forecasts/ngo/{ngo_a.id}?days=0", headers=auth_headers(token_a))
    assert res.status_code == 422

    # days = -5
    res = client.get(f"/forecasts/ngo/{ngo_a.id}?days=-5", headers=auth_headers(token_a))
    assert res.status_code == 422

    # days = 31 (exceeds max 30)
    res = client.get(f"/forecasts/ngo/{ngo_a.id}?days=31", headers=auth_headers(token_a))
    assert res.status_code == 422

    # days = 'invalid'
    res = client.get(f"/forecasts/ngo/{ngo_a.id}?days=invalid", headers=auth_headers(token_a))
    assert res.status_code == 422


def test_custom_valid_forecast_horizons(sample_ngo_a):
    """Testing valid horizon extremes (1 day, 14 days, 30 days)."""
    user_a, ngo_a = sample_ngo_a
    token_a = create_token(user_a.clerk_id)

    for h in [1, 14, 30]:
        res = client.get(f"/forecasts/ngo/{ngo_a.id}?days={h}", headers=auth_headers(token_a))
        assert res.status_code == 200
        data = res.json()
        assert data["forecast_horizon_days"] == h


def test_missing_ngo_returns_404(db_session):
    """Requesting forecast for a non-existent NGO ID returns 404."""
    uid = uuid.uuid4().hex[:8]
    user = User(
        name="Orphan Rep",
        email=f"orphan_{uid}@test.org",
        role=UserRole.NGO,
        clerk_id=f"clerk_orphan_{uid}"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    ngo = NGO(
        user_id=user.id,
        name=f"Valid NGO {uid}",
        address="10 Marina, Lagos",
        latitude=6.5,
        longitude=3.3,
        beneficiary_count=20,
        food_requirements="Any"
    )
    db_session.add(ngo)
    db_session.commit()
    db_session.refresh(ngo)

    token = create_token(user.clerk_id)
    # Query for non-existent NGO id (e.g. 99999999)
    res = client.get("/forecasts/ngo/99999999", headers=auth_headers(token))
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_insufficient_ngo_profile_data(db_session):
    """NGO with 0 beneficiaries and no food requirements returns 400."""
    uid = uuid.uuid4().hex[:8]
    user = User(
        name="Empty Rep",
        email=f"empty_{uid}@test.org",
        role=UserRole.NGO,
        clerk_id=f"clerk_empty_{uid}"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    ngo = NGO(
        user_id=user.id,
        name="Unconfigured NGO",
        address="10 Zero St",
        latitude=6.5,
        longitude=3.3,
        beneficiary_count=0,
        food_requirements="",
        capacity=0
    )
    db_session.add(ngo)
    db_session.commit()
    db_session.refresh(ngo)

    token = create_token(user.clerk_id)
    res = client.get(f"/forecasts/ngo/{ngo.id}", headers=auth_headers(token))
    assert res.status_code == 400
    assert "lacks sufficient profile information" in res.json()["detail"].lower()


# ==============================================================================
# 4. HISTORICAL DONATION BLENDING & COMPLETED DONATIONS
# ==============================================================================

def test_forecast_incorporates_historical_donations(db_session, sample_ngo_a, sample_restaurant_user):
    """When an NGO receives accepted/completed donations, historical context reflects them."""
    user_a, ngo_a = sample_ngo_a
    rest_user, rest = sample_restaurant_user

    # Add 2 completed donations accepted by NGO A
    d1 = FoodDonation(
        restaurant_id=rest.id,
        food_name="Vegetable Rice",
        food_category="Cooked Meals",
        quantity=25.0,
        available_until=datetime.now(timezone.utc) + timedelta(hours=5),
        status=DonationStatus.COMPLETED,
        accepted_ngo_id=ngo_a.id
    )
    d2 = FoodDonation(
        restaurant_id=rest.id,
        food_name="Apple Cartons",
        food_category="Fresh Produce",
        quantity=15.0,
        available_until=datetime.now(timezone.utc) + timedelta(hours=6),
        status=DonationStatus.ACCEPTED,
        accepted_ngo_id=ngo_a.id
    )
    db_session.add_all([d1, d2])
    db_session.commit()

    token_a = create_token(user_a.clerk_id)
    res = client.get(f"/forecasts/ngo/{ngo_a.id}?days=7", headers=auth_headers(token_a))
    assert res.status_code == 200
    data = res.json()

    hist = data["historical_context"]
    assert hist["total_donations_received"] >= 2
    assert hist["total_quantity_received_kg"] >= 40.0
    assert "Cooked Meals" in hist["observed_categories"]
    assert "Fresh Produce" in hist["observed_categories"]


# ==============================================================================
# 5. AGGREGATE NETWORK FORECAST & PRIVACY
# ==============================================================================

def test_aggregate_forecast_accessible_to_restaurant_and_ngo(sample_ngo_a, sample_restaurant_user):
    """Aggregate endpoint is accessible to both restaurant and NGO users."""
    user_a, _ = sample_ngo_a
    rest_user, _ = sample_restaurant_user

    token_ngo = create_token(user_a.clerk_id)
    token_rest = create_token(rest_user.clerk_id)

    res_ngo = client.get("/forecasts/aggregate?days=7", headers=auth_headers(token_ngo))
    assert res_ngo.status_code == 200
    data_ngo = res_ngo.json()

    res_rest = client.get("/forecasts/aggregate?days=7", headers=auth_headers(token_rest))
    assert res_rest.status_code == 200
    data_rest = res_rest.json()

    assert data_ngo["total_network_demand_kg"] >= 0.0
    assert data_ngo["active_ngos_count"] >= 1
    assert len(data_ngo["category_breakdown"]) > 0

    # Ensure individual NGO private identifiers are NOT exposed in aggregate payload
    serialized = str(data_ngo)
    assert user_a.name not in serialized


# ==============================================================================
# 6. MODEL EVALUATION TRANSPARENCY
# ==============================================================================

def test_model_evaluation_endpoint(sample_ngo_a):
    """
    When operational records are below threshold, model evaluation reports
    insufficient history, details collection requirements, and explains MAE/RMSE.
    """
    user_a, _ = sample_ngo_a
    token = create_token(user_a.clerk_id)

    res = client.get("/forecasts/evaluation", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()

    assert "is_evaluation_meaningful" in data
    assert "metrics_definitions" in data
    assert "MAE" in data["metrics_definitions"]
    assert "RMSE" in data["metrics_definitions"]
    assert "data_collection_requirements" in data
    assert len(data["data_collection_requirements"]) > 0


# ==============================================================================
# 7. UNIT TESTS: REGRESSION METRICS & TAXONOMY
# ==============================================================================

def test_calculate_regression_metrics_unit():
    """Validates mathematical correctness of pure-Python MAE and RMSE."""
    y_true = [10.0, 20.0, 30.0]
    y_pred = [12.0, 18.0, 34.0]
    # errors = [+2, -2, +4]
    # MAE = (2 + 2 + 4) / 3 = 8 / 3 = 2.67
    # sq_errors = [4, 4, 16] = 24 / 3 = 8 -> sqrt(8) = 2.83
    metrics = calculate_regression_metrics(y_true, y_pred)
    assert metrics["mae"] == 2.67
    assert metrics["rmse"] == 2.83
    assert metrics["sample_count"] == 3


def test_extract_demanded_categories_unit():
    """Validates requirement parsing into canonical taxonomy categories."""
    assert extract_demanded_categories(None) == STANDARD_CATEGORIES
    assert extract_demanded_categories("All food accepted") == STANDARD_CATEGORIES
    assert extract_demanded_categories("Cooked meals, Halal, Fresh fruits") == ["Cooked Meals", "Fresh Produce"]
    assert extract_demanded_categories("Bread, Pastries") == ["Bakery"]

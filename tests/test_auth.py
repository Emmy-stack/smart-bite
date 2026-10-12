import os
import time
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.main import app
from app.config import settings
from app.database import engine, SessionLocal
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.ngo import NGO
from app.models.donation import FoodDonation, DonationStatus
from app.models.match import Match, MatchStatus
import app.services.auth as auth_service

client = TestClient(app)

# Generate isolated test RSA key pair for cryptographic token simulation
_test_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)
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

# Second key pair to simulate tokens signed with wrong keys
_untrusted_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)
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
        # Validate that token is at least parseable
        jwt.get_unverified_header(token)
        return MockSigningKey(self._key)


@pytest.fixture(autouse=True)
def mock_clerk_jwks(monkeypatch):
    """
    Hooks PyJWKClient in app.services.auth to verify tokens using
    our local test public key.
    """
    mock_client = MockJWKClient(_test_public_pem)
    monkeypatch.setattr(auth_service, "get_jwks_client", lambda: mock_client)


def create_token(
    sub: str,
    email: str = None,
    exp_in_seconds: int = 3600,
    issuer: str = None,
    use_untrusted_key: bool = False
) -> str:
    """Helper to mint simulated Clerk session tokens."""
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
# 1. PUBLIC ENDPOINTS
# ==============================================================================

def test_public_health_and_docs_without_auth():
    """Health, root, and docs endpoints must remain public."""
    res_root = client.get("/")
    assert res_root.status_code == 200

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_docs = client.get("/docs")
    assert res_docs.status_code == 200


# ==============================================================================
# 2. TOKEN VERIFICATION & 401 ERROR CASES
# ==============================================================================

def test_missing_token_returns_401():
    """Calling protected endpoints without Authorization header returns 401."""
    res = client.get("/auth/me")
    assert res.status_code == 401
    assert "Authorization" in res.json()["detail"] or "required" in res.json()["detail"].lower()

    res_donations = client.get("/donations/")
    assert res_donations.status_code == 401


def test_malformed_token_returns_401():
    """Calling with malformed tokens returns 401."""
    res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401

    res_basic = client.get("/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert res_basic.status_code == 401


def test_expired_token_returns_401():
    """Expired tokens return 401 with clear expiration detail."""
    expired_token = create_token(sub="user_exp", exp_in_seconds=-300)
    res = client.get("/auth/me", headers=auth_headers(expired_token))
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_invalid_issuer_returns_401():
    """Tokens with unauthorized issuer claim return 401."""
    bad_iss_token = create_token(sub="user_iss", issuer="https://evil-identity-provider.com")
    res = client.get("/auth/me", headers=auth_headers(bad_iss_token))
    assert res.status_code == 401
    assert "issuer" in res.json()["detail"].lower()


def test_untrusted_signature_returns_401():
    """Tokens signed with an untrusted RSA private key return 401."""
    bad_key_token = create_token(sub="user_bad_key", use_untrusted_key=True)
    res = client.get("/auth/me", headers=auth_headers(bad_key_token))
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower() or "signature" in res.json()["detail"].lower()


# ==============================================================================
# 3. ONBOARDING & IDENTITY LINKING
# ==============================================================================

def test_unonboarded_user_flow():
    """A valid token for an un-onboarded identity returns is_onboarded=False on /auth/me."""
    clerk_id = f"user_unonboarded_{uuid.uuid4().hex[:6]}"
    token = create_token(sub=clerk_id, email="unonboarded@test.com")

    # /auth/me succeeds but reflects un-onboarded state
    res_me = client.get("/auth/me", headers=auth_headers(token))
    assert res_me.status_code == 200
    data = res_me.json()
    assert data["authenticated"] is True
    assert data["clerk_id"] == clerk_id
    assert data["is_onboarded"] is False
    assert data["role"] is None

    # Calling an endpoint requiring an onboarded application user returns 403
    res_donations = client.get("/donations/", headers=auth_headers(token))
    assert res_donations.status_code == 403
    assert "onboarding" in res_donations.json()["detail"].lower()


def test_restaurant_onboarding_and_immutability():
    """Test onboarding as restaurant, profile creation, and rejection of role change."""
    clerk_id = f"user_rest_{uuid.uuid4().hex[:6]}"
    token = create_token(sub=clerk_id, email=f"{clerk_id}@test.com")

    payload = {
        "name": "Mario Rossi",
        "email": f"{clerk_id}@test.com",
        "phone": "+1-555-0101",
        "restaurant_name": "Mario's Pizzeria",
        "address": "10 Pizza Way",
        "latitude": 40.7128,
        "longitude": -74.0060
    }
    onboard_res = client.post("/auth/onboard/restaurant", json=payload, headers=auth_headers(token))
    assert onboard_res.status_code == 201
    data = onboard_res.json()
    assert data["is_onboarded"] is True
    assert data["role"] == "restaurant"
    assert data["restaurant"]["name"] == "Mario's Pizzeria"

    # Repeated onboarding attempt with same identity is rejected
    dup_res = client.post("/auth/onboard/restaurant", json=payload, headers=auth_headers(token))
    assert dup_res.status_code == 400
    assert "already onboarded" in dup_res.json()["detail"].lower()

    # Attempting to switch role to NGO is strictly rejected
    ngo_payload = {
        "name": "Mario Rossi",
        "ngo_name": "Switch Attempt NGO",
        "address": "10 Pizza Way",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "beneficiary_count": 100,
        "capacity": 200,
        "pickup_available": True
    }
    switch_res = client.post("/auth/onboard/ngo", json=ngo_payload, headers=auth_headers(token))
    assert switch_res.status_code == 400
    assert "already onboarded" in switch_res.json()["detail"].lower()


def test_ngo_onboarding():
    """Test onboarding as NGO and profile verification."""
    clerk_id = f"user_ngo_{uuid.uuid4().hex[:6]}"
    token = create_token(sub=clerk_id, email=f"{clerk_id}@test.com")

    payload = {
        "name": "Sarah Connor",
        "email": f"{clerk_id}@test.com",
        "phone": "+1-555-0102",
        "ngo_name": "Resilience Food Network",
        "address": "20 Shelter Blvd",
        "latitude": 40.7300,
        "longitude": -73.9900,
        "beneficiary_count": 300,
        "food_requirements": "Vegetarian, Cooked",
        "capacity": 500,
        "pickup_available": True
    }
    onboard_res = client.post("/auth/onboard/ngo", json=payload, headers=auth_headers(token))
    assert onboard_res.status_code == 201
    data = onboard_res.json()
    assert data["is_onboarded"] is True
    assert data["role"] == "ngo"
    assert data["ngo"]["name"] == "Resilience Food Network"
    assert data["ngo"]["capacity"] == 500


def test_safe_backfill_existing_database_user():
    """Existing database users with clerk_id=None are safely linked upon onboarding with matching email."""
    db = SessionLocal()
    unique_email = f"legacy_chef_{uuid.uuid4().hex[:6]}@test.com"
    existing_user = User(
        name="Legacy Chef",
        email=unique_email,
        phone="+1-555-0000",
        role=UserRole.RESTAURANT,
        clerk_id=None
    )
    db.add(existing_user)
    db.commit()
    db.refresh(existing_user)
    db.close()

    clerk_id = f"user_clerk_{uuid.uuid4().hex[:6]}"
    token = create_token(sub=clerk_id, email=unique_email)

    payload = {
        "name": "Legacy Chef",
        "email": unique_email,
        "restaurant_name": "Legacy Trattoria",
        "address": "15 Heritage Lane",
        "latitude": 40.7200,
        "longitude": -74.0100
    }
    onboard_res = client.post("/auth/onboard/restaurant", json=payload, headers=auth_headers(token))
    assert onboard_res.status_code == 201
    data = onboard_res.json()
    assert data["user"]["id"] == existing_user.id
    assert data["clerk_id"] == clerk_id


# ==============================================================================
# 4. ROLE-BASED ACCESS CONTROL (RESTAURANT VS NGO)
# ==============================================================================

def test_restaurant_cannot_access_ngo_routes():
    """Restaurants cannot access NGO-only match action and pending routes."""
    # Create restaurant user
    clerk_id = f"user_rest_{uuid.uuid4().hex[:6]}"
    token = create_token(sub=clerk_id)
    client.post("/auth/onboard/restaurant", json={
        "name": "Rest Owner",
        "restaurant_name": "Tacos Locos",
        "address": "100 Taco St",
        "latitude": 40.71,
        "longitude": -74.01
    }, headers=auth_headers(token))

    # Calling NGO pending offers returns 403
    res_pending = client.get("/matches/pending", headers=auth_headers(token))
    assert res_pending.status_code == 403
    assert "ngo role required" in res_pending.json()["detail"].lower()

    # Calling NGO match accept returns 403
    res_accept = client.post("/matches/1/accept", headers=auth_headers(token))
    assert res_accept.status_code == 403
    assert "ngo role required" in res_accept.json()["detail"].lower()


def test_ngo_cannot_access_restaurant_routes():
    """NGOs cannot create donations or generate match offers."""
    # Create NGO user
    clerk_id = f"user_ngo_{uuid.uuid4().hex[:6]}"
    token = create_token(sub=clerk_id)
    client.post("/auth/onboard/ngo", json={
        "name": "NGO Leader",
        "ngo_name": "Community Table",
        "address": "200 Table Way",
        "latitude": 40.72,
        "longitude": -73.98,
        "beneficiary_count": 100,
        "capacity": 200,
        "pickup_available": True
    }, headers=auth_headers(token))

    # Calling donation creation returns 403
    don_payload = {
        "food_name": "Hot Soup",
        "food_category": "Cooked Meals",
        "quantity": 10.0,
        "available_until": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    }
    res_don = client.post("/donations/", json=don_payload, headers=auth_headers(token))
    assert res_don.status_code == 403
    assert "restaurant role required" in res_don.json()["detail"].lower()


# ==============================================================================
# 5. CROSS-TENANT ISOLATION & RESOURCE OWNERSHIP
# ==============================================================================

def test_cross_tenant_restaurant_isolation():
    """Restaurant A cannot view match history or cancel Restaurant B's donation."""
    # 1. Onboard Restaurant A
    token_a = create_token(sub=f"user_rest_a_{uuid.uuid4().hex[:6]}")
    res_a = client.post("/auth/onboard/restaurant", json={
        "name": "Owner A",
        "restaurant_name": "Bistro A",
        "address": "1 A St",
        "latitude": 40.71,
        "longitude": -74.01
    }, headers=auth_headers(token_a)).json()
    rest_a_id = res_a["restaurant"]["id"]

    # 2. Onboard Restaurant B
    token_b = create_token(sub=f"user_rest_b_{uuid.uuid4().hex[:6]}")
    res_b = client.post("/auth/onboard/restaurant", json={
        "name": "Owner B",
        "restaurant_name": "Bistro B",
        "address": "2 B St",
        "latitude": 40.72,
        "longitude": -74.02
    }, headers=auth_headers(token_b)).json()
    rest_b_id = res_b["restaurant"]["id"]

    # 3. Restaurant A creates a donation
    avail = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    don_res = client.post("/donations/", json={
        "food_name": "Pasta Trays",
        "food_category": "Cooked Meals",
        "quantity": 20.0,
        "available_until": avail
    }, headers=auth_headers(token_a))
    assert don_res.status_code == 201
    donation_a_id = don_res.json()["id"]

    # 4. Restaurant B attempts to view matches of Restaurant A's donation -> 403
    matches_res = client.get(f"/donations/{donation_a_id}/matches", headers=auth_headers(token_b))
    assert matches_res.status_code == 403

    # 5. Restaurant B attempts to cancel Restaurant A's donation -> 403
    cancel_res = client.post(f"/donations/{donation_a_id}/cancel", headers=auth_headers(token_b))
    assert cancel_res.status_code == 403

    # 6. Restaurant B attempts to run matching for Restaurant A's donation -> 403
    match_eval_res = client.get(f"/matches/donation/{donation_a_id}", headers=auth_headers(token_b))
    assert match_eval_res.status_code == 403

    # 7. Restaurant B attempts to spoof restaurant_id in request body -> 403
    spoof_res = client.post("/donations/", json={
        "restaurant_id": rest_a_id,  # Spoofing Restaurant A
        "food_name": "Illegal Food",
        "food_category": "Bakery",
        "quantity": 5.0,
        "available_until": avail
    }, headers=auth_headers(token_b))
    assert spoof_res.status_code == 403
    assert "cannot create donation for a restaurant you do not own" in spoof_res.json()["detail"].lower()


def test_cross_tenant_ngo_isolation_and_workflow():
    """NGO A cannot accept, reject, or view match offers belonging to NGO B."""
    # 1. Onboard Restaurant
    rest_token = create_token(sub=f"user_rest_{uuid.uuid4().hex[:6]}")
    client.post("/auth/onboard/restaurant", json={
        "name": "Donor Chef",
        "restaurant_name": "Grand Eatery",
        "address": "1 Grand Ave",
        "latitude": 40.71,
        "longitude": -74.00
    }, headers=auth_headers(rest_token))

    # 2. Onboard NGO 1
    token_ngo1 = create_token(sub=f"user_ngo1_{uuid.uuid4().hex[:6]}")
    ngo1_data = client.post("/auth/onboard/ngo", json={
        "name": "Leader 1",
        "ngo_name": "Shelter Alpha",
        "address": "10 Alpha Rd",
        "latitude": 40.715,
        "longitude": -74.005,
        "beneficiary_count": 50,
        "capacity": 100,
        "pickup_available": True
    }, headers=auth_headers(token_ngo1)).json()["ngo"]
    ngo1_id = ngo1_data["id"]

    # 3. Onboard NGO 2
    token_ngo2 = create_token(sub=f"user_ngo2_{uuid.uuid4().hex[:6]}")
    ngo2_data = client.post("/auth/onboard/ngo", json={
        "name": "Leader 2",
        "ngo_name": "Shelter Beta",
        "address": "20 Beta Rd",
        "latitude": 40.720,
        "longitude": -74.010,
        "beneficiary_count": 80,
        "capacity": 150,
        "pickup_available": True
    }, headers=auth_headers(token_ngo2)).json()["ngo"]
    ngo2_id = ngo2_data["id"]

    # 4. Restaurant creates a donation and generates offers
    avail = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    don = client.post("/donations/", json={
        "food_name": "Fresh Stew & Rice",
        "food_category": "Cooked Meals",
        "quantity": 30.0,
        "available_until": avail
    }, headers=auth_headers(rest_token)).json()
    don_id = don["id"]

    offers_res = client.post(f"/matches/donation/{don_id}/offers", json={"top_k": 5}, headers=auth_headers(rest_token))
    assert offers_res.status_code == 201
    offers = offers_res.json()
    assert len(offers) >= 2

    offer_ngo1 = next(o for o in offers if o["ngo_id"] == ngo1_id)
    offer_ngo2 = next(o for o in offers if o["ngo_id"] == ngo2_id)

    # 5. NGO 2 tries to query pending offers pretending to be NGO 1 -> 403
    impersonate_res = client.get(f"/matches/pending?ngo_id={ngo1_id}", headers=auth_headers(token_ngo2))
    assert impersonate_res.status_code == 403

    # 6. NGO 2 attempts to accept NGO 1's offer -> 403
    theft_res = client.post(f"/matches/{offer_ngo1['id']}/accept", headers=auth_headers(token_ngo2))
    assert theft_res.status_code == 403
    assert "not authorized to accept a match offer belonging to another ngo" in theft_res.json()["detail"].lower()

    # 7. NGO 1 legitimately accepts their own offer -> 200
    accept_res = client.post(f"/matches/{offer_ngo1['id']}/accept", headers=auth_headers(token_ngo1))
    assert accept_res.status_code == 200
    assert accept_res.json()["donation_status"] == "accepted"

    # 8. NGO 1 progresses status: accepted -> pickup -> delivered -> completed
    status_pickup = client.patch(f"/donations/{don_id}/status", json={"status": "pickup"}, headers=auth_headers(token_ngo1))
    assert status_pickup.status_code == 200
    assert status_pickup.json()["status"] == "pickup"

    status_delivered = client.patch(f"/donations/{don_id}/status", json={"status": "delivered"}, headers=auth_headers(token_ngo1))
    assert status_delivered.status_code == 200
    assert status_delivered.json()["status"] == "delivered"

    status_done = client.patch(f"/donations/{don_id}/status", json={"status": "completed"}, headers=auth_headers(token_ngo1))
    assert status_done.status_code == 200
    assert status_done.json()["status"] == "completed"

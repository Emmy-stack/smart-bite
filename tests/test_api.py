import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine
from app.models import Restaurant, NGO, FoodDonation, User

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "SmartBite API is running"}

def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_swagger_docs():
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower() or "html" in response.text.lower()

def test_user_lifecycle():
    import uuid
    unique_email = f"jane.{uuid.uuid4().hex[:8]}@foodrescue.org"
    user_payload = {
        "name": "Jane Doe",
        "email": unique_email,
        "phone": "+1-555-0199",
        "role": "ngo"
    }
    res = client.post("/users/", json=user_payload)
    assert res.status_code == 201
    user = res.json()
    assert user["email"] == user_payload["email"]
    user_id = user["id"]

    get_res = client.get(f"/users/{user_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Jane Doe"

    # Duplicate email fails
    dup_res = client.post("/users/", json=user_payload)
    assert dup_res.status_code == 400

def test_restaurant_lifecycle():
    # 1. Create a restaurant
    restaurant_payload = {
        "name": "Green Garden Bistro",
        "address": "123 Eco Way, Downtown",
        "latitude": 40.7128,
        "longitude": -74.0060
    }
    create_res = client.post("/restaurants/", json=restaurant_payload)
    assert create_res.status_code == 201, create_res.text
    created_data = create_res.json()
    assert created_data["name"] == restaurant_payload["name"]
    assert created_data["address"] == restaurant_payload["address"]
    assert created_data["latitude"] == restaurant_payload["latitude"]
    assert created_data["longitude"] == restaurant_payload["longitude"]
    restaurant_id = created_data["id"]

    # 2. Get all restaurants
    list_res = client.get("/restaurants/")
    assert list_res.status_code == 200
    restaurants = list_res.json()
    assert any(r["id"] == restaurant_id for r in restaurants)

    # 3. Get restaurant by ID
    get_res = client.get(f"/restaurants/{restaurant_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == restaurant_id

    # 4. Non-existent restaurant returns 404
    not_found_res = client.get("/restaurants/999999")
    assert not_found_res.status_code == 404

    # 5. Invalid latitude returns 422 validation error
    invalid_res = client.post("/restaurants/", json={
        "name": "Invalid Location",
        "address": "Some Street",
        "latitude": 150.0,  # Invalid: > 90
        "longitude": 0.0
    })
    assert invalid_res.status_code == 422

def test_ngo_lifecycle():
    # 1. Create an NGO
    ngo_payload = {
        "name": "Hope Food Bank",
        "address": "456 Charity Lane",
        "latitude": 40.7306,
        "longitude": -73.9352,
        "beneficiary_count": 250,
        "food_requirements": "Cooked meals, Halal, Fresh fruits",
        "capacity": 500,
        "pickup_available": True
    }
    create_res = client.post("/ngos/", json=ngo_payload)
    assert create_res.status_code == 201, create_res.text
    created_ngo = create_res.json()
    assert created_ngo["name"] == ngo_payload["name"]
    assert created_ngo["capacity"] == 500
    assert created_ngo["beneficiary_count"] == 250
    ngo_id = created_ngo["id"]

    # 2. List NGOs
    list_res = client.get("/ngos/")
    assert list_res.status_code == 200
    ngos = list_res.json()
    assert any(n["id"] == ngo_id for n in ngos)

    # 3. Get NGO by ID
    get_res = client.get(f"/ngos/{ngo_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == ngo_payload["name"]

    # 4. Non-existent NGO returns 404
    assert client.get("/ngos/999999").status_code == 404

def test_food_donation_lifecycle():
    # Setup: Create a restaurant first
    res_resp = client.post("/restaurants/", json={
        "name": "Sunset Bakery",
        "address": "789 Baker St",
        "latitude": 40.7589,
        "longitude": -73.9851
    })
    restaurant_id = res_resp.json()["id"]

    # 1. Create a food donation
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=6)
    donation_payload = {
        "restaurant_id": restaurant_id,
        "food_name": "Artisan Sourdough Loaves & Croissants",
        "food_category": "Bakery",
        "quantity": 25.0,
        "prepared_at": now.isoformat(),
        "available_until": until.isoformat(),
        "storage_method": "ambient",
        "pickup_available": True
    }
    create_res = client.post("/donations/", json=donation_payload)
    assert create_res.status_code == 201, create_res.text
    created_donation = create_res.json()
    assert created_donation["food_name"] == donation_payload["food_name"]
    assert created_donation["status"] == "available"
    assert created_donation["quantity"] == 25.0
    donation_id = created_donation["id"]

    # 2. List donations
    list_res = client.get("/donations/")
    assert list_res.status_code == 200
    donations = list_res.json()
    assert any(d["id"] == donation_id for d in donations)

    # 3. Filter donations by status
    status_res = client.get("/donations/?status=available")
    assert status_res.status_code == 200
    assert all(d["status"] == "available" for d in status_res.json())

    # 4. Filter donations by restaurant_id
    rest_filter_res = client.get(f"/donations/?restaurant_id={restaurant_id}")
    assert rest_filter_res.status_code == 200
    assert all(d["restaurant_id"] == restaurant_id for d in rest_filter_res.json())

    # 5. Get donation by ID
    get_res = client.get(f"/donations/{donation_id}")
    assert get_res.status_code == 200
    assert get_res.json()["food_name"] == donation_payload["food_name"]

    # 6. Non-existent donation returns 404
    assert client.get("/donations/999999").status_code == 404

    # 7. Donation with non-existent restaurant returns 404
    invalid_donation = client.post("/donations/", json={
        "restaurant_id": 999999,
        "food_name": "Ghost Food",
        "food_category": "Prepared",
        "quantity": 10.0,
        "available_until": until.isoformat()
    })
    assert invalid_donation.status_code == 404

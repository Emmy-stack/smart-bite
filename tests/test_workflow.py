import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database import engine, Base, SessionLocal
from app.models import Restaurant, NGO, FoodDonation, DonationStatus, Match, MatchStatus

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def init_db():
    Base.metadata.create_all(bind=engine)
    yield

def _create_test_entities():
    """Helper to provision fresh test restaurant, NGOs, and donation."""
    db = SessionLocal()
    try:
        restaurant = Restaurant(
            name="Mama Cass Eatery",
            address="10 Aromire Avenue, Ikeja, Lagos",
            latitude=6.5980,
            longitude=3.3450
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)

        ngo1 = NGO(
            name="Grace Food Aid",
            address="15 Obafemi Awolowo Way, Ikeja, Lagos",
            latitude=6.6010,
            longitude=3.3470,
            beneficiary_count=50,
            food_requirements="Cooked Meals, Rice",
            capacity=80,
            pickup_available=True
        )
        ngo2 = NGO(
            name="Lagos Children Mission",
            address="20 Mobolaji Bank Anthony, Maryland, Lagos",
            latitude=6.5800,
            longitude=3.3600,
            beneficiary_count=90,
            food_requirements="Hot meals, Stew",
            capacity=120,
            pickup_available=True
        )
        db.add_all([ngo1, ngo2])
        db.commit()
        db.refresh(ngo1)
        db.refresh(ngo2)

        avail = datetime.now(timezone.utc) + timedelta(hours=8)
        donation = FoodDonation(
            restaurant_id=restaurant.id,
            food_name="60 packs of Fried Rice & Chicken",
            food_category="Cooked Meals",
            quantity=60.0,
            available_until=avail,
            storage_method="insulated warmers",
            pickup_available=True,
            status=DonationStatus.AVAILABLE
        )
        db.add(donation)
        db.commit()
        db.refresh(donation)

        return restaurant.id, ngo1.id, ngo2.id, donation.id
    finally:
        db.close()


def test_create_match_offers():
    _, ngo1_id, ngo2_id, donation_id = _create_test_entities()

    # Create match offers
    res = client.post(f"/matches/donation/{donation_id}/offers", json={"top_k": 2, "min_score": 40.0})
    assert res.status_code == 201, res.text
    offers = res.json()
    assert len(offers) >= 1
    for offer in offers:
        assert offer["status"] == "pending"
        assert offer["match_score"] > 0
        assert offer["food_name"] == "60 packs of Fried Rice & Chicken"
        assert offer["restaurant_name"] == "Mama Cass Eatery"

    # Verify donation status transitioned to 'matched'
    don_res = client.get(f"/donations/{donation_id}")
    assert don_res.json()["status"] == "matched"

    # Idempotency: Creating offers again does not create duplicate entries for same NGO
    res2 = client.post(f"/matches/donation/{donation_id}/offers", json={"top_k": 2, "min_score": 40.0})
    assert res2.status_code == 201
    db = SessionLocal()
    try:
        count = db.query(Match).filter(Match.donation_id == donation_id).count()
        assert count == len(offers)
    finally:
        db.close()


def test_ngo_view_pending_offers():
    _, ngo1_id, _, donation_id = _create_test_entities()
    client.post(f"/matches/donation/{donation_id}/offers", json={"top_k": 5, "min_score": 30.0})

    # Query pending offers for ngo1
    res = client.get(f"/matches/pending?ngo_id={ngo1_id}")
    assert res.status_code == 200, res.text
    pending = res.json()
    assert len(pending) >= 1
    target_offer = next((o for o in pending if o["donation_id"] == donation_id), None)
    assert target_offer is not None
    assert target_offer["status"] == "pending"
    assert target_offer["food_name"] == "60 packs of Fried Rice & Chicken"


def test_accept_match_offer_workflow():
    _, ngo1_id, ngo2_id, donation_id = _create_test_entities()
    offers_res = client.post(f"/matches/donation/{donation_id}/offers", json={"top_k": 5, "min_score": 30.0})
    offers = offers_res.json()
    assert len(offers) >= 2

    winning_offer = offers[0]
    losing_offer = offers[1]

    # Accept the winning offer
    accept_res = client.post(f"/matches/{winning_offer['id']}/accept")
    assert accept_res.status_code == 200, accept_res.text
    accept_data = accept_res.json()
    assert accept_data["match"]["status"] == "accepted"
    assert accept_data["donation_status"] == "accepted"
    assert accept_data["match"]["responded_at"] is not None

    # Verify donation is accepted and linked to winning NGO
    don_res = client.get(f"/donations/{donation_id}")
    don = don_res.json()
    assert don["status"] == "accepted"
    assert don["accepted_ngo_id"] == winning_offer["ngo_id"]

    # Verify losing offer was cancelled
    db = SessionLocal()
    try:
        losing_db = db.query(Match).filter(Match.id == losing_offer["id"]).first()
        assert losing_db.status == MatchStatus.CANCELLED
        assert losing_db.responded_at is not None
    finally:
        db.close()


def test_prevent_second_ngo_accepting():
    _, _, _, donation_id = _create_test_entities()
    offers_res = client.post(f"/matches/donation/{donation_id}/offers", json={"top_k": 5, "min_score": 30.0})
    offers = offers_res.json()
    assert len(offers) >= 2

    # First NGO accepts
    client.post(f"/matches/{offers[0]['id']}/accept")

    # Second NGO tries to accept
    res2 = client.post(f"/matches/{offers[1]['id']}/accept")
    assert res2.status_code == 400
    assert "already" in res2.json()["detail"].lower() or "cannot" in res2.json()["detail"].lower()


def test_reject_offer():
    _, ngo1_id, _, donation_id = _create_test_entities()
    offers_res = client.post(f"/matches/donation/{donation_id}/offers", json={"top_k": 5, "min_score": 30.0})
    offers = offers_res.json()
    target_offer = offers[0]

    # Reject offer
    rej_res = client.post(f"/matches/{target_offer['id']}/reject")
    assert rej_res.status_code == 200, rej_res.text
    rej_data = rej_res.json()
    assert rej_data["match"]["status"] == "rejected"
    assert rej_data["match"]["responded_at"] is not None

    # Cannot accept an already rejected offer
    dup_res = client.post(f"/matches/{target_offer['id']}/accept")
    assert dup_res.status_code == 400


def test_prevent_accepting_expired_donation():
    db = SessionLocal()
    try:
        rest = db.query(Restaurant).first()
        ngo = db.query(NGO).first()
        # Create expired donation (expired 1 hour ago)
        expired_donation = FoodDonation(
            restaurant_id=rest.id,
            food_name="Cold Stew",
            food_category="Cooked Meals",
            quantity=10.0,
            available_until=datetime.now(timezone.utc) - timedelta(hours=1),
            status=DonationStatus.AVAILABLE
        )
        db.add(expired_donation)
        db.commit()
        db.refresh(expired_donation)

        # Manually create pending match
        match = Match(
            donation_id=expired_donation.id,
            ngo_id=ngo.id,
            match_score=85.0,
            status=MatchStatus.PENDING
        )
        db.add(match)
        db.commit()
        db.refresh(match)
        match_id = match.id
    finally:
        db.close()

    # Attempt to accept expired offer
    res = client.post(f"/matches/{match_id}/accept")
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_donation_lifecycle_transitions():
    _, _, _, donation_id = _create_test_entities()

    # 1. Invalid jump: available -> completed
    bad_res = client.patch(f"/donations/{donation_id}/status", json={"status": "completed"})
    assert bad_res.status_code == 400
    assert "cannot change from 'available' to 'completed'" in bad_res.json()["detail"]

    # 2. Valid path: available -> matched -> accepted -> pickup -> delivered -> completed
    step1 = client.patch(f"/donations/{donation_id}/status", json={"status": "matched"})
    assert step1.status_code == 200
    assert step1.json()["status"] == "matched"

    step2 = client.patch(f"/donations/{donation_id}/status", json={"status": "accepted"})
    assert step2.status_code == 200
    assert step2.json()["status"] == "accepted"

    step3 = client.patch(f"/donations/{donation_id}/status", json={"status": "pickup"})
    assert step3.status_code == 200
    assert step3.json()["status"] == "pickup"

    step4 = client.patch(f"/donations/{donation_id}/status", json={"status": "delivered"})
    assert step4.status_code == 200
    assert step4.json()["status"] == "delivered"

    step5 = client.patch(f"/donations/{donation_id}/status", json={"status": "completed"})
    assert step5.status_code == 200
    assert step5.json()["status"] == "completed"

    # Terminal state: completed cannot change
    terminal_res = client.patch(f"/donations/{donation_id}/status", json={"status": "pickup"})
    assert terminal_res.status_code == 400


def test_donation_cancellation():
    _, _, _, donation_id = _create_test_entities()
    client.post(f"/matches/donation/{donation_id}/offers", json={"top_k": 2})

    # Cancel donation
    cancel_res = client.post(f"/donations/{donation_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Verify pending offers are now cancelled
    db = SessionLocal()
    try:
        active_matches = db.query(Match).filter(
            Match.donation_id == donation_id,
            Match.status == MatchStatus.PENDING
        ).count()
        assert active_matches == 0
    finally:
        db.close()

    # Cannot transition a cancelled donation
    prog_res = client.patch(f"/donations/{donation_id}/status", json={"status": "accepted"})
    assert prog_res.status_code == 400


def test_restaurant_view_match_history():
    _, _, _, donation_id = _create_test_entities()
    client.post(f"/matches/donation/{donation_id}/offers", json={"top_k": 2})

    res = client.get(f"/donations/{donation_id}/matches")
    assert res.status_code == 200
    data = res.json()
    assert data["donation_id"] == donation_id
    assert data["total_offers"] >= 1
    assert len(data["offers"]) >= 1


def test_missing_entities():
    # Non-existent match accept/reject
    assert client.post("/matches/999999/accept").status_code == 404
    assert client.post("/matches/999999/reject").status_code == 404

    # Non-existent NGO pending offers
    assert client.get("/matches/pending?ngo_id=999999").status_code == 404

    # Non-existent donation status update
    assert client.patch("/donations/999999/status", json={"status": "accepted"}).status_code == 404
    assert client.get("/donations/999999/matches").status_code == 404
    assert client.post("/donations/999999/cancel").status_code == 404

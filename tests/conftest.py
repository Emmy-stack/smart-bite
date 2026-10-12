import os
import pytest
from fastapi import Request, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

TEST_DB_URL = "postgresql://postgres@localhost:5432/food_rescue_test_db"
os.environ["DATABASE_URL"] = TEST_DB_URL

import app.database as app_db
from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.ngo import NGO
from app.models.donation import FoodDonation
from app.models.match import Match
from app.services.auth import (
    get_current_clerk_claims,
    get_current_user,
    get_current_restaurant_user,
    get_current_ngo_user,
)

test_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Point app database engine and session factory to test database
app_db.engine = test_engine
app_db.SessionLocal = TestingSessionLocal


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes tables and columns in the isolated test database."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        conn.execute(text("ALTER TABLE food_donations ADD COLUMN IF NOT EXISTS accepted_ngo_id INTEGER REFERENCES ngos(id) ON DELETE SET NULL;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS clerk_id VARCHAR(128);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_clerk_id ON users (clerk_id) WHERE clerk_id IS NOT NULL;"))
        conn.commit()
    yield
    # Clean up after entire test run
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def override_get_db():
    """Ensures FastAPI dependencies use the isolated test database session."""
    def _get_test_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def handle_legacy_test_auth(request):
    """
    For Step 1-3 tests (test_api, test_matching, test_workflow), provides contextual
    mock user dependencies so legacy test suites continue running without alteration.
    For test_auth.py, this fixture does nothing, allowing full Clerk auth testing.
    """
    if "test_auth" in request.node.fspath.basename or "test_forecasting" in request.node.fspath.basename:
        # In test_auth.py and test_forecasting.py, do not install legacy mock overrides
        yield
        return

    def _get_or_create_restaurant_user(request: Request, db: Session = Depends(get_db)) -> User:
        import uuid

        # When creating a new restaurant, provide a user without an existing restaurant
        if request.method == "POST" and request.url.path == "/restaurants/":
            uid = uuid.uuid4().hex[:8]
            user = User(
                name=f"New Restaurant Owner {uid}",
                email=f"new_rest_owner_{uid}@foodrescue.test",
                role=UserRole.RESTAURANT,
                clerk_id=f"clerk_new_rest_{uid}"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

        # 1. Check if donation_id in path
        target_restaurant = None
        if "donation_id" in request.path_params:
            try:
                don_id = int(request.path_params["donation_id"])
                don = db.query(FoodDonation).filter(FoodDonation.id == don_id).first()
                if don and don.restaurant:
                    target_restaurant = don.restaurant
            except Exception:
                pass

        if not target_restaurant and "restaurant_id" in request.path_params:
            try:
                r_id = int(request.path_params["restaurant_id"])
                target_restaurant = db.query(Restaurant).filter(Restaurant.id == r_id).first()
            except Exception:
                pass

        if not target_restaurant:
            target_restaurant = db.query(Restaurant).order_by(Restaurant.id.desc()).first()

        if not target_restaurant:
            target_restaurant = Restaurant(
                name="Legacy Mock Restaurant",
                address="123 Test St",
                latitude=6.5,
                longitude=3.3
            )
            db.add(target_restaurant)
            db.commit()
            db.refresh(target_restaurant)

        if target_restaurant.user:
            return target_restaurant.user

        user = User(
            name=f"Owner of {target_restaurant.name}",
            email=f"rest_legacy_{target_restaurant.id}@foodrescue.test",
            role=UserRole.RESTAURANT,
            clerk_id=f"clerk_rest_legacy_{target_restaurant.id}"
        )
        db.add(user)
        db.flush()
        target_restaurant.user_id = user.id
        db.commit()
        db.refresh(user)
        return user

    def _get_or_create_ngo_user(request: Request, db: Session = Depends(get_db)) -> User:
        import uuid

        # When creating a new NGO, provide a user without an existing NGO
        if request.method == "POST" and request.url.path == "/ngos/":
            uid = uuid.uuid4().hex[:8]
            user = User(
                name=f"New NGO Rep {uid}",
                email=f"new_ngo_rep_{uid}@foodrescue.test",
                role=UserRole.NGO,
                clerk_id=f"clerk_new_ngo_{uid}"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

        target_ngo = None
        if "match_id" in request.path_params:
            try:
                m_id = int(request.path_params["match_id"])
                match_rec = db.query(Match).filter(Match.id == m_id).first()
                if match_rec and match_rec.ngo:
                    target_ngo = match_rec.ngo
            except Exception:
                pass

        if not target_ngo and "ngo_id" in request.query_params:
            try:
                n_id = int(request.query_params["ngo_id"])
                target_ngo = db.query(NGO).filter(NGO.id == n_id).first()
            except Exception:
                pass


        if not target_ngo and "ngo_id" in request.path_params:
            try:
                n_id = int(request.path_params["ngo_id"])
                target_ngo = db.query(NGO).filter(NGO.id == n_id).first()
            except Exception:
                pass

        if not target_ngo:
            target_ngo = db.query(NGO).order_by(NGO.id.desc()).first()

        if not target_ngo:
            target_ngo = NGO(
                name="Legacy Mock NGO",
                address="456 Test Way",
                latitude=6.51,
                longitude=3.31,
                beneficiary_count=100,
                food_requirements="Any",
                capacity=200,
                pickup_available=True
            )
            db.add(target_ngo)
            db.commit()
            db.refresh(target_ngo)

        if target_ngo.user:
            return target_ngo.user

        user = User(
            name=f"Rep of {target_ngo.name}",
            email=f"ngo_legacy_{target_ngo.id}@foodrescue.test",
            role=UserRole.NGO,
            clerk_id=f"clerk_ngo_legacy_{target_ngo.id}"
        )
        db.add(user)
        db.flush()
        target_ngo.user_id = user.id
        db.commit()
        db.refresh(user)
        return user

    def _get_or_create_current_user(request: Request, db: Session = Depends(get_db)) -> User:
        # Check if URL belongs to restaurant, NGO, or donation
        path = request.url.path
        if "/restaurants" in path or "/donations" in path:
            return _get_or_create_restaurant_user(request, db)
        elif "/ngos" in path:
            return _get_or_create_ngo_user(request, db)
        else:
            return _get_or_create_restaurant_user(request, db)

    def _mock_claims():
        return {"sub": "clerk_legacy_user", "email": "legacy@foodrescue.test"}

    app.dependency_overrides[get_current_clerk_claims] = _mock_claims
    app.dependency_overrides[get_current_user] = _get_or_create_current_user
    app.dependency_overrides[get_current_restaurant_user] = _get_or_create_restaurant_user
    app.dependency_overrides[get_current_ngo_user] = _get_or_create_ngo_user

    yield

    app.dependency_overrides.pop(get_current_clerk_claims, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_restaurant_user, None)
    app.dependency_overrides.pop(get_current_ngo_user, None)

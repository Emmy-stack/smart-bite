import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import engine, Base
from app.models import User, Restaurant, NGO, FoodDonation, Match  # Ensure models are loaded
from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.restaurants import router as restaurants_router
from app.routes.ngos import router as ngos_router
from app.routes.donations import router as donations_router
from app.routes.matches import router as matches_router
from app.routes.forecasting import router as forecasting_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist and apply safe idempotent column additions
    try:
        from sqlalchemy import text
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE food_donations ADD COLUMN IF NOT EXISTS accepted_ngo_id INTEGER REFERENCES ngos(id) ON DELETE SET NULL;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS clerk_id VARCHAR(128);"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_clerk_id ON users (clerk_id) WHERE clerk_id IS NOT NULL;"))
            conn.commit()
        print("Database tables and migration columns initialized successfully.")
    except Exception as e:
        print(f"Warning: Database initialization encountered an error: {e}")

    # Validate authentication configuration at startup in live environments
    if "PYTEST_CURRENT_TEST" not in os.environ:
        try:
            from app.config import settings
            settings.validate_auth_config()
            print("Clerk authentication configuration validated successfully.")
        except Exception as e:
            print(f"Auth configuration notice: {e}")

    yield
    # Shutdown logic (if any)

app = FastAPI(
    title=os.getenv("APP_NAME", "SmartBite API"),
    description="Backend API for SmartBite — AI-powered food redistribution platform connecting restaurants to NGOs.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,https://smart-bite-app-snowy.vercel.app")
origins = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]
if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers for clean and standardized error responses
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append({
            "field": field,
            "message": err.get("msg", "Invalid input"),
            "type": err.get("type", "value_error")
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "Validation error in request payload",
            "errors": errors
        }
    )

# Root endpoint (Public)
@app.get("/", summary="Root Endpoint")
@app.get("/api", summary="Root API Endpoint")
def read_root():
    return {"message": "SmartBite API is running"}

# Register API routers with direct root paths (e.g. /health, /donations)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(restaurants_router)
app.include_router(ngos_router)
app.include_router(donations_router)
app.include_router(matches_router)
app.include_router(forecasting_router)

# Also register with /api prefix for multi-service rewrite compatibility (e.g. /api/health, /api/donations)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(restaurants_router, prefix="/api")
app.include_router(ngos_router, prefix="/api")
app.include_router(donations_router, prefix="/api")
app.include_router(matches_router, prefix="/api")
app.include_router(forecasting_router, prefix="/api")


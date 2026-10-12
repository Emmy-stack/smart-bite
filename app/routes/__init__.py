from app.routes.health import router as health_router
from app.routes.users import router as users_router
from app.routes.restaurants import router as restaurants_router
from app.routes.ngos import router as ngos_router
from app.routes.donations import router as donations_router
from app.routes.matches import router as matches_router
from app.routes.forecasting import router as forecasting_router

__all__ = [
    "health_router",
    "users_router",
    "restaurants_router",
    "ngos_router",
    "donations_router",
    "matches_router",
    "forecasting_router",
]

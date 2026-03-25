from fastapi import APIRouter

from app.api.routes import auth, foods, reports, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(foods.router, prefix="/foods", tags=["foods"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])

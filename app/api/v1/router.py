from fastapi import APIRouter

from app.api.v1 import admin, auth, content, payments, subscriptions, tutors, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(content.router)
api_router.include_router(subscriptions.router)
api_router.include_router(payments.router)
api_router.include_router(tutors.router)
api_router.include_router(admin.router)
"""Root API router that wires up individual feature routers."""

from fastapi import APIRouter

from .routes import auth, batches, health, jobs, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(batches.router, prefix="/job-batches", tags=["job-batches"])

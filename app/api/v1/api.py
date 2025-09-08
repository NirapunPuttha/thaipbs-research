from fastapi import APIRouter
from app.api.v1.endpoints import auth, articles, admin, users, files, analytics, activity, profile

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(articles.router, prefix="/articles", tags=["Articles"]) 
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])
api_router.include_router(files.router, prefix="/files", tags=["Files"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(activity.router, prefix="/activity", tags=["Activity"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
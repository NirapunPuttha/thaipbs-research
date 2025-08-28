from typing import Optional, List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.database import get_database
from app.core.security import get_current_user, get_current_admin_user
from app.models.user import UserResponse
from app.services.activity_service import ActivityService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/user/{user_id}")
async def get_user_activity(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get user's activity history (user can only see their own, admins can see anyone's)"""
    try:
        # Check if user can access this activity log
        if current_user.id != user_id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own activity"
            )
        
        service = ActivityService(db)
        activities = await service.get_user_activity(
            user_id=user_id,
            days=days,
            limit=limit,
            action_filter=action
        )
        
        return {
            "user_id": user_id,
            "activities": activities,
            "total_returned": len(activities),
            "period_days": days
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user activity"
        )

@router.get("/my-activity")
async def get_my_activity(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get current user's activity history"""
    try:
        service = ActivityService(db)
        activities = await service.get_user_activity(
            user_id=current_user.id,
            days=days,
            limit=limit,
            action_filter=action
        )
        
        return {
            "user_id": current_user.id,
            "activities": activities,
            "total_returned": len(activities),
            "period_days": days
        }
        
    except Exception as e:
        logger.error(f"Error getting my activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get activity"
        )

@router.get("/article/{article_id}")
async def get_article_activity(
    article_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get activity history for a specific article (admin only)"""
    try:
        service = ActivityService(db)
        activities = await service.get_article_activity(
            article_id=article_id,
            days=days,
            limit=limit
        )
        
        return {
            "article_id": article_id,
            "activities": activities,
            "total_returned": len(activities),
            "period_days": days
        }
        
    except Exception as e:
        logger.error(f"Error getting article activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get article activity"
        )

@router.get("/system")
async def get_system_activity(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get system-wide activity (admin only)"""
    try:
        service = ActivityService(db)
        activities = await service.get_system_activity(
            days=days,
            limit=limit,
            action_filter=action,
            entity_type_filter=entity_type
        )
        
        return {
            "activities": activities,
            "total_returned": len(activities),
            "period_days": days,
            "filters": {
                "action": action,
                "entity_type": entity_type
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting system activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system activity"
        )

@router.get("/summary")
async def get_activity_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get activity summary statistics (admin only)"""
    try:
        service = ActivityService(db)
        summary = await service.get_activity_summary(days=days)
        
        if not summary:
            return {
                "period_days": days,
                "total_activities": 0,
                "activities_by_action": {},
                "activities_by_entity": {},
                "top_activities": []
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting activity summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get activity summary"
        )

@router.get("/actions")
async def get_available_actions(
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get list of available action types (admin only)"""
    try:
        query = "SELECT DISTINCT action FROM activity_logs ORDER BY action"
        rows = await db.fetch_all(query)
        actions = [row['action'] for row in rows]
        
        return {
            "actions": actions,
            "total": len(actions)
        }
        
    except Exception as e:
        logger.error(f"Error getting available actions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available actions"
        )

@router.get("/entity-types")
async def get_available_entity_types(
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get list of available entity types (admin only)"""
    try:
        query = "SELECT DISTINCT entity_type FROM activity_logs ORDER BY entity_type"
        rows = await db.fetch_all(query)
        entity_types = [row['entity_type'] for row in rows]
        
        return {
            "entity_types": entity_types,
            "total": len(entity_types)
        }
        
    except Exception as e:
        logger.error(f"Error getting available entity types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available entity types"
        )
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from app.core.database import get_database
from app.core.security import get_current_user, get_current_admin_user
from app.models.user import (
    UserResponse, UserProfileUpdate, UserDetailedInfo, 
    DownloadHistoryResponse, UserStats, UserProfileComplete
)
from app.services.user_profile_service import UserProfileService
from app.services.activity_service import ActivityService, ActivityLogger
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get current user's profile"""
    try:
        service = UserProfileService(db)
        profile = await service.get_user_profile(current_user.id)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get profile"
        )

@router.get("/me/complete", response_model=UserProfileComplete)
async def get_my_complete_profile(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get current user's complete profile with stats and detailed info"""
    try:
        service = UserProfileService(db)
        profile = await service.get_complete_user_profile(current_user.id)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting complete user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get complete profile"
        )

@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    profile_data: UserProfileUpdate,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Update current user's profile"""
    try:
        service = UserProfileService(db)
        
        # Get old profile for activity logging
        old_profile = await service.get_user_profile(current_user.id)
        
        updated_profile = await service.update_user_profile(current_user.id, profile_data)
        
        if not updated_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        # Log profile update activity
        try:
            activity_service = ActivityService(db)
            client_ip = request.client.host if request.client else "unknown"
            
            old_values = {
                "username": old_profile.username,
                "first_name": old_profile.first_name,
                "last_name": old_profile.last_name
            }
            
            new_values = {
                "username": updated_profile.username,
                "first_name": updated_profile.first_name,
                "last_name": updated_profile.last_name
            }
            
            await activity_service.log_activity(
                action="update",
                entity_type="profile",
                entity_id=current_user.id,
                user_id=current_user.id,
                old_values=old_values,
                new_values=new_values,
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent")
            )
        except Exception as activity_error:
            logger.warning(f"Failed to log profile update activity: {activity_error}")
        
        return updated_profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.post("/me/detailed-info")
async def submit_detailed_info(
    detailed_info: UserDetailedInfo,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Submit detailed information (required after 5+ downloads)"""
    try:
        service = UserProfileService(db)
        
        success = await service.submit_detailed_info(current_user.id, detailed_info)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to submit detailed information"
            )
        
        # Log detailed info submission
        try:
            activity_service = ActivityService(db)
            client_ip = request.client.host if request.client else "unknown"
            
            await activity_service.log_activity(
                action="submit_detailed_info",
                entity_type="profile",
                entity_id=current_user.id,
                user_id=current_user.id,
                new_values={
                    "detailed_info_submitted": True,
                    "organization": detailed_info.organization
                },
                ip_address=client_ip,
                user_agent=request.headers.get("user-agent")
            )
        except Exception as activity_error:
            logger.warning(f"Failed to log detailed info activity: {activity_error}")
        
        return {"message": "Detailed information submitted successfully"}
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error submitting detailed info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit detailed information"
        )

@router.get("/me/download-history", response_model=DownloadHistoryResponse)
async def get_my_download_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get current user's download history"""
    try:
        service = UserProfileService(db)
        history = await service.get_download_history(
            user_id=current_user.id,
            page=page,
            page_size=page_size
        )
        
        return history
        
    except Exception as e:
        logger.error(f"Error getting download history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get download history"
        )

@router.get("/me/stats", response_model=UserStats)
async def get_my_statistics(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get current user's statistics"""
    try:
        service = UserProfileService(db)
        stats = await service.get_user_statistics(current_user.id)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user statistics"
        )

@router.get("/me/detailed-info-required")
async def check_detailed_info_required(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Check if user needs to submit detailed information"""
    try:
        service = UserProfileService(db)
        required = await service.check_detailed_info_required(current_user.id)
        
        return {
            "detailed_info_required": required,
            "download_count": current_user.download_count,
            "already_submitted": current_user.detailed_info_submitted
        }
        
    except Exception as e:
        logger.error(f"Error checking detailed info requirement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check detailed info requirement"
        )

# Admin endpoints
@router.get("/{user_id}", response_model=UserProfileComplete)
async def get_user_profile_admin(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get any user's complete profile (admin only)"""
    try:
        service = UserProfileService(db)
        profile = await service.get_complete_user_profile(user_id)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile for admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )

@router.get("/{user_id}/download-history", response_model=DownloadHistoryResponse)
async def get_user_download_history_admin(
    user_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get any user's download history (admin only)"""
    try:
        service = UserProfileService(db)
        history = await service.get_download_history(
            user_id=user_id,
            page=page,
            page_size=page_size
        )
        
        return history
        
    except Exception as e:
        logger.error(f"Error getting user download history for admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get download history"
        )

@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_statistics_admin(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get any user's statistics (admin only)"""
    try:
        service = UserProfileService(db)
        stats = await service.get_user_statistics(user_id)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting user statistics for admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user statistics"
        )
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.database import get_database
from app.core.security import get_current_admin_user
from app.models.user import UserResponse, UserCreate, UserUpdate
from app.services.user_management_service import UserManagementService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/")
async def admin_status():
    return {"message": "Admin User Management APIs - Ready"}

# User Management Endpoints
@router.get("/users", response_model=dict)
async def get_all_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username, email, or name"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_admin: Optional[bool] = Query(None, description="Filter by admin status"),
    is_creator: Optional[bool] = Query(None, description="Filter by creator status"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by user level"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get paginated list of all users with filters (admin only)"""
    try:
        service = UserManagementService(db)
        result = await service.get_all_users(
            page=page,
            page_size=page_size,
            search=search,
            is_active=is_active,
            is_admin=is_admin,
            is_creator=is_creator,
            level=level,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return result
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get user by ID (admin only)"""
    try:
        service = UserManagementService(db)
        user = await service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Create new user (admin only)"""
    try:
        service = UserManagementService(db)
        new_user = await service.create_user(user_data)
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    update_data: UserUpdate,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Update user (admin only)"""
    try:
        service = UserManagementService(db)
        updated_user = await service.update_user(user_id, update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    hard_delete: bool = Query(False, description="Permanently delete user (default: soft delete)"),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Delete user - soft delete by default, hard delete with parameter (admin only)"""
    try:
        # Prevent self-deletion
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        service = UserManagementService(db)
        success = await service.delete_user(user_id, soft_delete=not hard_delete)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or cannot be deleted"
            )
        
        return {
            "message": f"User {'permanently deleted' if hard_delete else 'deactivated'} successfully",
            "user_id": user_id,
            "hard_delete": hard_delete
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    new_password: str = Query(..., min_length=8, description="New password (min 8 characters)"),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Reset user password (admin only)"""
    try:
        service = UserManagementService(db)
        success = await service.reset_user_password(user_id, new_password)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "message": "Password reset successfully",
            "user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

@router.get("/statistics")
async def get_user_statistics(
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get user statistics for admin dashboard"""
    try:
        service = UserManagementService(db)
        stats = await service.get_user_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )

# Additional admin utilities
@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Activate deactivated user (admin only)"""
    try:
        service = UserManagementService(db)
        update_data = UserUpdate(is_active=True)
        updated_user = await service.update_user(user_id, update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "message": "User activated successfully",
            "user_id": user_id,
            "user": updated_user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user"
        )

@router.post("/users/{user_id}/promote")
async def promote_user_to_admin(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Promote user to admin (super admin only)"""
    try:
        service = UserManagementService(db)
        update_data = UserUpdate(is_admin=True, level=3)
        updated_user = await service.update_user(user_id, update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "message": "User promoted to admin successfully",
            "user_id": user_id,
            "user": updated_user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error promoting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to promote user"
        )
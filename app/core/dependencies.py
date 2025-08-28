from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from uuid import UUID
from app.models.user import UserResponse
from app.services.user_service import UserService
from app.core.database import get_database, DatabaseManager
from app.core.security import verify_token
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Service dependencies
async def get_user_service(db: DatabaseManager = Depends(get_database)) -> UserService:
    """Get UserService instance"""
    return UserService(db)

# Authentication dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Get current authenticated user"""
    try:
        # Verify access token
        payload = verify_token(credentials.credentials, token_type="access")
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        user = await user_service.get_user_by_id(UUID(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    user_service: UserService = Depends(get_user_service)
) -> Optional[UserResponse]:
    """Get current authenticated user (optional - for public endpoints)"""
    if not credentials:
        return None
        
    try:
        payload = verify_token(credentials.credentials, token_type="access")
        
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user = await user_service.get_user_by_id(UUID(user_id))
        return user
        
    except Exception as e:
        logger.debug(f"Optional authentication failed: {e}")
        return None

# Authorization dependencies
async def require_admin(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """Require admin privileges"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

async def require_level(min_level: int):
    """Require minimum user level"""
    async def _require_level(
        current_user: UserResponse = Depends(get_current_user)
    ) -> UserResponse:
        if current_user.level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User level {min_level} or higher required"
            )
        return current_user
    return _require_level

async def require_level_2(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """Require level 2 or higher"""
    if current_user.level < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User level 2 or higher required"
        )
    return current_user

async def require_level_3(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """Require level 3 or higher"""
    if current_user.level < 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User level 3 or higher required"
        )
    return current_user

async def require_author_or_admin(article_author_id: UUID):
    """Require article author or admin privileges"""
    async def _require_author_or_admin(
        current_user: UserResponse = Depends(get_current_user)
    ) -> UserResponse:
        if not current_user.is_admin and current_user.id != article_author_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Author or admin privileges required"
            )
        return current_user
    return _require_author_or_admin

# Utility functions
def get_user_id_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Extract user ID from JWT token"""
    payload = verify_token(credentials.credentials, token_type="access")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return user_id
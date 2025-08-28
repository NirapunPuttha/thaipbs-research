from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from app.models.user import (
    UserCreate, UserLogin, UserResponse, Token, RefreshToken,
    UserProfileUpdate, UserDetailedInfo
)
from app.services.user_service import UserService
from app.services.file_service import FileService
from app.core.dependencies import get_user_service, get_current_user
from app.core.database import get_database, DatabaseManager
from app.core.security import create_tokens_for_user, verify_token
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# File service dependency
async def get_file_service(db: DatabaseManager = Depends(get_database)) -> FileService:
    return FileService(db)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service)
):
    """Register a new user"""
    try:
        user = await user_service.create_user(user_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/login", response_model=Token)
async def login(
    user_credentials: UserLogin,
    user_service: UserService = Depends(get_user_service)
):
    """Login user and return JWT tokens"""
    try:
        user = await user_service.authenticate_user(
            user_credentials.email,
            user_credentials.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Create tokens
        tokens = create_tokens_for_user(str(user.id), user.email)
        
        return Token(**tokens)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshToken,
    user_service: UserService = Depends(get_user_service)
):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        payload = verify_token(refresh_data.refresh_token, token_type="refresh")
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Verify user still exists and is active
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new tokens
        tokens = create_tokens_for_user(user_id, email)
        
        return Token(**tokens)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refresh token error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get current authenticated user"""
    return current_user

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Update user profile"""
    try:
        updated_user = await user_service.update_user_profile(current_user.id, profile_data)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return updated_user
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/detailed-info", response_model=UserResponse)
async def submit_detailed_info(
    detailed_info: UserDetailedInfo,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Submit detailed user information (required after 5+ downloads)"""
    try:
        # Check if user has 5+ downloads
        if current_user.download_count < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Detailed information required only after 5 downloads"
            )
        
        updated_user = await user_service.submit_detailed_info(current_user.id, detailed_info)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit detailed info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/upload-profile-image", response_model=UserResponse)
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
):
    """Upload user profile image"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        updated_user = await file_service.upload_profile_image(current_user.id, file)
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile image upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image upload failed"
        )

@router.delete("/delete-profile-image", response_model=UserResponse)
async def delete_profile_image(
    current_user: UserResponse = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
):
    """Delete user profile image"""
    try:
        updated_user = await file_service.delete_profile_image(current_user.id)
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile image deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image deletion failed"
        )
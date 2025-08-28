from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response
from fastapi.responses import FileResponse
from pathlib import Path
import os
import logging

from app.core.database import get_database
from app.core.security import get_current_admin_user, get_current_user, get_optional_current_user
from app.models.user import UserResponse
from app.models.article import ArticleFileResponse
from app.services.file_service import FileService

router = APIRouter()
logger = logging.getLogger(__name__)

# Profile image serving (existing functionality)
@router.get("/uploads/profiles/{filename}")
async def get_profile_image(filename: str):
    """Serve profile images"""
    try:
        file_path = os.path.join("uploads/profiles", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        return FileResponse(
            file_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "max-age=3600"}  # Cache for 1 hour
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving profile image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve image"
        )

# Article file management endpoints
@router.post("/articles/upload/{article_id}", response_model=ArticleFileResponse)
async def upload_article_file(
    article_id: UUID,
    file: UploadFile = File(...),
    youtube_url: Optional[str] = Form(None),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Upload file for article (admin only)"""
    try:
        service = FileService(db)
        
        # Validate file size (50MB limit)
        if file.size and file.size > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 50MB limit"
            )
        
        # Upload file
        file_record = await service.upload_article_file(
            file=file,
            article_id=article_id,
            uploaded_by=current_user.id,
            youtube_url=youtube_url
        )
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File upload failed"
            )
        
        return file_record
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file for article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )

@router.post("/articles/youtube/{article_id}", response_model=ArticleFileResponse)
async def add_youtube_video(
    article_id: UUID,
    youtube_url: str = Form(...),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Add YouTube video to article (admin only)"""
    try:
        service = FileService(db)
        
        # Create a mock UploadFile for YouTube (since we don't have actual file)
        class MockUploadFile:
            filename = None
            content_type = None
            async def read(self): return b''
        
        # Upload YouTube video record
        file_record = await service.upload_article_file(
            file=MockUploadFile(),
            article_id=article_id,
            uploaded_by=current_user.id,
            youtube_url=youtube_url
        )
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="YouTube video add failed"
            )
        
        return file_record
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding YouTube video for article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="YouTube video add failed"
        )

@router.get("/articles/{article_id}", response_model=List[ArticleFileResponse])
async def get_article_files(
    article_id: UUID,
    db = Depends(get_database)
):
    """Get all files for an article (public access)"""
    try:
        service = FileService(db)
        files = await service.get_article_files(article_id)
        return files
        
    except Exception as e:
        logger.error(f"Error getting files for article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get files"
        )

@router.get("/file/{file_id}", response_model=ArticleFileResponse)
async def get_file_info(
    file_id: UUID,
    db = Depends(get_database)
):
    """Get file information by ID"""
    try:
        service = FileService(db)
        file_record = await service.get_file_by_id(file_id)
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        return file_record
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file info"
        )

@router.get("/download/{file_path:path}")
async def download_file(
    file_path: str,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Download file (requires login for PDF files)"""
    try:
        from app.core.config import settings
        
        # Construct full file path
        full_path = Path(settings.UPLOAD_DIR) / file_path
        
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check if it's a PDF and user is logged in
        if full_path.suffix.lower() == '.pdf':
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Login required for PDF download"
                )
        
        # Return file
        return FileResponse(
            path=full_path,
            filename=full_path.name,
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File download failed"
        )

@router.delete("/articles/{file_id}")
async def delete_file(
    file_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Delete file (admin only)"""
    try:
        service = FileService(db)
        
        success = await service.delete_article_file(file_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        return {"message": "File deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File deletion failed"
        )

@router.post("/articles/{file_id}/increment-download")
async def increment_download_count(
    file_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Increment download count (authenticated users only)"""
    try:
        service = FileService(db)
        
        success = await service.increment_download_count(file_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        return {"message": "Download count updated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating download count for file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update download count"
        )
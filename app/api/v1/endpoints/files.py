from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response, Request
from fastapi.responses import FileResponse
from pathlib import Path
import os
import logging

from app.core.database import get_database
from app.core.security import get_current_admin_user, get_current_user, get_optional_current_user
from app.models.user import UserResponse
from app.models.article import ArticleFileResponse
from app.services.file_service import FileService
from app.services.user_profile_service import UserProfileService
from app.services.activity_service import ActivityService, ActivityLogger
from app.utils.image_processor import image_processor
from app.services.minio_service import minio_service
from app.core.config import settings

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
    request: Request,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Download file (requires login for PDF files) - supports both MinIO and local storage"""
    try:
        from fastapi.responses import RedirectResponse
        
        # Check if it's a MinIO object path
        if settings.FILE_STORAGE_TYPE == "minio" and (
            file_path.startswith("profiles/") or 
            file_path.startswith("articles/") or 
            file_path.startswith("covers/")
        ):
            # Generate presigned URL for MinIO
            presigned_url = await minio_service.generate_presigned_url(file_path)
            
            if presigned_url:
                # Check authentication for PDFs
                if file_path.endswith('.pdf') and not current_user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Login required for PDF download"
                    )
                
                # Log download for MinIO files
                if current_user:
                    try:
                        file_service = FileService(db)
                        file_info = await file_service.get_file_by_path(file_path)
                        
                        profile_service = UserProfileService(db)
                        client_ip = request.client.host if request.client else "unknown"
                        
                        file_id = file_info.id if file_info else UUID("00000000-0000-0000-0000-000000000000")
                        article_id = file_info.article_id if file_info else None
                        file_name = Path(file_path).name
                        file_type = Path(file_path).suffix.lower().replace('.', '') or 'unknown'
                        
                        # Get file info from MinIO
                        minio_info = await minio_service.get_file_info(file_path)
                        file_size = minio_info['size'] if minio_info else 0
                        
                        await profile_service.log_file_download(
                            user_id=current_user.id,
                            file_id=file_id,
                            article_id=article_id,
                            file_name=file_name,
                            file_type=file_type,
                            file_size=file_size,
                            ip_address=client_ip
                        )
                    except Exception as log_error:
                        logger.warning(f"Failed to log MinIO download: {log_error}")
                
                # Redirect to presigned URL
                return RedirectResponse(url=presigned_url, status_code=302)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found in MinIO"
                )
        
        # Fallback to local file serving
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
        
        # Check download quota for logged in users
        if current_user:
            from app.core.config import settings
            
            # Determine quota based on user registration status
            if current_user.detailed_info_submitted:
                quota_limit = settings.DOWNLOAD_QUOTA_DETAILED
            else:
                quota_limit = settings.DOWNLOAD_QUOTA_BASIC
            
            # Check if user has exceeded quota
            if current_user.download_count >= quota_limit:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error_type": "download_quota_exceeded",
                        "message": "คุณได้ดาวน์โหลดเกินโควต้าแล้ว กรุณาลงทะเบียนข้อมูลเพิ่มเติมเพื่อดาวน์โหลดได้ไม่จำกัด",
                        "current_downloads": current_user.download_count,
                        "quota_limit": quota_limit,
                        "action_required": "complete_registration",
                        "registration_required": not current_user.detailed_info_submitted
                    }
                )
            
            # Send warning if approaching quota (80% of limit)
            remaining_downloads = quota_limit - current_user.download_count
            if remaining_downloads <= max(1, quota_limit * 0.2):  # 20% remaining or 1 download left
                logger.info(f"User {current_user.id} approaching download quota: {remaining_downloads} downloads remaining")
        
        # Get file info from database to get proper file_id and article_id
        file_service = FileService(db)
        file_info = await file_service.get_file_by_path(file_path)
        
        # Log download
        try:
            profile_service = UserProfileService(db)
            client_ip = request.client.host if request.client else "unknown"
            
            # Extract file information
            file_id = file_info.id if file_info else UUID("00000000-0000-0000-0000-000000000000")
            article_id = file_info.article_id if file_info else None
            file_size = full_path.stat().st_size
            file_type = full_path.suffix.lower().replace('.', '') or 'unknown'
            
            await profile_service.log_file_download(
                user_id=current_user.id if current_user else None,
                file_id=file_id,
                article_id=article_id,
                file_name=full_path.name,
                file_type=file_type,
                file_size=file_size,
                ip_address=client_ip
            )
            
            # Also log activity
            if current_user:
                activity_service = ActivityService(db)
                await ActivityLogger.log_file_download(
                    activity_service=activity_service,
                    file_id=file_id,
                    article_id=article_id,
                    user_id=current_user.id,
                    ip_address=client_ip,
                    user_agent=request.headers.get("user-agent")
                )
                
        except Exception as log_error:
            # Don't fail download if logging fails
            logger.warning(f"Failed to log download: {log_error}")
        
        # Prepare headers with quota information
        headers = {}
        if current_user:
            if current_user.detailed_info_submitted:
                quota_limit = settings.DOWNLOAD_QUOTA_DETAILED
            else:
                quota_limit = settings.DOWNLOAD_QUOTA_BASIC
                
            remaining_downloads = quota_limit - (current_user.download_count + 1)  # +1 because this download will count
            headers.update({
                "X-Download-Quota-Limit": str(quota_limit),
                "X-Download-Quota-Used": str(current_user.download_count + 1),
                "X-Download-Quota-Remaining": str(remaining_downloads),
                "X-Registration-Required": str(not current_user.detailed_info_submitted).lower()
            })
            
            # Add warning header if approaching limit
            if remaining_downloads <= max(1, quota_limit * 0.2):
                headers["X-Download-Warning"] = "approaching_limit"
        
        # Return file
        return FileResponse(
            path=full_path,
            filename=full_path.name,
            media_type="application/octet-stream",
            headers=headers
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

@router.post("/covers/upload/{article_id}")
async def upload_cover_image(
    article_id: UUID,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Upload cover image for article (admin only)"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image files are allowed for cover images"
            )
        
        # Validate file size (10MB limit for cover images)
        if file.size and file.size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Cover image size exceeds 10MB limit"
            )
        
        # Validate image
        file_content = await file.read()
        image_processor.validate_image_file(file.content_type, len(file_content))
        
        # Process cover image
        file_path, public_url = await image_processor.process_cover_image(
            file_content, file.filename or "cover_image"
        )
        
        # Update article with cover image URL
        from app.services.article_service import ArticleService
        article_service = ArticleService(db)
        
        # Check if article exists
        existing_article = await article_service.get_article_detail(article_id)
        if not existing_article:
            # Clean up uploaded file
            try:
                os.remove(file_path)
            except:
                pass
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # Update article cover image
        from app.models.article import ArticleUpdate
        update_data = ArticleUpdate(cover_image_url=public_url)
        updated_article = await article_service.update_article(article_id, update_data)
        
        if not updated_article:
            # Clean up uploaded file if update failed
            try:
                os.remove(file_path)
            except:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update article with cover image"
            )
        
        # Log activity
        try:
            activity_service = ActivityService(db)
            await activity_service.log_activity(
                activity_type="cover_upload",
                user_id=current_user.id,
                article_id=article_id,
                description=f"Cover image uploaded: {file.filename}",
                new_values={"cover_image_url": public_url}
            )
        except Exception as activity_error:
            logger.warning(f"Failed to log cover upload activity: {activity_error}")
        
        return {
            "message": "Cover image uploaded successfully",
            "cover_image_url": public_url,
            "file_path": file_path,
            "article_id": article_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading cover image for article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cover image upload failed"
        )

@router.get("/uploads/covers/{filename}")
async def get_cover_image(filename: str):
    """Serve cover images"""
    try:
        file_path = os.path.join("uploads/covers", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cover image not found"
            )
        
        return FileResponse(
            file_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "max-age=3600"}  # Cache for 1 hour
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving cover image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve cover image"
        )

@router.get("/uploads/articles/{filename}")
async def get_article_image(filename: str):
    """Serve article images"""
    try:
        file_path = os.path.join("uploads/articles", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article image not found"
            )
        
        return FileResponse(
            file_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "max-age=3600"}  # Cache for 1 hour
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving article image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve article image"
        )

# MinIO specific endpoints
@router.get("/minio/presigned-url/{object_name:path}")
async def get_presigned_url(
    object_name: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Generate presigned URL for MinIO object (authenticated users only)"""
    try:
        if settings.FILE_STORAGE_TYPE != "minio":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MinIO is not enabled"
            )
        
        # Check if object exists
        exists = await minio_service.file_exists(object_name)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Generate presigned URL
        presigned_url = await minio_service.generate_presigned_url(object_name)
        
        if not presigned_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate presigned URL"
            )
        
        return {
            "object_name": object_name,
            "presigned_url": presigned_url,
            "expires_in": "7 days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating presigned URL for {object_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL"
        )

@router.get("/minio/upload-url/{folder}/{filename}")
async def get_upload_presigned_url(
    folder: str,
    filename: str,
    current_user: UserResponse = Depends(get_current_admin_user)
):
    """Generate presigned URL for MinIO file upload (admin only)"""
    try:
        if settings.FILE_STORAGE_TYPE != "minio":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MinIO is not enabled"
            )
        
        # Generate object name
        object_name = minio_service.generate_object_name(filename, folder)
        
        # Generate presigned upload URL
        from datetime import timedelta
        upload_url = await minio_service.generate_upload_presigned_url(
            object_name, expires=timedelta(hours=1)
        )
        
        if not upload_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate upload URL"
            )
        
        return {
            "object_name": object_name,
            "upload_url": upload_url,
            "expires_in": "1 hour",
            "public_url": f"{settings.minio_base_url}/{object_name}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating upload URL for {folder}/{filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL"
        )
import os
import logging
import shutil
from typing import Optional, List, Tuple
from uuid import UUID, uuid4
from pathlib import Path
from PIL import Image
import mimetypes
from datetime import datetime
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.core.database import DatabaseManager
from app.utils.image_processor import image_processor
from app.models.user import UserResponse
from app.models.article import ArticleFileResponse, FileType
from app.services.minio_service import minio_service

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.upload_dir = Path(settings.UPLOAD_DIR) if hasattr(settings, 'UPLOAD_DIR') else Path("uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.use_minio = settings.FILE_STORAGE_TYPE == "minio"
    
    async def _save_file_to_storage(
        self, 
        file_data: bytes, 
        filename: str, 
        folder: str, 
        content_type: str = None
    ) -> Tuple[str, str, str]:
        """
        Save file to either MinIO or local storage
        Returns: (storage_type, file_path_or_object_name, public_url)
        """
        if self.use_minio:
            # Save to MinIO
            object_name = minio_service.generate_object_name(filename, folder)
            success, public_url = await minio_service.upload_file(
                file_data, object_name, content_type
            )
            
            if not success:
                raise HTTPException(status_code=500, detail="Failed to upload to MinIO")
            
            return "minio", object_name, public_url
        else:
            # Save to local storage (existing logic)
            file_extension = Path(filename).suffix.lower()
            unique_filename = f"{uuid4()}{file_extension}"
            
            # Create folder structure
            folder_path = self.upload_dir / folder
            folder_path.mkdir(parents=True, exist_ok=True)
            
            file_path = folder_path / unique_filename
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # Generate relative URL
            relative_path = f"{folder}/{unique_filename}"
            public_url = f"/api/v1/files/uploads/{relative_path}"
            
            return "local", str(file_path), public_url
    
    async def _delete_file_from_storage(self, storage_type: str, file_path_or_object: str) -> bool:
        """Delete file from storage based on storage type"""
        if storage_type == "minio":
            return await minio_service.delete_file(file_path_or_object)
        else:
            # Delete local file
            try:
                if os.path.exists(file_path_or_object):
                    os.remove(file_path_or_object)
                    return True
                return False
            except Exception as e:
                logger.error(f"Failed to delete local file {file_path_or_object}: {e}")
                return False
    
    async def upload_profile_image(self, user_id: UUID, file: UploadFile) -> UserResponse:
        """
        Upload and process user profile image
        """
        try:
            # Validate file
            if not file.content_type:
                raise HTTPException(status_code=400, detail="File content type not provided")
            
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            # Validate image
            image_processor.validate_image_file(file.content_type, file_size)
            
            # Get current user to check if has existing image
            current_user = await self._get_user_by_id(user_id)
            if not current_user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Delete old profile image if exists
            old_storage_type = current_user.get('profile_storage_type', 'local')
            old_file_path = current_user.get('profile_image_path')
            old_minio_object = current_user.get('profile_image_minio_object')
            
            if old_storage_type == 'minio' and old_minio_object:
                await self._delete_file_from_storage('minio', old_minio_object)
            elif old_storage_type == 'local' and old_file_path:
                await image_processor.delete_profile_image(old_file_path)
            
            # Process and save image
            if self.use_minio:
                # Process image and save to MinIO
                processed_content, _ = self._process_image(file_content, file.filename or "profile_image")
                storage_type, minio_object, public_url = await self._save_file_to_storage(
                    processed_content, file.filename or "profile_image.jpg", "profiles", file.content_type
                )
                file_path = None  # MinIO doesn't use local file paths
            else:
                # Use existing image processor for local storage
                file_path, public_url = await image_processor.process_profile_image(
                    file_content, file.filename or "profile_image"
                )
                storage_type = "local"
                minio_object = None
            
            # Update user record
            updated_user = await self._update_user_profile_image(
                user_id, file_path, public_url, storage_type, minio_object
            )
            
            if not updated_user:
                # Clean up uploaded file if database update failed
                if storage_type == 'minio' and minio_object:
                    await self._delete_file_from_storage('minio', minio_object)
                elif file_path:
                    await image_processor.delete_profile_image(file_path)
                raise HTTPException(status_code=500, detail="Failed to update user profile")
            
            logger.info(f"Profile image uploaded for user {user_id}: {public_url}")
            return UserResponse(**updated_user)
            
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Profile image upload failed: {e}")
            raise HTTPException(status_code=500, detail="Image upload failed")
    
    async def delete_profile_image(self, user_id: UUID) -> UserResponse:
        """
        Delete user profile image
        """
        try:
            # Get current user
            current_user = await self._get_user_by_id(user_id)
            if not current_user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Delete file if exists
            if current_user.get('profile_image_path'):
                await image_processor.delete_profile_image(current_user['profile_image_path'])
            
            # Update database
            updated_user = await self._update_user_profile_image(user_id, None, None)
            
            if not updated_user:
                raise HTTPException(status_code=500, detail="Failed to update user profile")
            
            logger.info(f"Profile image deleted for user {user_id}")
            return UserResponse(**updated_user)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Profile image deletion failed: {e}")
            raise HTTPException(status_code=500, detail="Image deletion failed")
    
    async def _get_user_by_id(self, user_id: UUID) -> Optional[dict]:
        """Get user by ID including profile image fields"""
        query = """
        SELECT id, email, username, first_name, last_name, level, is_admin, 
               is_active, download_count, detailed_info_submitted, 
               profile_image_url, profile_image_path, profile_image_minio_object,
               profile_storage_type, created_at, updated_at
        FROM users 
        WHERE id = $1 AND is_active = true
        """
        
        row = await self.db.fetch_one(query, user_id)
        return dict(row) if row else None
    
    async def _update_user_profile_image(
        self, 
        user_id: UUID, 
        file_path: Optional[str], 
        public_url: Optional[str],
        storage_type: str = 'local',
        minio_object: Optional[str] = None
    ) -> Optional[dict]:
        """Update user profile image in database"""
        query = """
        UPDATE users 
        SET profile_image_path = $1, profile_image_url = $2, profile_storage_type = $3,
            profile_image_minio_object = $4, updated_at = NOW()
        WHERE id = $5
        RETURNING id, email, username, first_name, last_name, level, is_admin, 
                  is_active, download_count, detailed_info_submitted,
                  profile_image_url, profile_image_path, profile_image_minio_object,
                  profile_storage_type, created_at, updated_at
        """
        
        row = await self.db.fetch_one(query, file_path, public_url, storage_type, minio_object, user_id)
        return dict(row) if row else None
    
    # Article file management methods
    async def upload_article_file(
        self, 
        file: UploadFile, 
        article_id: UUID, 
        uploaded_by: UUID,
        youtube_url: Optional[str] = None
    ) -> Optional[ArticleFileResponse]:
        """Upload and process article file"""
        try:
            if youtube_url:
                return await self._save_youtube_file(article_id, uploaded_by, youtube_url)
            
            if not file.filename:
                raise ValueError("Filename is required")
                
            # Read file content
            file_content = await file.read()
            
            # Determine file type
            file_type, mime_type = self._get_file_type_and_mime(file.filename, file.content_type)
            
            # Create unique filename
            file_extension = Path(file.filename).suffix.lower()
            unique_filename = f"{uuid4()}{file_extension}"
            file_path = self.upload_dir / str(article_id) / unique_filename
            
            # Create directory if not exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Process image if needed using ImageProcessor
            if file_type == FileType.IMAGE:
                try:
                    processed_path, processed_url = await image_processor.process_article_image(
                        file_content, file.filename or "article_image"
                    )
                    # Use processed image info
                    file_path = Path(processed_path)
                    file_url = processed_url
                    file_size = file_path.stat().st_size
                    logger.info(f"Article image optimized: {file.filename} -> {processed_path}")
                except Exception as img_error:
                    logger.warning(f"Image optimization failed, using fallback: {img_error}")
                    processed_content, processed_size = self._process_image(file_content, file.filename)
                    file_content = processed_content
                    file_size = processed_size
                    
                    # Save file to disk (fallback)
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    
                    # Generate file URL (relative to upload directory)
                    relative_path = str(file_path.relative_to(self.upload_dir))
                    file_url = f"/api/v1/files/download/{relative_path}"
            else:
                file_size = len(file_content)
                # Save file to disk (non-image files)
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                # Generate file URL (relative to upload directory)
                relative_path = str(file_path.relative_to(self.upload_dir))
                file_url = f"/api/v1/files/download/{relative_path}"
            
            # Save to database
            file_record = await self._save_file_record(
                article_id=article_id,
                file_type=file_type,
                original_name=file.filename,
                file_path=str(file_path),
                file_url=file_url,
                file_size=file_size,
                mime_type=mime_type,
                uploaded_by=uploaded_by
            )
            
            logger.info(f"Article file uploaded: {file.filename} -> {unique_filename}")
            return file_record
            
        except Exception as e:
            logger.error(f"Error uploading article file {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    
    async def get_article_files(self, article_id: UUID) -> List[ArticleFileResponse]:
        """Get all files for an article"""
        query = """
        SELECT id, article_id, file_type, original_name, file_path, file_url,
               youtube_url, youtube_embed_id, file_size, mime_type,
               download_count, uploaded_by, created_at
        FROM article_files
        WHERE article_id = $1
        ORDER BY created_at
        """
        
        rows = await self.db.fetch_all(query, article_id)
        return [ArticleFileResponse(**dict(row)) for row in rows]
    
    async def get_file_by_id(self, file_id: UUID) -> Optional[ArticleFileResponse]:
        """Get file by ID"""
        query = """
        SELECT id, article_id, file_type, original_name, file_path, file_url,
               youtube_url, youtube_embed_id, file_size, mime_type,
               download_count, uploaded_by, created_at
        FROM article_files
        WHERE id = $1
        """
        
        row = await self.db.fetch_one(query, file_id)
        return ArticleFileResponse(**dict(row)) if row else None

    async def get_file_by_path(self, file_path: str) -> Optional[ArticleFileResponse]:
        """Get file by file path"""
        try:
            query = """
            SELECT id, article_id, file_type, original_name, file_path, file_url,
                   youtube_url, youtube_embed_id, file_size, mime_type, 
                   download_count, uploaded_by, created_at
            FROM article_files
            WHERE file_path = $1 OR file_url LIKE $2
            """
            
            # Try to match both file_path directly and file_url pattern
            url_pattern = f"%{file_path}"
            row = await self.db.fetch_one(query, file_path, url_pattern)
            
            if not row:
                return None
                
            return ArticleFileResponse(**dict(row))
            
        except Exception as e:
            logger.error(f"Error getting file by path: {e}")
            return None  # Return None instead of raising to not break download
    
    async def delete_article_file(self, file_id: UUID) -> bool:
        """Delete article file from database and disk"""
        try:
            # Get file info first
            file_record = await self.get_file_by_id(file_id)
            if not file_record:
                return False
            
            # Delete from database
            delete_query = "DELETE FROM article_files WHERE id = $1"
            result = await self.db.execute_query(delete_query, file_id)
            
            # Delete from disk if it's not a YouTube file
            if file_record.file_type != FileType.YOUTUBE and file_record.file_path:
                file_path = Path(file_record.file_path)
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"File deleted from disk: {file_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            raise HTTPException(status_code=500, detail=f"File deletion failed: {str(e)}")
    
    async def increment_download_count(self, file_id: UUID) -> bool:
        """Increment download count for a file"""
        try:
            query = """
            UPDATE article_files 
            SET download_count = download_count + 1 
            WHERE id = $1
            """
            result = await self.db.execute_query(query, file_id)
            return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Error incrementing download count for file {file_id}: {e}")
            return False
    
    def _get_file_type_and_mime(self, filename: str, content_type: Optional[str] = None) -> Tuple[FileType, str]:
        """Determine file type and mime type"""        
        mime_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        
        file_extension = Path(filename).suffix.lower()
        
        # Image files
        if mime_type.startswith('image/') or file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            return FileType.IMAGE, mime_type
        
        # PDF files
        if mime_type == 'application/pdf' or file_extension == '.pdf':
            return FileType.PDF, mime_type
        
        # Default to PDF for other documents
        return FileType.PDF, mime_type
    
    def _process_image(self, image_content: bytes, filename: str) -> Tuple[bytes, int]:
        """Process image - resize if too large and reduce quality by 25%"""
        try:
            from io import BytesIO
            
            # Open image
            image = Image.open(BytesIO(image_content))
            
            # Convert RGBA to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Get original size
            original_size = len(image_content)
            
            # If image is larger than 1MB, reduce quality by 25% as per overview.txt
            if original_size > 1024 * 1024:  # 1MB
                quality = 75  # 25% reduction from 100%
                
                # Also resize if image is very large
                if max(image.size) > 1920:
                    ratio = 1920 / max(image.size)
                    new_size = tuple(int(dim * ratio) for dim in image.size)
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save with reduced quality
                output = BytesIO()
                image.save(output, format='JPEG', quality=quality, optimize=True)
                processed_content = output.getvalue()
                processed_size = len(processed_content)
                
                logger.info(f"Image processed: {filename} ({original_size} -> {processed_size} bytes)")
                return processed_content, processed_size
            
            return image_content, original_size
            
        except Exception as e:
            logger.error(f"Error processing image {filename}: {e}")
            # Return original if processing fails
            return image_content, len(image_content)
    
    def _extract_youtube_embed_id(self, youtube_url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        import re
        
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        
        return None
    
    async def _save_youtube_file(self, article_id: UUID, uploaded_by: UUID, youtube_url: str) -> Optional[ArticleFileResponse]:
        """Save YouTube file record"""
        embed_id = self._extract_youtube_embed_id(youtube_url)
        
        return await self._save_file_record(
            article_id=article_id,
            file_type=FileType.YOUTUBE,
            original_name=f"YouTube Video ({embed_id})" if embed_id else "YouTube Video",
            youtube_url=youtube_url,
            youtube_embed_id=embed_id,
            uploaded_by=uploaded_by
        )
    
    async def _save_file_record(
        self,
        article_id: UUID,
        file_type: FileType,
        original_name: str,
        uploaded_by: UUID,
        file_path: Optional[str] = None,
        file_url: Optional[str] = None,
        youtube_url: Optional[str] = None,
        youtube_embed_id: Optional[str] = None,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None
    ) -> Optional[ArticleFileResponse]:
        """Save file record to database"""
        
        query = """
        INSERT INTO article_files (
            article_id, file_type, original_name, file_path, file_url,
            youtube_url, youtube_embed_id, file_size, mime_type, uploaded_by
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id, article_id, file_type, original_name, file_path, file_url,
                  youtube_url, youtube_embed_id, file_size, mime_type,
                  download_count, uploaded_by, created_at
        """
        
        row = await self.db.fetch_one(
            query,
            article_id, file_type.value, original_name, file_path, file_url,
            youtube_url, youtube_embed_id, file_size, mime_type, uploaded_by
        )
        
        return ArticleFileResponse(**dict(row)) if row else None
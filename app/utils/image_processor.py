import io
import os
import uuid
from PIL import Image
import aiofiles
from typing import Optional, Tuple
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class ImageProcessor:
    def __init__(self, max_size: int = 2048, quality: int = 50):
        self.max_size = max_size
        self.quality = quality
        self.allowed_formats = {'JPEG', 'JPG', 'PNG', 'WEBP'}
        self.upload_dir = "uploads/profiles"
        self.article_images_dir = "uploads/articles"
        self.cover_images_dir = "uploads/covers"
        self.use_minio = settings.FILE_STORAGE_TYPE == "minio"
        
    def _get_minio_service(self):
        """Lazy import to avoid circular imports"""
        from app.services.minio_service import minio_service
        return minio_service
    
    async def process_profile_image(self, image_data: bytes, filename: str) -> Tuple[str, str]:
        """
        Process profile image: resize, compress, and save
        Returns: (file_path_or_object_name, public_url)
        """
        try:
            # Load and process image
            processed_data = self._process_image_data(image_data, filename, crop_square=True)
            
            if self.use_minio:
                # Upload to MinIO
                minio_service = self._get_minio_service()
                object_name = minio_service.generate_object_name(filename, "profiles")
                
                success, public_url = await minio_service.upload_file(
                    processed_data, object_name, "image/jpeg"
                )
                
                if not success:
                    raise ValueError("Failed to upload to MinIO")
                
                logger.info(f"Profile image processed and uploaded to MinIO: {object_name}")
                return object_name, public_url
            else:
                # Save locally (existing logic)
                return await self._save_image_locally(processed_data, filename, "profiles")
                
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise ValueError(f"Failed to process image: {str(e)}")
    
    def _process_image_data(self, image_data: bytes, filename: str, crop_square: bool = False) -> bytes:
        """Process image data and return processed bytes"""
        # Load image
        image = Image.open(io.BytesIO(image_data))
        
        # Validate format
        if image.format not in self.allowed_formats:
            raise ValueError(f"Unsupported image format: {image.format}")
        
        # Convert to RGB if necessary (for JPEG)
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Resize if too large
        if image.width > self.max_size or image.height > self.max_size:
            image.thumbnail((self.max_size, self.max_size), Image.Resampling.LANCZOS)
            logger.info(f"Image resized to: {image.width}x{image.height}")
        
        # Create square crop if requested
        if crop_square:
            image = self._create_square_crop(image)
        
        # Compress and return bytes
        output_buffer = io.BytesIO()
        image.save(
            output_buffer,
            format='JPEG',
            quality=self.quality,
            optimize=True
        )
        
        return output_buffer.getvalue()
    
    async def _save_image_locally(self, image_data: bytes, filename: str, folder: str) -> Tuple[str, str]:
        """Save image locally and return file path and URL"""
        # Create upload directory if not exists
        upload_dir = getattr(self, f"{folder.rstrip('s')}_images_dir", f"uploads/{folder}")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = 'jpg'  # Always save as JPEG for consistency
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save to file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(image_data)
        
        # Generate public URL
        public_url = f"/uploads/{folder}/{unique_filename}"
        
        logger.info(f"Image saved locally: {file_path} (quality: {self.quality}%)")
        return file_path, public_url
    
    def _create_square_crop(self, image: Image.Image) -> Image.Image:
        """Create square crop from center of image"""
        width, height = image.size
        
        # Already square
        if width == height:
            return image
        
        # Crop to square from center
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size
        
        return image.crop((left, top, right, bottom))
    
    async def delete_profile_image(self, file_path: str) -> bool:
        """Delete profile image file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Profile image deleted: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
            return False
    
    def validate_image_file(self, content_type: str, file_size: int) -> None:
        """Validate image file before processing"""
        # Check content type
        allowed_types = {
            'image/jpeg', 'image/jpg', 'image/png', 
            'image/webp', 'image/gif'
        }
        
        if content_type.lower() not in allowed_types:
            raise ValueError(f"Invalid file type: {content_type}")
        
        # Check file size (5MB limit)
        max_size = 5 * 1024 * 1024  # 5MB
        if file_size > max_size:
            raise ValueError(f"File too large: {file_size} bytes (max: {max_size})")
        
        logger.info(f"Image validation passed: {content_type}, {file_size} bytes")

    async def process_article_image(self, image_data: bytes, filename: str) -> Tuple[str, str]:
        """
        Process article image: optimize and save without cropping
        Returns: (file_path_or_object_name, public_url)
        """
        try:
            # Process image data without cropping
            processed_data = self._process_image_data(image_data, filename, crop_square=False)
            
            if self.use_minio:
                # Upload to MinIO
                minio_service = self._get_minio_service()
                object_name = minio_service.generate_object_name(filename, "articles")
                
                success, public_url = await minio_service.upload_file(
                    processed_data, object_name, "image/jpeg"
                )
                
                if not success:
                    raise ValueError("Failed to upload to MinIO")
                
                logger.info(f"Article image processed and uploaded to MinIO: {object_name}")
                return object_name, public_url
            else:
                # Save locally
                return await self._save_image_locally(processed_data, filename, "articles")
                
        except Exception as e:
            logger.error(f"Article image processing failed: {e}")
            raise ValueError(f"Failed to process article image: {str(e)}")
    
    async def process_cover_image(self, image_data: bytes, filename: str) -> Tuple[str, str]:
        """
        Process cover image: optimize for display (16:9 aspect ratio recommended)
        Returns: (file_path_or_object_name, public_url)
        """
        try:
            # Process image data without cropping
            processed_data = self._process_image_data(image_data, filename, crop_square=False)
            
            if self.use_minio:
                # Upload to MinIO
                minio_service = self._get_minio_service()
                object_name = minio_service.generate_object_name(filename, "covers")
                
                success, public_url = await minio_service.upload_file(
                    processed_data, object_name, "image/jpeg"
                )
                
                if not success:
                    raise ValueError("Failed to upload to MinIO")
                
                logger.info(f"Cover image processed and uploaded to MinIO: {object_name}")
                return object_name, public_url
            else:
                # Save locally
                return await self._save_image_locally(processed_data, filename, "covers")
                
        except Exception as e:
            logger.error(f"Cover image processing failed: {e}")
            raise ValueError(f"Failed to process cover image: {str(e)}")

# Global image processor instance
image_processor = ImageProcessor(quality=50)  # 50% quality as requested
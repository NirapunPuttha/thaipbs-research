import asyncio
import logging
from typing import Optional, Tuple, BinaryIO, Union
from minio import Minio
from minio.error import S3Error
from datetime import timedelta
import tempfile
import uuid
from pathlib import Path
import mimetypes

from app.core.config import settings

logger = logging.getLogger(__name__)

class MinIOService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        
    async def ensure_bucket_exists(self) -> bool:
        """Ensure bucket exists, create if not"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created MinIO bucket: {self.bucket_name}")
            return True
        except Exception as bucket_error:
            # Handle bucket already exists errors
            if "BucketAlreadyOwnedByYou" in str(bucket_error) or "BucketAlreadyExists" in str(bucket_error):
                logger.info(f"Bucket {self.bucket_name} already exists")
                return True
        except S3Error as e:
            logger.error(f"MinIO bucket error: {e}")
            return False
    
    async def upload_file(
        self, 
        file_data: bytes, 
        object_name: str, 
        content_type: str = None
    ) -> Tuple[bool, Optional[str]]:
        """Upload file to MinIO"""
        try:
            await self.ensure_bucket_exists()
            
            # Auto-detect content type if not provided
            if not content_type:
                content_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(file_data)
                temp_file.flush()
                
                # Upload to MinIO
                self.client.fput_object(
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    file_path=temp_file.name,
                    content_type=content_type
                )
            
            # Generate public URL
            public_url = f"{settings.minio_base_url}/{object_name}"
            logger.info(f"File uploaded to MinIO: {object_name}")
            return True, public_url
            
        except S3Error as e:
            logger.error(f"MinIO upload error: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error during MinIO upload: {e}")
            return False, None
    
    async def delete_file(self, object_name: str) -> bool:
        """Delete file from MinIO"""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"File deleted from MinIO: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"MinIO delete error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during MinIO delete: {e}")
            return False
    
    async def file_exists(self, object_name: str) -> bool:
        """Check if file exists in MinIO"""
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False
    
    async def get_file_info(self, object_name: str) -> Optional[dict]:
        """Get file metadata from MinIO"""
        try:
            stat = self.client.stat_object(self.bucket_name, object_name)
            return {
                "object_name": object_name,
                "size": stat.size,
                "etag": stat.etag,
                "last_modified": stat.last_modified,
                "content_type": stat.content_type
            }
        except S3Error as e:
            logger.error(f"MinIO stat error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting file info: {e}")
            return None
    
    async def generate_presigned_url(
        self, 
        object_name: str, 
        expires: timedelta = timedelta(days=7)
    ) -> Optional[str]:
        """Generate presigned URL for file access"""
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires
            )
            logger.debug(f"Generated presigned URL for {object_name}")
            return url
        except S3Error as e:
            logger.error(f"MinIO presigned URL error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            return None
    
    async def generate_upload_presigned_url(
        self, 
        object_name: str, 
        expires: timedelta = timedelta(hours=1)
    ) -> Optional[str]:
        """Generate presigned URL for file upload"""
        try:
            url = self.client.presigned_put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=expires
            )
            logger.debug(f"Generated presigned upload URL for {object_name}")
            return url
        except S3Error as e:
            logger.error(f"MinIO presigned upload URL error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned upload URL: {e}")
            return None
    
    def generate_object_name(self, filename: str, folder: str = "") -> str:
        """Generate unique object name for MinIO"""
        file_extension = Path(filename).suffix.lower()
        unique_id = str(uuid.uuid4())
        
        if folder:
            return f"{folder}/{unique_id}{file_extension}"
        else:
            return f"{unique_id}{file_extension}"
    
    async def copy_file(self, source_object: str, dest_object: str) -> bool:
        """Copy file within MinIO bucket"""
        try:
            from minio.commonconfig import CopySource
            
            copy_source = CopySource(self.bucket_name, source_object)
            self.client.copy_object(self.bucket_name, dest_object, copy_source)
            logger.info(f"File copied in MinIO: {source_object} -> {dest_object}")
            return True
        except S3Error as e:
            logger.error(f"MinIO copy error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error copying file: {e}")
            return False
    
    async def list_files(self, prefix: str = "", limit: int = 1000) -> list:
        """List files in bucket with optional prefix filter"""
        try:
            objects = self.client.list_objects(
                self.bucket_name, 
                prefix=prefix,
                recursive=True
            )
            
            files = []
            count = 0
            for obj in objects:
                if count >= limit:
                    break
                    
                files.append({
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag
                })
                count += 1
            
            logger.info(f"Listed {len(files)} files with prefix '{prefix}'")
            return files
            
        except S3Error as e:
            logger.error(f"MinIO list error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing files: {e}")
            return []

# Global MinIO service instance
minio_service = MinIOService()
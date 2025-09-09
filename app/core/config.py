from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: Optional[str] = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 30))
    
    # File Upload
    FILE_UPLOAD_MAX_SIZE: int = int(os.getenv("FILE_UPLOAD_MAX_SIZE", 52428800))  # 50MB
    IMAGE_COMPRESSION_QUALITY: float = float(os.getenv("IMAGE_COMPRESSION_QUALITY", 0.8))
    UPLOAD_PATH: str = os.getenv("UPLOAD_PATH", "./uploads")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    
    # Download Quota
    DOWNLOAD_QUOTA_BASIC: int = int(os.getenv("DOWNLOAD_QUOTA_BASIC", 3))  # Basic users can download 3 files max
    DOWNLOAD_QUOTA_DETAILED: int = int(os.getenv("DOWNLOAD_QUOTA_DETAILED", 999))  # Detailed users unlimited (or high number)
    
    # Security
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # Database Pool
    DB_POOL_MIN_SIZE: int = int(os.getenv("DB_POOL_MIN_SIZE", 5))
    DB_POOL_MAX_SIZE: int = int(os.getenv("DB_POOL_MAX_SIZE", 20))
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_QUERY_LOGGING: bool = os.getenv("ENABLE_QUERY_LOGGING", "false").lower() == "true"
    
    # Admin
    INITIAL_ADMIN_EMAIL: Optional[str] = os.getenv("INITIAL_ADMIN_EMAIL")
    
    # MinIO Configuration
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "password123")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "research-file")
    
    # File Storage Configuration
    FILE_STORAGE_TYPE: str = os.getenv("FILE_STORAGE_TYPE", "local")  # "local" or "minio"
    
    @property
    def minio_base_url(self) -> str:
        protocol = "https" if self.MINIO_SECURE else "http"
        return f"{protocol}://{self.MINIO_ENDPOINT}/{self.MINIO_BUCKET_NAME}"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
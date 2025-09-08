from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# User creation schema
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    level: Optional[int] = 1  # Default to level 1 (basic user)
    is_admin: Optional[bool] = False
    is_creator: Optional[bool] = False
    is_active: Optional[bool] = True
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

    @validator('level')
    def validate_level(cls, v):
        if v is not None and not 1 <= v <= 3:
            raise ValueError('Level must be between 1 and 3')
        return v
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, underscore and hyphen')
        return v

# User login schema
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# User response schema (without password)
class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    level: int
    is_admin: bool
    is_creator: bool
    is_active: bool
    download_count: int
    detailed_info_submitted: bool
    profile_image_url: Optional[str] = None
    profile_image_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# User profile update schema
class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    
    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            if len(v) < 3:
                raise ValueError('Username must be at least 3 characters long')
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError('Username can only contain letters, numbers, underscore and hyphen')
        return v

# Detailed info schema (after 5+ downloads)
class UserDetailedInfo(BaseModel):
    address: str
    phone: str
    organization: str
    research_purpose: str

# Admin user management schema
class UserUpdate(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    level: Optional[int] = None
    is_admin: Optional[bool] = None
    is_creator: Optional[bool] = None
    is_active: Optional[bool] = None

    @validator('email')
    def validate_email(cls, v):
        if v is not None:
            # Basic email validation
            if '@' not in v or '.' not in v.split('@')[-1]:
                raise ValueError('Invalid email format')
        return v

    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            if len(v) < 3:
                raise ValueError('Username must be at least 3 characters long')
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError('Username can only contain letters, numbers, underscore and hyphen')
        return v

    @validator('password')
    def validate_password(cls, v):
        if v is not None:
            if len(v) < 8:
                raise ValueError('Password must be at least 8 characters long')
        return v

    @validator('level')
    def validate_level(cls, v):
        if v is not None and not 1 <= v <= 3:
            raise ValueError('Level must be between 1 and 3')
        return v

class UserAdminUpdate(BaseModel):
    level: Optional[int] = None
    is_admin: Optional[bool] = None
    is_creator: Optional[bool] = None
    is_active: Optional[bool] = None
    
    @validator('level')
    def validate_level(cls, v):
        if v is not None and v not in [1, 2, 3]:
            raise ValueError('Level must be 1, 2, or 3')
        return v

# User list for admin
class UserListResponse(BaseModel):
    id: UUID
    email: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    level: int
    is_admin: bool
    is_creator: bool
    is_active: bool
    download_count: int
    detailed_info_submitted: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# JWT token schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None

class RefreshToken(BaseModel):
    refresh_token: str

# Download history models
class DownloadHistoryItem(BaseModel):
    id: UUID
    file_id: UUID
    article_id: Optional[UUID]
    file_name: str
    file_type: str
    file_size: Optional[int]
    article_title: Optional[str]
    downloaded_at: datetime
    ip_address: Optional[str]

class DownloadHistoryResponse(BaseModel):
    downloads: List[DownloadHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int

# User statistics models
class UserStats(BaseModel):
    user_id: UUID
    total_downloads: int
    unique_articles_downloaded: int
    favorite_articles_count: int
    total_article_views: int
    recent_activity_count: int
    most_downloaded_file_type: Optional[str]
    registration_date: datetime
    last_activity_date: Optional[datetime]
    account_level: int

# Complete user profile response (including stats)
class UserProfileComplete(UserResponse):
    # Detailed info fields (if submitted)
    address: Optional[str] = None
    phone: Optional[str] = None 
    organization: Optional[str] = None
    research_purpose: Optional[str] = None
    
    # Statistics
    stats: Optional[UserStats] = None
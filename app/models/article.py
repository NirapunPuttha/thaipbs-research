from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published" 
    SUSPENDED = "suspended"

class AccessLevel(int, Enum):
    PUBLIC = 1
    REGISTERED = 2
    DETAILED = 3

class FileType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    YOUTUBE = "youtube"

# Article Type models
class ArticleTypeBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool = True

class ArticleTypeResponse(ArticleTypeBase):
    id: int
    created_at: datetime

# Topic models
class TopicBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = True

class TopicResponse(TopicBase):
    id: int
    created_at: datetime

# Tag models
class TagBase(BaseModel):
    name: str
    slug: str

class TagResponse(TagBase):
    id: int
    usage_count: int = 0
    created_at: datetime

# Article File models
class ArticleFileBase(BaseModel):
    file_type: FileType
    original_name: Optional[str] = None
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    youtube_url: Optional[str] = None
    youtube_embed_id: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None

class ArticleFileCreate(ArticleFileBase):
    pass

class ArticleFileResponse(ArticleFileBase):
    id: UUID
    article_id: UUID
    download_count: int = 0
    uploaded_by: Optional[UUID] = None
    created_at: datetime

# Article models
class ArticleBase(BaseModel):
    title: str = Field(..., max_length=500)
    content: str
    excerpt: Optional[str] = None
    cover_image_url: Optional[str] = None
    access_level: AccessLevel = AccessLevel.PUBLIC
    is_featured: bool = False

# Minimal article creation - just type and basic info
class ArticleCreateMinimal(BaseModel):
    article_type_id: int  # Required - must specify article type
    title: Optional[str] = Field("Untitled Draft", max_length=500)
    content: Optional[str] = "Draft content - to be edited"
    
    @validator('title')
    def validate_title(cls, v):
        if not v or len(v.strip()) == 0:
            return "Untitled Draft"
        return v.strip()

# Full article creation for advanced use
class ArticleCreate(ArticleBase):
    article_type_id: Optional[int] = None
    topic_ids: Optional[List[int]] = []
    tag_names: Optional[List[str]] = []
    files: Optional[List[ArticleFileCreate]] = []

    @validator('title')
    def validate_title(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Title cannot be empty')
        return v.strip()

    @validator('content')
    def validate_content(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Content cannot be empty')
        return v.strip()

class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    excerpt: Optional[str] = None
    cover_image_url: Optional[str] = None
    article_type_id: Optional[int] = None
    access_level: Optional[AccessLevel] = None
    status: Optional[ArticleStatus] = None
    is_featured: Optional[bool] = None
    topic_ids: Optional[List[int]] = None
    tag_names: Optional[List[str]] = None

    @validator('title')
    def validate_title(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Title cannot be empty')
        return v.strip() if v else v

    @validator('content')
    def validate_content(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('Content cannot be empty')
        return v.strip() if v else v

class ArticleResponse(ArticleBase):
    id: UUID
    slug: str
    status: ArticleStatus
    view_count_unique: int = 0
    view_count_total: int = 0
    share_count: int = 0
    favorite_count: int = 0
    download_count: int = 0
    created_by: UUID
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class ArticleDetail(ArticleResponse):
    article_type: Optional[ArticleTypeResponse] = None
    topics: List[TopicResponse] = []
    tags: List[TagResponse] = []
    files: List[ArticleFileResponse] = []
    authors: List[dict] = []  # Will be populated with user info

class ArticleListItem(BaseModel):
    id: UUID
    title: str
    slug: str
    excerpt: Optional[str] = None
    cover_image_url: Optional[str] = None
    article_type: Optional[ArticleTypeResponse] = None
    access_level: AccessLevel
    status: ArticleStatus
    is_featured: bool = False
    view_count_unique: int = 0
    favorite_count: int = 0
    created_by: UUID
    published_at: Optional[datetime] = None
    created_at: datetime
    is_favorite: bool = False  # Whether current user has favorited this article
    topics: List[TopicResponse] = []
    tags: List[TagResponse] = []
    authors: List[dict] = []  # Ordered list of authors with role and order

# Search and Filter models
class ArticleSearchRequest(BaseModel):
    query: Optional[str] = None
    author_query: Optional[str] = None  # Search by author name
    author_ids: Optional[List[UUID]] = None  # Filter by specific author IDs
    article_type_ids: Optional[List[int]] = []
    topic_ids: Optional[List[int]] = []
    tag_names: Optional[List[str]] = []
    access_level: Optional[AccessLevel] = None
    status: Optional[ArticleStatus] = ArticleStatus.PUBLISHED
    is_featured: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    published_after: Optional[datetime] = None
    published_before: Optional[datetime] = None
    sort_by: Optional[str] = "created_at"  # created_at, published_at, view_count_unique, view_count_total, title
    sort_order: Optional[str] = "desc"  # asc, desc
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

class ArticleSearchResponse(BaseModel):
    items: List[ArticleListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    user_role: Optional[str] = None  # "admin" or "user" for frontend logic


# Admin specific models
class ArticleAdminUpdate(ArticleUpdate):
    created_by: Optional[UUID] = None
    author_ids: Optional[List[UUID]] = []  # Additional authors

class ArticleStats(BaseModel):
    total_articles: int = 0
    published_articles: int = 0
    draft_articles: int = 0
    suspended_articles: int = 0
    featured_articles: int = 0
    total_views: int = 0
    total_downloads: int = 0
    articles_by_type: dict = {}
    articles_by_access_level: dict = {}
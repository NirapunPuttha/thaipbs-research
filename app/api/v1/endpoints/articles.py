from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from app.core.database import get_database
from app.core.security import get_current_user, get_current_admin_user, get_current_creator_user, get_optional_current_user
from app.models.user import UserResponse
from app.models.article import (
    ArticleCreate, ArticleCreateMinimal, ArticleUpdate, ArticleResponse, ArticleDetail,
    ArticleListItem, ArticleSearchRequest, ArticleSearchResponse,
    ArticleAdminUpdate, ArticleStats, ArticleStatus, AccessLevel,
    ArticleTypeResponse, TopicResponse, TagResponse
)
from pydantic import BaseModel
from app.services.article_service import ArticleService
from app.services.analytics_service import AnalyticsService
from app.services.activity_service import ActivityService, ActivityLogger
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Home endpoint - Homepage API (must come before article_identifier route)
@router.get("/home", response_model=dict)
async def get_home_articles(
    featured_limit: int = Query(10, ge=1, le=20, description="Number of featured articles (default 10)"),
    latest_limit: int = Query(10, ge=1, le=50, description="Number of latest articles (default 10)"),
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Get home page data: featured articles (10) and latest articles (10)"""
    try:
        service = ArticleService(db)
        current_user_id = current_user.id if current_user else None
        
        # Get featured articles (10 first) - บทความที่ถูกตั้งค่าว่าแนะนำ 10 อันดับแรก
        featured_request = ArticleSearchRequest(
            status=ArticleStatus.PUBLISHED,
            access_level=AccessLevel.PUBLIC,
            is_featured=True,
            sort_by="published_at",  # เรียงตามวันที่เผยแพร่
            sort_order="desc",
            page=1,
            page_size=featured_limit
        )
        featured_response = await service.get_article_list(featured_request, current_user_id)
        
        # Get latest articles (10 first) - บทความใหม่ 10 อันดับแรก
        latest_request = ArticleSearchRequest(
            status=ArticleStatus.PUBLISHED,
            access_level=AccessLevel.PUBLIC,
            sort_by="published_at",  # เรียงตามวันที่เผยแพร่
            sort_order="desc",
            page=1,
            page_size=latest_limit
        )
        latest_response = await service.get_article_list(latest_request, current_user_id)
        
        return {
            "featured_articles": featured_response.items,
            "featured_count": len(featured_response.items),
            "latest_articles": latest_response.items,
            "latest_count": len(latest_response.items)
        }
        
    except Exception as e:
        logger.error(f"Error getting home articles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Public endpoints (no authentication required)
@router.get("/{article_identifier}", response_model=ArticleDetail)
async def get_article(
    article_identifier: str,
    request: Request,
    track_view: bool = Query(True, description="Whether to track this view"),
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Get article by UUID or slug (public access with access level checking) - automatically tracks views"""
    try:
        # Determine if identifier is UUID or slug
        try:
            # Try to parse as UUID first
            article_uuid = UUID(article_identifier)
            is_uuid = True
            logger.info(f"Starting get_article by UUID: {article_uuid}")
        except ValueError:
            # Not a valid UUID, treat as slug
            is_uuid = False
            logger.info(f"Starting get_article by slug: {article_identifier}")
        
        service = ArticleService(db)
        
        # Fetch article based on identifier type
        if is_uuid:
            article = await service.get_article_detail(article_uuid)
        else:
            article = await service.get_article_by_slug(article_identifier)
        
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # For public access, only show published articles
        if article.status != ArticleStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # Check access level (public can only see level 1)
        if article.access_level != AccessLevel.PUBLIC:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - login required"
            )
        
        # Track view automatically if requested
        identifier_type = "UUID" if is_uuid else "slug"
        logger.info(f"Track view parameter: {track_view} for article {identifier_type}: {article_identifier}")
        if track_view:
            try:
                analytics_service = AnalyticsService(db)
                client_ip = request.client.host if request.client else "unknown"
                user_agent = request.headers.get("user-agent")
                referrer = request.headers.get("referer")
                
                await analytics_service.track_article_view(
                    article_id=article.id,
                    ip_address=client_ip,
                    user_id=current_user.id if current_user else None,
                    user_agent=user_agent,
                    referrer=referrer,
                    session_id=f"anon_{hash(f'{client_ip}_{user_agent}')}" if not current_user else None
                )
                logger.info(f"View tracked for article {identifier_type} {article_identifier} (ID: {article.id}) from IP {client_ip}")
                
                # Log activity
                try:
                    activity_service = ActivityService(db)
                    await ActivityLogger.log_article_view(
                        activity_service=activity_service,
                        article_id=article.id,
                        user_id=current_user.id if current_user else None,
                        ip_address=client_ip,
                        user_agent=user_agent
                    )
                except Exception as activity_error:
                    logger.warning(f"Failed to log view activity: {activity_error}")
                    
            except Exception as e:
                # Don't fail the whole request if view tracking fails
                logger.error(f"Failed to track view for article {identifier_type} {article_identifier}: {e}")
                import traceback
                logger.error(f"View tracking error details: {traceback.format_exc()}")
        
        return article
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting article by {article_identifier}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/search", response_model=ArticleSearchResponse)
async def search_articles(
    search_request: ArticleSearchRequest,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Search articles (public access)"""
    try:
        service = ArticleService(db)
        
        # Force public access restrictions
        search_request.status = ArticleStatus.PUBLISHED
        search_request.access_level = AccessLevel.PUBLIC
        
        current_user_id = current_user.id if current_user else None
        return await service.get_article_list(search_request, current_user_id)
        
    except Exception as e:
        logger.error(f"Error searching articles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("", response_model=ArticleSearchResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    query: str = Query(None),
    author_query: str = Query(None),  # Search by author name
    article_type_ids: List[int] = Query([]),
    topic_ids: List[int] = Query([]),
    tag_names: List[str] = Query([]),
    is_featured: bool = Query(None),
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """List articles with filters (public access)"""
    try:
        search_request = ArticleSearchRequest(
            query=query,
            author_query=author_query,
            article_type_ids=article_type_ids,
            topic_ids=topic_ids,
            tag_names=tag_names,
            is_featured=is_featured,
            status=ArticleStatus.PUBLISHED,
            access_level=AccessLevel.PUBLIC,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )
        
        service = ArticleService(db)
        current_user_id = current_user.id if current_user else None
        return await service.get_article_list(search_request, current_user_id)
        
    except Exception as e:
        logger.error(f"Error listing articles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Authenticated user endpoints
@router.get("/auth/{article_id}", response_model=ArticleDetail)
async def get_article_authenticated(
    article_id: UUID,
    request: Request,
    track_view: bool = Query(True, description="Whether to track this view"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get article by ID (authenticated access with level checking) - automatically tracks views"""
    try:
        service = ArticleService(db)
        article = await service.get_article_detail(article_id)
        
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # For authenticated access, show published articles
        if article.status != ArticleStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # Check access level - user level must be >= article level
        if article.access_level.value > current_user.level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied - insufficient user level"
            )
        
        # Track view automatically if requested
        logger.info(f"Track view parameter: {track_view} for article {article_id}")
        if track_view:
            try:
                analytics_service = AnalyticsService(db)
                client_ip = request.client.host if request.client else "unknown"
                user_agent = request.headers.get("user-agent")
                referrer = request.headers.get("referer")
                
                await analytics_service.track_article_view(
                    article_id=article_id,
                    ip_address=client_ip,
                    user_id=current_user.id,
                    user_agent=user_agent,
                    referrer=referrer
                )
                logger.info(f"Authenticated view tracked for article {article_id} by user {current_user.username}")
            except Exception as e:
                # Don't fail the whole request if view tracking fails
                logger.warning(f"Failed to track authenticated view for article {article_id}: {e}")
        
        return article
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/auth/search", response_model=ArticleSearchResponse)
async def search_articles_authenticated(
    search_request: ArticleSearchRequest,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Search articles (authenticated access)"""
    try:
        service = ArticleService(db)
        
        # Set max access level based on user level
        search_request.status = ArticleStatus.PUBLISHED
        search_request.access_level = AccessLevel(current_user.level)
        
        return await service.get_article_list(search_request, current_user.id)
        
    except Exception as e:
        logger.error(f"Error searching articles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Admin endpoints  
@router.post("/quick", response_model=ArticleDetail)
async def create_article_minimal(
    article_data: ArticleCreateMinimal,
    request: Request,
    current_user: UserResponse = Depends(get_current_creator_user),
    db = Depends(get_database)
):
    """Create new article quickly - just type and draft (admin or creator only)"""
    try:
        service = ArticleService(db)
        article = await service.create_article_minimal(article_data, current_user.id)
        
        if not article:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create article"
            )
        
        # Log activity
        try:
            activity_service = ActivityService(db)
            client_ip = request.headers.get("x-forwarded-for") or "unknown"
            user_agent = request.headers.get("user-agent")
            
            new_values = {
                "title": article.title,
                "status": article.status.value,
                "access_level": article.access_level.value,
                "article_type_id": article.article_type_id
            }
            
            await ActivityLogger.log_article_create(
                activity_service=activity_service,
                article_id=article.id,
                user_id=current_user.id,
                new_values=new_values,
                ip_address=client_ip,
                user_agent=user_agent
            )
        except Exception as activity_error:
            logger.warning(f"Failed to log create activity: {activity_error}")
        
        return article
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating minimal article: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("", response_model=ArticleDetail)
async def create_article(
    article_data: ArticleCreate,
    request: Request,
    current_user: UserResponse = Depends(get_current_creator_user),
    db = Depends(get_database)
):
    """Create new article with full data (admin or creator only)"""
    try:
        service = ArticleService(db)
        article = await service.create_article(article_data, current_user.id)
        
        if not article:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create article"
            )
        
        # Log activity
        try:
            activity_service = ActivityService(db)
            client_ip = request.headers.get("x-forwarded-for") or "unknown"
            user_agent = request.headers.get("user-agent")
            
            new_values = {
                "title": article.title,
                "status": article.status.value,
                "access_level": article.access_level.value,
                "is_featured": article.is_featured
            }
            
            await ActivityLogger.log_article_create(
                activity_service=activity_service,
                article_id=article.id,
                user_id=current_user.id,
                new_values=new_values,
                ip_address=client_ip,
                user_agent=user_agent
            )
        except Exception as activity_error:
            logger.warning(f"Failed to log create activity: {activity_error}")
        
        return article
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating article: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/{article_id}", response_model=ArticleDetail)
async def update_article(
    article_id: UUID,
    update_data: ArticleUpdate,
    current_user: UserResponse = Depends(get_current_creator_user),
    db = Depends(get_database)
):
    """Update article (admin or creator/author only)"""
    try:
        service = ArticleService(db)
        
        # Check if article exists
        existing = await service.get_article_detail(article_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        # Check permission: admin can edit anything, creator can edit only their own articles
        if not current_user.is_admin:
            # Check if user is the author or co-author
            is_author = existing.created_by == current_user.id
            is_co_author = any(author.get('id') == current_user.id for author in existing.authors)
            
            if not (is_author or is_co_author):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only edit articles you created or co-authored"
                )
        
        article = await service.update_article(article_id, update_data)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update article"
            )
        
        return article
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.delete("/{article_id}")
async def delete_article(
    article_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Delete article (admin only) - soft delete"""
    try:
        service = ArticleService(db)
        
        success = await service.delete_article(article_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        return {"message": "Article deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/{article_id}/publish", response_model=ArticleDetail)
async def publish_article(
    article_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Publish article (admin only)"""
    try:
        service = ArticleService(db)
        
        article = await service.publish_article(article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Article not found or already published"
            )
        
        return article
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/admin/{article_id}", response_model=ArticleDetail)
async def get_article_admin(
    article_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get article by ID (admin access - can see any status)"""
    try:
        service = ArticleService(db)
        article = await service.get_article_detail(article_id)
        
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        return article
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/manage", response_model=ArticleSearchResponse)
async def get_managed_articles(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    
    # Search filters
    query: Optional[str] = Query(None, description="Search text in title, content, excerpt"),
    author_query: Optional[str] = Query(None, description="Search by author name"),
    
    # Category filters
    article_type_ids: List[int] = Query([], description="Filter by article types"),
    topic_ids: List[int] = Query([], description="Filter by topics"),
    tag_names: List[str] = Query([], description="Filter by tag names"),
    
    # Status and access filters
    status: Optional[str] = Query(None, description="Article status (draft, published, suspended)"),
    access_level: Optional[int] = Query(None, ge=1, le=3, description="Access level (1-3)"),
    is_featured: Optional[bool] = Query(None, description="Filter featured articles"),
    
    # Date range filters
    created_after: Optional[datetime] = Query(None, description="Created after date"),
    created_before: Optional[datetime] = Query(None, description="Created before date"),
    published_after: Optional[datetime] = Query(None, description="Published after date"),
    published_before: Optional[datetime] = Query(None, description="Published before date"),
    
    # Authentication required
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Smart article management API:
    - Admin: See all articles in the system (any status, any access level)
    - User: See only articles they created/authored (any status of their own)
    """
    try:
        service = ArticleService(db)
        
        # Convert status string to enum
        status_enum = None
        if status:
            try:
                status_enum = ArticleStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status}. Valid options: draft, published, suspended"
                )
        
        # Convert access_level to enum
        access_level_enum = None
        if access_level:
            try:
                access_level_enum = AccessLevel(access_level)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid access_level: {access_level}. Valid options: 1, 2, 3"
                )
        
        # Build search request based on user role
        if current_user.is_admin:
            # 👨‍💼 Admin Mode: See everything
            search_request = ArticleSearchRequest(
                query=query,
                author_query=author_query,
                article_type_ids=article_type_ids,
                topic_ids=topic_ids,
                tag_names=tag_names,
                status=status_enum,
                access_level=access_level_enum,
                is_featured=is_featured,
                created_after=created_after,
                created_before=created_before,
                published_after=published_after,
                published_before=published_before,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                page_size=page_size
                # No restrictions for admin
            )
            user_role = "admin"
            
        else:
            # 👤 User Mode: See only own articles
            # Restrict some filters for non-admin users
            filtered_status = status_enum
            if status_enum == ArticleStatus.SUSPENDED:
                # Users shouldn't see suspended articles (admin action)
                filtered_status = None
            
            search_request = ArticleSearchRequest(
                query=query,
                author_query=author_query,
                author_ids=[current_user.id],  # 🔑 Only show user's own articles
                article_type_ids=article_type_ids,
                topic_ids=topic_ids,
                tag_names=tag_names,
                status=filtered_status,
                access_level=access_level_enum,
                is_featured=None,  # Users can't filter by featured (admin privilege)
                created_after=created_after,
                created_before=created_before,
                published_after=published_after,
                published_before=published_before,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                page_size=page_size
            )
            user_role = "user"
        
        # Get articles
        result = await service.get_article_list(search_request, current_user.id)
        
        # Add user role info for frontend
        result.user_role = user_role
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting managed articles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/admin/search", response_model=ArticleSearchResponse)
async def search_articles_admin(
    search_request: ArticleSearchRequest,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Search articles (admin access - can see all statuses and levels)"""
    try:
        service = ArticleService(db)
        return await service.get_article_list(search_request, current_user.id)
        
    except Exception as e:
        logger.error(f"Error searching articles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Helper endpoints
@router.get("/types/all", response_model=List[ArticleTypeResponse])
async def get_article_types(db = Depends(get_database)):
    """Get all article types"""
    try:
        query = """
        SELECT id, name, slug, description, is_active, created_at
        FROM article_types
        WHERE is_active = true
        ORDER BY id
        """
        
        rows = await db.fetch_all(query)
        return [ArticleTypeResponse(**dict(row)) for row in rows]
        
    except Exception as e:
        logger.error(f"Error getting article types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/topics/all", response_model=List[TopicResponse])
async def get_topics(db = Depends(get_database)):
    """Get all topics"""
    try:
        query = """
        SELECT id, name, slug, description, category, is_active, created_at
        FROM topics
        WHERE is_active = true
        ORDER BY category, name
        """
        
        rows = await db.fetch_all(query)
        return [TopicResponse(**dict(row)) for row in rows]
        
    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/tags/popular", response_model=List[TagResponse])
async def get_popular_tags(
    limit: int = Query(50, ge=1, le=100),
    db = Depends(get_database)
):
    """Get popular tags"""
    try:
        query = """
        SELECT id, name, slug, usage_count, created_at
        FROM tags
        WHERE usage_count > 0
        ORDER BY usage_count DESC, name ASC
        LIMIT $1
        """
        
        rows = await db.fetch_all(query, limit)
        return [TagResponse(**dict(row)) for row in rows]
        
    except Exception as e:
        logger.error(f"Error getting popular tags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# Article Authors Management Endpoints (for existing article_authors table)
class AddAuthorRequest(BaseModel):
    user_id: UUID
    role: str = "co-author"
    author_order: int = 99
    author_name: Optional[str] = None
    author_affiliation: Optional[str] = None
    author_email: Optional[str] = None

@router.post("/{article_id}/authors")
async def add_article_author(
    article_id: UUID,
    request: AddAuthorRequest,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Add author to article (admin only)"""
    try:
        # Insert into article_authors table
        query = """
        INSERT INTO article_authors (
            article_id, user_id, role, author_order, 
            author_name, author_affiliation, author_email, 
            added_by, added_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        ON CONFLICT (article_id, user_id) DO UPDATE SET
            role = EXCLUDED.role,
            author_order = EXCLUDED.author_order,
            author_name = EXCLUDED.author_name,
            author_affiliation = EXCLUDED.author_affiliation,
            author_email = EXCLUDED.author_email
        RETURNING id
        """
        
        result = await db.fetch_one(query, 
            article_id, request.user_id, request.role, request.author_order,
            request.author_name, request.author_affiliation, request.author_email,
            current_user.id if current_user else None
        )
        
        return {"message": "Author added successfully", "author_id": result["id"]}
        
    except Exception as e:
        logger.error(f"Error adding author to article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add author"
        )

@router.delete("/{article_id}/authors/{user_id}")
async def remove_article_author(
    article_id: UUID,
    user_id: UUID,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Remove author from article (admin only)"""
    try:
        # Check if author exists first
        check_query = "SELECT COUNT(*) FROM article_authors WHERE article_id = $1 AND user_id = $2"
        count = await db.fetch_val(check_query, article_id, user_id)
        
        if count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author not found in this article"
            )
            
        # Delete the author
        delete_query = "DELETE FROM article_authors WHERE article_id = $1 AND user_id = $2"
        await db.execute_query(delete_query, article_id, user_id)
        
        return {"message": "Author removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing author from article {article_id}: {e}")
        import traceback
        logger.error(f"Full error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove author: {str(e)}"
        )
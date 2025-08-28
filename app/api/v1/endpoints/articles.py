from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from app.core.database import get_database
from app.core.security import get_current_user, get_current_admin_user, get_optional_current_user
from app.models.user import UserResponse
from app.models.article import (
    ArticleCreate, ArticleUpdate, ArticleResponse, ArticleDetail,
    ArticleListItem, ArticleSearchRequest, ArticleSearchResponse,
    ArticleAdminUpdate, ArticleStats, ArticleStatus, AccessLevel,
    ArticleTypeResponse, TopicResponse, TagResponse
)
from app.services.article_service import ArticleService
from app.services.analytics_service import AnalyticsService
from app.services.activity_service import ActivityService, ActivityLogger
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Homepage endpoint (must come before article_identifier route)
@router.get("/homepage", response_model=dict)
async def get_homepage_articles(
    featured_limit: int = Query(5, ge=1, le=20, description="Number of featured articles"),
    popular_limit: int = Query(10, ge=1, le=50, description="Number of popular articles"),
    latest_limit: int = Query(10, ge=1, le=50, description="Number of latest articles"),
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Get homepage articles with featured, popular, and latest sections"""
    try:
        from app.services.analytics_service import AnalyticsService
        
        service = ArticleService(db)
        analytics_service = AnalyticsService(db)
        current_user_id = current_user.id if current_user else None
        
        # Get featured articles
        featured_request = ArticleSearchRequest(
            status=ArticleStatus.PUBLISHED,
            access_level=AccessLevel.PUBLIC,
            is_featured=True,
            sort_by="created_at",
            sort_order="desc",
            page=1,
            page_size=featured_limit
        )
        featured_response = await service.get_article_list(featured_request, current_user_id)
        
        # Get popular articles (last 30 days)
        popular_articles = await analytics_service.get_popular_articles(
            days=30,
            limit=popular_limit,
            sort_by="view_count_unique"
        )
        
        # Get latest articles
        latest_request = ArticleSearchRequest(
            status=ArticleStatus.PUBLISHED,
            access_level=AccessLevel.PUBLIC,
            sort_by="published_at",
            sort_order="desc",
            page=1,
            page_size=latest_limit
        )
        latest_response = await service.get_article_list(latest_request, current_user_id)
        
        return {
            "featured": {
                "articles": featured_response.items,
                "total": featured_response.total
            },
            "popular": {
                "articles": popular_articles,
                "criteria": {"days": 30, "sort_by": "view_count_unique"}
            },
            "latest": {
                "articles": latest_response.items,
                "total": latest_response.total
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting homepage articles: {e}")
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
@router.post("", response_model=ArticleDetail)
async def create_article(
    article_data: ArticleCreate,
    request: Request,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Create new article (admin only)"""
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
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Update article (admin only)"""
    try:
        service = ArticleService(db)
        
        # Check if article exists
        existing = await service.get_article_detail(article_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
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
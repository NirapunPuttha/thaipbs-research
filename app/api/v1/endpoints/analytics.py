from typing import Optional, Dict, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query

from app.core.database import get_database
from app.core.security import get_current_user, get_current_admin_user, get_optional_current_user
from app.models.user import UserResponse
from app.models.article import ArticleSearchResponse, ArticleListItem
from app.services.analytics_service import AnalyticsService
from app.services.article_service import ArticleService
from app.services.activity_service import ActivityService, ActivityLogger
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/share/{article_id}")
async def track_article_share(
    article_id: UUID,
    platform: str = Query(..., description="Platform name (facebook, twitter, line, etc.)"),
    request: Request = None,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    db = Depends(get_database)
):
    """Track article share (public endpoint)"""
    try:
        service = AnalyticsService(db)
        
        # Get client IP
        client_ip = request.client.host if request.client else None
        
        success = await service.track_article_share(
            article_id=article_id,
            platform=platform,
            ip_address=client_ip,
            user_id=current_user.id if current_user else None
        )
        
        if success:
            # Log activity
            try:
                activity_service = ActivityService(db)
                await ActivityLogger.log_share(
                    activity_service=activity_service,
                    article_id=article_id,
                    platform=platform,
                    user_id=current_user.id if current_user else None,
                    ip_address=client_ip,
                    user_agent=request.headers.get("user-agent") if request else None
                )
            except Exception as activity_error:
                logger.warning(f"Failed to log share activity: {activity_error}")
            
            return {"message": "Share tracked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to track share"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking share for article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track share"
        )

@router.post("/favorite/{article_id}")
async def add_to_favorites(
    article_id: UUID,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Add article to favorites (authenticated users only)"""
    try:
        service = AnalyticsService(db)
        
        success = await service.add_to_favorites(
            user_id=current_user.id,
            article_id=article_id
        )
        
        if success:
            # Log activity
            try:
                activity_service = ActivityService(db)
                client_ip = request.client.host if request.client else "unknown"
                await ActivityLogger.log_favorite_add(
                    activity_service=activity_service,
                    article_id=article_id,
                    user_id=current_user.id,
                    ip_address=client_ip,
                    user_agent=request.headers.get("user-agent")
                )
            except Exception as activity_error:
                logger.warning(f"Failed to log favorite add activity: {activity_error}")
            
            return {"message": "Added to favorites"}
        else:
            return {"message": "Already in favorites"}
        
    except Exception as e:
        logger.error(f"Error adding article {article_id} to favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add to favorites"
        )

@router.delete("/favorite/{article_id}")
async def remove_from_favorites(
    article_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Remove article from favorites (authenticated users only)"""
    try:
        service = AnalyticsService(db)
        
        success = await service.remove_from_favorites(
            user_id=current_user.id,
            article_id=article_id
        )
        
        if success:
            return {"message": "Removed from favorites"}
        else:
            return {"message": "Was not in favorites"}
        
    except Exception as e:
        logger.error(f"Error removing article {article_id} from favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove from favorites"
        )

@router.get("/favorite/{article_id}")
async def check_favorite_status(
    article_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Check if article is in user's favorites"""
    try:
        service = AnalyticsService(db)
        
        is_favorite = await service.is_favorite(
            user_id=current_user.id,
            article_id=article_id
        )
        
        return {"is_favorite": is_favorite}
        
    except Exception as e:
        logger.error(f"Error checking favorite status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check favorite status"
        )

@router.get("/favorites")
async def get_user_favorites(
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get user's favorite articles (simple list)"""
    try:
        service = AnalyticsService(db)
        
        article_ids = await service.get_user_favorites(current_user.id)
        
        return {
            "favorites": [str(article_id) for article_id in article_ids],
            "count": len(article_ids)
        }
        
    except Exception as e:
        logger.error(f"Error getting user favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get favorites"
        )

@router.get("/my-favorites", response_model=ArticleSearchResponse)
async def get_my_favorites_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    query: str = Query(None, description="Search in title and author name"),
    current_user: UserResponse = Depends(get_current_user),
    db = Depends(get_database)
):
    """Get user's favorite articles with full details and search"""
    try:
        analytics_service = AnalyticsService(db)
        
        # Get user's favorite article IDs
        favorite_ids = await analytics_service.get_user_favorites(current_user.id)
        
        if not favorite_ids:
            return ArticleSearchResponse(
                articles=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0
            )
        
        # Get articles with search functionality
        article_service = ArticleService(db)
        favorites_response = await article_service.get_favorite_articles(
            favorite_ids=favorite_ids,
            current_user_id=current_user.id,
            page=page,
            page_size=page_size,
            search_query=query
        )
        
        return favorites_response
        
    except Exception as e:
        logger.error(f"Error getting my favorites list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get favorites list"
        )

@router.get("/article/{article_id}")
async def get_article_analytics(
    article_id: UUID,
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get comprehensive analytics for an article (admin only)"""
    try:
        service = AnalyticsService(db)
        
        analytics = await service.get_article_analytics(article_id)
        
        if not analytics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found"
            )
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analytics for article {article_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get article analytics"
        )

@router.get("/popular")
async def get_popular_articles(
    days: int = Query(7, ge=1, le=365, description="Number of days to consider"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    sort_by: str = Query("view_count_unique", description="Sort metric"),
    db = Depends(get_database)
):
    """Get popular articles (public endpoint)"""
    try:
        service = AnalyticsService(db)
        
        articles = await service.get_popular_articles(
            days=days,
            limit=limit,
            sort_by=sort_by
        )
        
        return {
            "articles": articles,
            "criteria": {
                "days": days,
                "limit": limit,
                "sort_by": sort_by
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting popular articles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get popular articles"
        )

@router.get("/system")
async def get_system_analytics(
    current_user: UserResponse = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """Get system-wide analytics (admin only)"""
    try:
        service = AnalyticsService(db)
        
        analytics = await service.get_system_analytics()
        
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting system analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system analytics"
        )
import logging
from typing import Optional, Dict, List
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address, AddressValueError
import asyncio

from app.core.database import DatabaseManager
from app.models.article import ArticleStats
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def track_article_view(
        self, 
        article_id: UUID, 
        ip_address: str,
        user_id: Optional[UUID] = None,
        user_agent: Optional[str] = None,
        referrer: Optional[str] = None,
        session_id: Optional[str] = None,
        view_duration: Optional[int] = None
    ) -> bool:
        """Track article view - counts unique views per IP per day"""
        try:
            # Validate IP address
            try:
                if ':' in ip_address:
                    IPv6Address(ip_address)
                else:
                    IPv4Address(ip_address)
            except AddressValueError:
                logger.warning(f"Invalid IP address: {ip_address}")
                return False
            
            # Insert view record - check for existing view first
            check_query = """
            SELECT id FROM article_views 
            WHERE article_id = $1 AND ip_address = $2 AND DATE(created_at) = CURRENT_DATE
            """
            
            existing_view = await self.db.fetch_one(check_query, article_id, ip_address)
            
            if existing_view:
                # Already viewed today, just increment total count
                await self._increment_total_view_count(article_id)
                return True
            
            # Insert new view record
            view_query = """
            INSERT INTO article_views (
                article_id, user_id, ip_address, user_agent, referrer, 
                session_id, view_duration, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            RETURNING id
            """
            
            result = await self.db.fetch_one(
                view_query,
                article_id, user_id, ip_address, user_agent, 
                referrer, session_id, view_duration
            )
            
            # If a new view was inserted, update article counters
            if result:
                await self._update_article_view_counts(article_id)
                logger.info(f"New unique view tracked for article {article_id} from IP {ip_address}")
                return True
            
            # Always update total view count even if not unique
            await self._increment_total_view_count(article_id)
            return True
            
        except Exception as e:
            logger.error(f"Error tracking view for article {article_id}: {e}")
            return False
    
    async def track_article_share(
        self,
        article_id: UUID,
        platform: str,
        ip_address: Optional[str] = None,
        user_id: Optional[UUID] = None
    ) -> bool:
        """Track article share"""
        try:
            # Insert share record
            share_query = """
            INSERT INTO share_tracking (article_id, platform, ip_address, user_id)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """
            
            result = await self.db.fetch_one(
                share_query,
                article_id, platform, ip_address, user_id
            )
            
            if result:
                # Update article share count
                await self._increment_share_count(article_id)
                logger.info(f"Share tracked for article {article_id} on {platform}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error tracking share for article {article_id}: {e}")
            return False
    
    async def add_to_favorites(self, user_id: UUID, article_id: UUID) -> bool:
        """Add article to user favorites"""
        try:
            # Insert favorite record
            favorite_query = """
            INSERT INTO article_favorites (user_id, article_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, article_id) DO NOTHING
            RETURNING user_id
            """
            
            result = await self.db.fetch_one(favorite_query, user_id, article_id)
            
            if result:
                # Update article favorite count
                await self._increment_favorite_count(article_id)
                logger.info(f"Article {article_id} added to favorites by user {user_id}")
                return True
            
            return False  # Already in favorites
            
        except Exception as e:
            logger.error(f"Error adding article {article_id} to favorites: {e}")
            return False
    
    async def remove_from_favorites(self, user_id: UUID, article_id: UUID) -> bool:
        """Remove article from user favorites"""
        try:
            # Remove favorite record
            favorite_query = """
            DELETE FROM article_favorites 
            WHERE user_id = $1 AND article_id = $2
            RETURNING user_id
            """
            
            result = await self.db.fetch_one(favorite_query, user_id, article_id)
            
            if result:
                # Update article favorite count
                await self._decrement_favorite_count(article_id)
                logger.info(f"Article {article_id} removed from favorites by user {user_id}")
                return True
            
            return False  # Was not in favorites
            
        except Exception as e:
            logger.error(f"Error removing article {article_id} from favorites: {e}")
            return False
    
    async def is_favorite(self, user_id: UUID, article_id: UUID) -> bool:
        """Check if article is in user's favorites"""
        try:
            query = """
            SELECT 1 FROM article_favorites 
            WHERE user_id = $1 AND article_id = $2
            """
            
            result = await self.db.fetch_one(query, user_id, article_id)
            return result is not None
            
        except Exception as e:
            logger.error(f"Error checking favorite status: {e}")
            return False
    
    async def get_user_favorites(self, user_id: UUID) -> List[UUID]:
        """Get user's favorite article IDs"""
        try:
            query = """
            SELECT article_id FROM article_favorites 
            WHERE user_id = $1
            ORDER BY created_at DESC
            """
            
            rows = await self.db.fetch_all(query, user_id)
            return [row['article_id'] for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting user favorites: {e}")
            return []
    
    async def get_article_analytics(self, article_id: UUID) -> Dict:
        """Get comprehensive analytics for an article"""
        try:
            # Get article basic stats
            article_query = """
            SELECT view_count_unique, view_count_total, share_count, 
                   favorite_count, download_count, created_at, published_at
            FROM articles 
            WHERE id = $1
            """
            
            article_row = await self.db.fetch_one(article_query, article_id)
            if not article_row:
                return {}
            
            # Get view trends (last 30 days)
            trends_query = """
            SELECT DATE(created_at) as view_date, COUNT(*) as daily_views
            FROM article_views 
            WHERE article_id = $1 
              AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY view_date DESC
            """
            
            trends_rows = await self.db.fetch_all(trends_query, article_id)
            
            # Get share breakdown
            shares_query = """
            SELECT platform, COUNT(*) as share_count
            FROM share_tracking 
            WHERE article_id = $1 
            GROUP BY platform
            ORDER BY share_count DESC
            """
            
            shares_rows = await self.db.fetch_all(shares_query, article_id)
            
            # Get top referrers
            referrers_query = """
            SELECT referrer, COUNT(*) as referral_count
            FROM article_views 
            WHERE article_id = $1 
              AND referrer IS NOT NULL
              AND referrer != ''
            GROUP BY referrer
            ORDER BY referral_count DESC
            LIMIT 10
            """
            
            referrers_rows = await self.db.fetch_all(referrers_query, article_id)
            
            return {
                "article_id": str(article_id),
                "view_count_unique": article_row['view_count_unique'],
                "view_count_total": article_row['view_count_total'],
                "share_count": article_row['share_count'],
                "favorite_count": article_row['favorite_count'],
                "download_count": article_row['download_count'],
                "created_at": article_row['created_at'],
                "published_at": article_row['published_at'],
                "daily_trends": [
                    {
                        "date": str(row['view_date']),
                        "views": row['daily_views']
                    }
                    for row in trends_rows
                ],
                "share_breakdown": [
                    {
                        "platform": row['platform'],
                        "count": row['share_count']
                    }
                    for row in shares_rows
                ],
                "top_referrers": [
                    {
                        "referrer": row['referrer'],
                        "count": row['referral_count']
                    }
                    for row in referrers_rows
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics for article {article_id}: {e}")
            return {}
    
    async def get_popular_articles(
        self, 
        days: int = 7, 
        limit: int = 10,
        sort_by: str = "view_count_unique"
    ) -> List[Dict]:
        """Get popular articles by various metrics"""
        try:
            # Validate sort_by parameter
            allowed_sorts = ["view_count_unique", "view_count_total", "share_count", "favorite_count"]
            if sort_by not in allowed_sorts:
                sort_by = "view_count_unique"
            
            query = f"""
            SELECT a.id, a.title, a.slug, a.{sort_by}, 
                   a.created_at, a.published_at,
                   COUNT(av.id) as recent_views
            FROM articles a
            LEFT JOIN article_views av ON a.id = av.article_id 
                AND av.created_at >= NOW() - INTERVAL '{days} days'
            WHERE a.status = 'published'
            GROUP BY a.id, a.title, a.slug, a.{sort_by}, a.created_at, a.published_at
            ORDER BY a.{sort_by} DESC, recent_views DESC
            LIMIT $1
            """
            
            rows = await self.db.fetch_all(query, limit)
            
            return [
                {
                    "article_id": str(row['id']),
                    "title": row['title'],
                    "slug": row['slug'],
                    "metric_value": row[sort_by],
                    "recent_views": row['recent_views'],
                    "created_at": row['created_at'],
                    "published_at": row['published_at']
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Error getting popular articles: {e}")
            return []
    
    async def get_system_analytics(self) -> Dict:
        """Get system-wide analytics"""
        try:
            # Overall stats
            stats_query = """
            SELECT 
                COUNT(*) as total_articles,
                COUNT(*) FILTER (WHERE status = 'published') as published_articles,
                COUNT(*) FILTER (WHERE status = 'draft') as draft_articles,
                COUNT(*) FILTER (WHERE is_featured = true) as featured_articles,
                SUM(view_count_unique) as total_unique_views,
                SUM(view_count_total) as total_views,
                SUM(share_count) as total_shares,
                SUM(favorite_count) as total_favorites,
                SUM(download_count) as total_downloads
            FROM articles
            """
            
            stats_row = await self.db.fetch_one(stats_query)
            
            # User stats
            users_query = """
            SELECT 
                COUNT(*) as total_users,
                COUNT(*) FILTER (WHERE is_active = true) as active_users,
                COUNT(*) FILTER (WHERE level = 1) as level_1_users,
                COUNT(*) FILTER (WHERE level = 2) as level_2_users,
                COUNT(*) FILTER (WHERE level = 3) as level_3_users,
                COUNT(*) FILTER (WHERE is_admin = true) as admin_users
            FROM users
            """
            
            users_row = await self.db.fetch_one(users_query)
            
            # Recent activity (last 7 days)
            activity_query = """
            SELECT 
                COUNT(DISTINCT av.id) as recent_views,
                COUNT(DISTINCT st.id) as recent_shares,
                COUNT(DISTINCT af.user_id, af.article_id) as recent_favorites
            FROM article_views av
            FULL OUTER JOIN share_tracking st ON st.created_at >= NOW() - INTERVAL '7 days'
            FULL OUTER JOIN article_favorites af ON af.created_at >= NOW() - INTERVAL '7 days'
            WHERE av.created_at >= NOW() - INTERVAL '7 days'
            """
            
            activity_row = await self.db.fetch_one(activity_query)
            
            return {
                "articles": dict(stats_row) if stats_row else {},
                "users": dict(users_row) if users_row else {},
                "recent_activity": dict(activity_row) if activity_row else {},
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system analytics: {e}")
            return {}
    
    # Private helper methods
    async def _update_article_view_counts(self, article_id: UUID):
        """Update both unique and total view counts"""
        try:
            # Get unique view count
            unique_query = """
            SELECT COUNT(DISTINCT ip_address) as unique_count
            FROM article_views 
            WHERE article_id = $1
            """
            
            unique_row = await self.db.fetch_one(unique_query, article_id)
            unique_count = unique_row['unique_count'] if unique_row else 0
            
            # Get total view count
            total_query = """
            SELECT COUNT(*) as total_count
            FROM article_views 
            WHERE article_id = $1
            """
            
            total_row = await self.db.fetch_one(total_query, article_id)
            total_count = total_row['total_count'] if total_row else 0
            
            # Update article record
            update_query = """
            UPDATE articles 
            SET view_count_unique = $1, view_count_total = $2, updated_at = NOW()
            WHERE id = $3
            """
            
            await self.db.execute_query(update_query, unique_count, total_count, article_id)
            
        except Exception as e:
            logger.error(f"Error updating view counts for article {article_id}: {e}")
    
    async def _increment_total_view_count(self, article_id: UUID):
        """Increment only total view count"""
        try:
            query = """
            UPDATE articles 
            SET view_count_total = view_count_total + 1, updated_at = NOW()
            WHERE id = $1
            """
            
            await self.db.execute_query(query, article_id)
            
        except Exception as e:
            logger.error(f"Error incrementing total view count for article {article_id}: {e}")
    
    async def _increment_share_count(self, article_id: UUID):
        """Increment article share count"""
        try:
            query = """
            UPDATE articles 
            SET share_count = share_count + 1, updated_at = NOW()
            WHERE id = $1
            """
            
            await self.db.execute_query(query, article_id)
            
        except Exception as e:
            logger.error(f"Error incrementing share count for article {article_id}: {e}")
    
    async def _increment_favorite_count(self, article_id: UUID):
        """Increment article favorite count"""
        try:
            query = """
            UPDATE articles 
            SET favorite_count = favorite_count + 1, updated_at = NOW()
            WHERE id = $1
            """
            
            await self.db.execute_query(query, article_id)
            
        except Exception as e:
            logger.error(f"Error incrementing favorite count for article {article_id}: {e}")
    
    async def _decrement_favorite_count(self, article_id: UUID):
        """Decrement article favorite count"""
        try:
            query = """
            UPDATE articles 
            SET favorite_count = GREATEST(0, favorite_count - 1), updated_at = NOW()
            WHERE id = $1
            """
            
            await self.db.execute_query(query, article_id)
            
        except Exception as e:
            logger.error(f"Error decrementing favorite count for article {article_id}: {e}")
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from app.core.database import DatabaseManager
from app.models.user import (
    UserResponse, UserProfileUpdate, UserDetailedInfo, 
    DownloadHistoryItem, DownloadHistoryResponse, UserStats, UserProfileComplete
)
import logging

logger = logging.getLogger(__name__)

class UserProfileService:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def get_user_profile(self, user_id: UUID) -> Optional[UserResponse]:
        """Get user profile by ID"""
        try:
            query = """
            SELECT id, email, username, first_name, last_name, level, 
                   is_admin, is_active, download_count, detailed_info_submitted,
                   profile_image_url, profile_image_path, created_at, updated_at
            FROM users 
            WHERE id = $1 AND is_active = true
            """
            
            row = await self.db.fetch_one(query, user_id)
            if not row:
                return None
                
            return UserResponse(**dict(row))
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            raise
    
    async def get_complete_user_profile(self, user_id: UUID) -> Optional[UserProfileComplete]:
        """Get complete user profile with detailed info and statistics"""
        try:
            # Get basic user info with detailed info
            query = """
            SELECT id, email, username, first_name, last_name, level, 
                   is_admin, is_active, download_count, detailed_info_submitted,
                   profile_image_url, profile_image_path, created_at, updated_at,
                   address, phone, organization, research_purpose
            FROM users 
            WHERE id = $1 AND is_active = true
            """
            
            row = await self.db.fetch_one(query, user_id)
            if not row:
                return None
            
            user_dict = dict(row)
            
            # Get user statistics
            stats = await self.get_user_statistics(user_id)
            user_dict['stats'] = stats
            
            return UserProfileComplete(**user_dict)
            
        except Exception as e:
            logger.error(f"Error getting complete user profile: {e}")
            raise
    
    async def update_user_profile(
        self, 
        user_id: UUID, 
        profile_data: UserProfileUpdate
    ) -> Optional[UserResponse]:
        """Update user profile"""
        try:
            update_fields = []
            values = []
            param_count = 0
            
            for field, value in profile_data.dict(exclude_unset=True).items():
                if value is not None:
                    param_count += 1
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(value)
            
            if not update_fields:
                # No changes, return current profile
                return await self.get_user_profile(user_id)
            
            param_count += 1
            values.append(user_id)
            
            query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_count}
            RETURNING id, email, username, first_name, last_name, level, 
                     is_admin, is_active, download_count, detailed_info_submitted,
                     profile_image_url, profile_image_path, created_at, updated_at
            """
            
            row = await self.db.fetch_one(query, *values)
            if not row:
                return None
                
            return UserResponse(**dict(row))
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            raise
    
    async def submit_detailed_info(
        self, 
        user_id: UUID, 
        detailed_info: UserDetailedInfo
    ) -> bool:
        """Submit detailed user information (after 5+ downloads)"""
        try:
            # Check if user has 5+ downloads
            download_check = "SELECT download_count FROM users WHERE id = $1"
            user_row = await self.db.fetch_one(download_check, user_id)
            
            if not user_row or user_row['download_count'] < 5:
                raise ValueError("Must have at least 5 downloads to submit detailed information")
            
            query = """
            UPDATE users 
            SET address = $1, phone = $2, organization = $3, research_purpose = $4,
                detailed_info_submitted = true, updated_at = NOW()
            WHERE id = $5
            """
            
            result = await self.db.execute_query(
                query,
                detailed_info.address,
                detailed_info.phone,
                detailed_info.organization,
                detailed_info.research_purpose,
                user_id
            )
            
            return result == "UPDATE 1"
            
        except Exception as e:
            logger.error(f"Error submitting detailed info: {e}")
            raise
    
    async def get_download_history(
        self, 
        user_id: UUID, 
        page: int = 1, 
        page_size: int = 20
    ) -> DownloadHistoryResponse:
        """Get user's download history"""
        try:
            # Count total downloads
            count_query = "SELECT COUNT(*) as total FROM download_logs WHERE user_id = $1"
            count_row = await self.db.fetch_one(count_query, user_id)
            total = count_row['total'] if count_row else 0
            
            if total == 0:
                return DownloadHistoryResponse(
                    downloads=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                    total_pages=0
                )
            
            # Get downloads with article info
            offset = (page - 1) * page_size
            query = """
            SELECT 
                dl.id, dl.file_id, dl.article_id, dl.file_name, dl.file_type,
                dl.file_size, dl.downloaded_at, dl.ip_address,
                a.title as article_title
            FROM download_logs dl
            LEFT JOIN articles a ON dl.article_id = a.id
            WHERE dl.user_id = $1
            ORDER BY dl.downloaded_at DESC
            LIMIT $2 OFFSET $3
            """
            
            rows = await self.db.fetch_all(query, user_id, page_size, offset)
            
            downloads = []
            for row in rows:
                download_dict = dict(row)
                downloads.append(DownloadHistoryItem(**download_dict))
            
            total_pages = (total + page_size - 1) // page_size
            
            return DownloadHistoryResponse(
                downloads=downloads,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
            
        except Exception as e:
            logger.error(f"Error getting download history: {e}")
            raise
    
    async def get_user_statistics(self, user_id: UUID) -> UserStats:
        """Get comprehensive user statistics"""
        try:
            # Get basic user info
            user_query = "SELECT download_count, created_at, level FROM users WHERE id = $1"
            user_row = await self.db.fetch_one(user_query, user_id)
            
            if not user_row:
                raise ValueError("User not found")
            
            # Get download statistics
            download_stats_query = """
            SELECT 
                COUNT(*) as total_downloads,
                COUNT(DISTINCT article_id) as unique_articles,
                MAX(downloaded_at) as last_download_date
            FROM download_logs 
            WHERE user_id = $1
            """
            download_row = await self.db.fetch_one(download_stats_query, user_id)
            
            # Get most downloaded file type
            file_type_query = """
            SELECT file_type, COUNT(*) as count
            FROM download_logs 
            WHERE user_id = $1
            GROUP BY file_type
            ORDER BY count DESC
            LIMIT 1
            """
            file_type_row = await self.db.fetch_one(file_type_query, user_id)
            
            # Get favorites count
            favorites_query = "SELECT COUNT(*) as count FROM article_favorites WHERE user_id = $1"
            favorites_row = await self.db.fetch_one(favorites_query, user_id)
            
            # Get article views count (from activity logs)
            views_query = """
            SELECT COUNT(*) as count 
            FROM activity_logs 
            WHERE user_id = $1 AND action = 'view' AND entity_type = 'article'
            """
            views_row = await self.db.fetch_one(views_query, user_id)
            
            # Get recent activity count (last 30 days)
            recent_activity_query = """
            SELECT COUNT(*) as count 
            FROM activity_logs 
            WHERE user_id = $1 AND created_at >= $2
            """
            thirty_days_ago = datetime.now() - timedelta(days=30)
            activity_row = await self.db.fetch_one(recent_activity_query, user_id, thirty_days_ago)
            
            # Get last activity date
            last_activity_query = """
            SELECT MAX(created_at) as last_activity 
            FROM activity_logs 
            WHERE user_id = $1
            """
            last_activity_row = await self.db.fetch_one(last_activity_query, user_id)
            
            return UserStats(
                user_id=user_id,
                total_downloads=download_row['total_downloads'] if download_row else 0,
                unique_articles_downloaded=download_row['unique_articles'] if download_row else 0,
                favorite_articles_count=favorites_row['count'] if favorites_row else 0,
                total_article_views=views_row['count'] if views_row else 0,
                recent_activity_count=activity_row['count'] if activity_row else 0,
                most_downloaded_file_type=file_type_row['file_type'] if file_type_row else None,
                registration_date=user_row['created_at'],
                last_activity_date=last_activity_row['last_activity'] if last_activity_row else None,
                account_level=user_row['level']
            )
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            raise
    
    async def log_file_download(
        self,
        user_id: Optional[UUID],
        file_id: UUID,
        article_id: Optional[UUID],
        file_name: str,
        file_type: str,
        file_size: Optional[int],
        ip_address: Optional[str]
    ) -> bool:
        """Log a file download and update user download count"""
        try:
            # Insert download log
            log_query = """
            INSERT INTO download_logs (user_id, file_id, article_id, file_name, file_type, file_size, ip_address)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            
            await self.db.execute_query(
                log_query,
                user_id, file_id, article_id, file_name, file_type, file_size, ip_address
            )
            
            # Update user download count if user is logged in
            if user_id:
                count_query = """
                UPDATE users 
                SET download_count = download_count + 1, updated_at = NOW()
                WHERE id = $1
                """
                await self.db.execute_query(count_query, user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging file download: {e}")
            return False
    
    async def check_detailed_info_required(self, user_id: UUID) -> bool:
        """Check if user needs to submit detailed information"""
        try:
            query = """
            SELECT download_count, detailed_info_submitted 
            FROM users 
            WHERE id = $1
            """
            row = await self.db.fetch_one(query, user_id)
            
            if not row:
                return False
            
            # Require detailed info if user has 5+ downloads but hasn't submitted
            return row['download_count'] >= 5 and not row['detailed_info_submitted']
            
        except Exception as e:
            logger.error(f"Error checking detailed info requirement: {e}")
            return False
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import HTTPException

from app.core.database import DatabaseManager
from app.models.user import UserResponse, UserCreate, UserUpdate

logger = logging.getLogger(__name__)

class UserManagementService:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def get_all_users(
        self, 
        page: int = 1, 
        page_size: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
        is_creator: Optional[bool] = None,
        level: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get paginated list of users with filters"""
        try:
            # Build WHERE conditions
            conditions = ["1=1"]  # Base condition
            params = []
            param_count = 0
            
            if search:
                param_count += 1
                conditions.append(f"""
                    (username ILIKE ${param_count} OR 
                     email ILIKE ${param_count} OR 
                     first_name ILIKE ${param_count} OR 
                     last_name ILIKE ${param_count})
                """)
                params.append(f"%{search}%")
            
            if is_active is not None:
                param_count += 1
                conditions.append(f"is_active = ${param_count}")
                params.append(is_active)
            
            if is_admin is not None:
                param_count += 1
                conditions.append(f"is_admin = ${param_count}")
                params.append(is_admin)
            
            if is_creator is not None:
                param_count += 1
                conditions.append(f"is_creator = ${param_count}")
                params.append(is_creator)
            
            if level is not None:
                param_count += 1
                conditions.append(f"level = ${param_count}")
                params.append(level)
            
            where_clause = " AND ".join(conditions)
            
            # Validate sort fields
            valid_sorts = ["created_at", "updated_at", "username", "email", "level", "download_count"]
            if sort_by not in valid_sorts:
                sort_by = "created_at"
            
            if sort_order.lower() not in ["asc", "desc"]:
                sort_order = "desc"
            
            # Get total count
            count_query = f"""
                SELECT COUNT(*) as total 
                FROM users 
                WHERE {where_clause}
            """
            count_result = await self.db.fetch_one(count_query, *params)
            total = count_result["total"] if count_result else 0
            
            # Calculate pagination
            offset = (page - 1) * page_size
            total_pages = (total + page_size - 1) // page_size
            
            # Get users
            users_query = f"""
                SELECT id, email, username, first_name, last_name, level, 
                       is_admin, is_creator, is_active, download_count, detailed_info_submitted,
                       profile_image_url, created_at, updated_at
                FROM users 
                WHERE {where_clause}
                ORDER BY {sort_by} {sort_order.upper()}
                LIMIT ${param_count + 1} OFFSET ${param_count + 2}
            """
            params.extend([page_size, offset])
            
            users_rows = await self.db.fetch_all(users_query, *params)
            users = [UserResponse(**dict(row)) for row in users_rows]
            
            return {
                "items": users,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
            
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get users: {str(e)}")
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        """Get user by ID"""
        try:
            query = """
                SELECT id, email, username, first_name, last_name, level,
                       is_admin, is_creator, is_active, download_count, detailed_info_submitted,
                       profile_image_url, profile_image_path, created_at, updated_at
                FROM users 
                WHERE id = $1
            """
            
            row = await self.db.fetch_one(query, user_id)
            return UserResponse(**dict(row)) if row else None
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get user: {str(e)}")
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create new user (admin only)"""
        try:
            # Check if email already exists
            existing_user = await self._get_user_by_email(user_data.email)
            if existing_user:
                raise HTTPException(status_code=400, detail="Email already registered")
            
            # Check if username already exists
            if user_data.username:
                existing_username = await self._get_user_by_username(user_data.username)
                if existing_username:
                    raise HTTPException(status_code=400, detail="Username already taken")
            
            # Hash password
            from app.core.security import get_password_hash
            hashed_password = get_password_hash(user_data.password)
            
            # Insert user
            query = """
                INSERT INTO users (
                    email, username, first_name, last_name, password_hash,
                    level, is_admin, is_creator, is_active
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, email, username, first_name, last_name, level,
                          is_admin, is_creator, is_active, download_count, detailed_info_submitted,
                          profile_image_url, created_at, updated_at
            """
            
            row = await self.db.fetch_one(
                query,
                user_data.email,
                user_data.username,
                user_data.first_name,
                user_data.last_name, 
                hashed_password,
                user_data.level or 1,
                user_data.is_admin or False,
                user_data.is_creator or False,
                user_data.is_active if user_data.is_active is not None else True
            )
            
            if not row:
                raise HTTPException(status_code=500, detail="Failed to create user")
            
            logger.info(f"User created: {user_data.email}")
            return UserResponse(**dict(row))
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")
    
    async def update_user(self, user_id: UUID, update_data: UserUpdate) -> Optional[UserResponse]:
        """Update user (admin only)"""
        try:
            # Check if user exists
            existing_user = await self.get_user_by_id(user_id)
            if not existing_user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Build update fields
            set_clauses = []
            params = []
            param_count = 0
            
            # Check for email conflicts
            if update_data.email and update_data.email != existing_user.email:
                existing_email = await self._get_user_by_email(update_data.email)
                if existing_email and existing_email["id"] != user_id:
                    raise HTTPException(status_code=400, detail="Email already registered")
                
                param_count += 1
                set_clauses.append(f"email = ${param_count}")
                params.append(update_data.email)
            
            # Check for username conflicts
            if update_data.username and update_data.username != existing_user.username:
                existing_username = await self._get_user_by_username(update_data.username)
                if existing_username and existing_username["id"] != user_id:
                    raise HTTPException(status_code=400, detail="Username already taken")
                
                param_count += 1
                set_clauses.append(f"username = ${param_count}")
                params.append(update_data.username)
            
            # Other fields
            if update_data.first_name is not None:
                param_count += 1
                set_clauses.append(f"first_name = ${param_count}")
                params.append(update_data.first_name)
            
            if update_data.last_name is not None:
                param_count += 1
                set_clauses.append(f"last_name = ${param_count}")
                params.append(update_data.last_name)
            
            if update_data.level is not None:
                param_count += 1
                set_clauses.append(f"level = ${param_count}")
                params.append(update_data.level)
            
            if update_data.is_admin is not None:
                param_count += 1
                set_clauses.append(f"is_admin = ${param_count}")
                params.append(update_data.is_admin)
            
            if update_data.is_creator is not None:
                param_count += 1
                set_clauses.append(f"is_creator = ${param_count}")
                params.append(update_data.is_creator)
            
            if update_data.is_active is not None:
                param_count += 1
                set_clauses.append(f"is_active = ${param_count}")
                params.append(update_data.is_active)
            
            if update_data.password:
                from app.core.security import get_password_hash
                hashed_password = get_password_hash(update_data.password)
                param_count += 1
                set_clauses.append(f"password_hash = ${param_count}")
                params.append(hashed_password)
            
            if not set_clauses:
                return existing_user  # No changes
            
            # Add updated_at
            param_count += 1
            set_clauses.append(f"updated_at = ${param_count}")
            params.append(datetime.utcnow())
            
            # Add user_id for WHERE clause
            param_count += 1
            params.append(user_id)
            
            # Update query
            query = f"""
                UPDATE users 
                SET {", ".join(set_clauses)}
                WHERE id = ${param_count}
                RETURNING id, email, username, first_name, last_name, level,
                          is_admin, is_creator, is_active, download_count, detailed_info_submitted,
                          profile_image_url, created_at, updated_at
            """
            
            row = await self.db.fetch_one(query, *params)
            
            if not row:
                raise HTTPException(status_code=500, detail="Failed to update user")
            
            logger.info(f"User updated: {user_id}")
            return UserResponse(**dict(row))
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")
    
    async def delete_user(self, user_id: UUID, soft_delete: bool = True) -> bool:
        """Delete user (soft delete by default)"""
        try:
            if soft_delete:
                # Soft delete - set is_active to false
                query = """
                    UPDATE users 
                    SET is_active = false, updated_at = NOW()
                    WHERE id = $1 AND id != (
                        SELECT id FROM users WHERE is_admin = true ORDER BY created_at LIMIT 1
                    )
                """
                result = await self.db.execute_query(query, user_id)
                success = result == "UPDATE 1"
            else:
                # Hard delete - actually remove from database
                query = """
                    DELETE FROM users 
                    WHERE id = $1 AND id != (
                        SELECT id FROM users WHERE is_admin = true ORDER BY created_at LIMIT 1
                    )
                """
                result = await self.db.execute_query(query, user_id)
                success = result == "DELETE 1"
            
            if success:
                logger.info(f"User {'soft' if soft_delete else 'hard'} deleted: {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")
    
    async def reset_user_password(self, user_id: UUID, new_password: str) -> bool:
        """Reset user password (admin only)"""
        try:
            from app.core.security import get_password_hash
            hashed_password = get_password_hash(new_password)
            
            query = """
                UPDATE users 
                SET password_hash = $1, updated_at = NOW()
                WHERE id = $2
            """
            
            result = await self.db.execute_query(query, hashed_password, user_id)
            success = result == "UPDATE 1"
            
            if success:
                logger.info(f"Password reset for user: {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error resetting password for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to reset password: {str(e)}")
    
    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics for dashboard"""
        try:
            stats_query = """
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(*) FILTER (WHERE is_active = true) as active_users,
                    COUNT(*) FILTER (WHERE is_admin = true) as admin_users,
                    COUNT(*) FILTER (WHERE detailed_info_submitted = true) as detailed_users,
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as new_users_30d,
                    AVG(download_count) as avg_downloads,
                    MAX(download_count) as max_downloads
                FROM users
            """
            
            stats_row = await self.db.fetch_one(stats_query)
            
            # Level distribution
            level_query = """
                SELECT level, COUNT(*) as count
                FROM users 
                WHERE is_active = true
                GROUP BY level
                ORDER BY level
            """
            level_rows = await self.db.fetch_all(level_query)
            level_distribution = {row["level"]: row["count"] for row in level_rows}
            
            # Recent registrations (last 7 days)
            recent_query = """
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM users 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """
            recent_rows = await self.db.fetch_all(recent_query)
            recent_registrations = [
                {"date": row["date"].isoformat(), "count": row["count"]} 
                for row in recent_rows
            ]
            
            return {
                "total_users": stats_row["total_users"] or 0,
                "active_users": stats_row["active_users"] or 0,
                "admin_users": stats_row["admin_users"] or 0,
                "detailed_users": stats_row["detailed_users"] or 0,
                "new_users_30d": stats_row["new_users_30d"] or 0,
                "avg_downloads": float(stats_row["avg_downloads"] or 0),
                "max_downloads": stats_row["max_downloads"] or 0,
                "level_distribution": level_distribution,
                "recent_registrations": recent_registrations
            }
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")
    
    async def _get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Helper: Get user by email"""
        query = "SELECT id, email FROM users WHERE email = $1"
        row = await self.db.fetch_one(query, email)
        return dict(row) if row else None
    
    async def _get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Helper: Get user by username"""
        query = "SELECT id, username FROM users WHERE username = $1"
        row = await self.db.fetch_one(query, username)
        return dict(row) if row else None
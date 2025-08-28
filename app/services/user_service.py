from typing import Optional, List
from uuid import UUID
import asyncpg
from app.core.database import DatabaseManager
from app.core.security import get_password_hash, verify_password
from app.models.user import UserCreate, UserResponse, UserProfileUpdate, UserDetailedInfo, UserAdminUpdate
import logging

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def create_user(self, user_data: UserCreate) -> Optional[UserResponse]:
        """Create a new user"""
        try:
            # Hash password
            hashed_password = get_password_hash(user_data.password)
            
            # Insert user into database
            query = """
            INSERT INTO users (email, password_hash, username, first_name, last_name)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, email, username, first_name, last_name, level, is_admin, 
                      is_active, download_count, detailed_info_submitted, created_at, updated_at
            """
            
            row = await self.db.fetch_one(
                query,
                user_data.email,
                hashed_password,
                user_data.username,
                user_data.first_name,
                user_data.last_name
            )
            
            if row:
                return UserResponse(**dict(row))
            return None
            
        except asyncpg.UniqueViolationError as e:
            if "email" in str(e):
                raise ValueError("Email already registered")
            elif "username" in str(e):
                raise ValueError("Username already taken")
            else:
                raise ValueError("User already exists")
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user by email (including password hash for authentication)"""
        query = """
        SELECT id, email, password_hash, username, first_name, last_name, 
               level, is_admin, is_active, download_count, detailed_info_submitted,
               created_at, updated_at
        FROM users 
        WHERE email = $1 AND is_active = true
        """
        
        row = await self.db.fetch_one(query, email)
        return dict(row) if row else None
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        """Get user by ID (without password hash)"""
        query = """
        SELECT id, email, username, first_name, last_name, level, is_admin, 
               is_active, download_count, detailed_info_submitted, 
               profile_image_url, profile_image_path, created_at, updated_at
        FROM users 
        WHERE id = $1 AND is_active = true
        """
        
        row = await self.db.fetch_one(query, user_id)
        return UserResponse(**dict(row)) if row else None
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserResponse]:
        """Authenticate user with email and password"""
        user_data = await self.get_user_by_email(email)
        if not user_data:
            return None
            
        if not verify_password(password, user_data["password_hash"]):
            return None
            
        # Remove password hash before returning
        del user_data["password_hash"]
        return UserResponse(**user_data)
    
    async def update_user_profile(self, user_id: UUID, update_data: UserProfileUpdate) -> Optional[UserResponse]:
        """Update user profile"""
        try:
            # Build dynamic update query
            update_fields = []
            values = []
            param_count = 0
            
            for field, value in update_data.dict(exclude_unset=True).items():
                param_count += 1
                update_fields.append(f"{field} = ${param_count}")
                values.append(value)
            
            if not update_fields:
                # No fields to update
                return await self.get_user_by_id(user_id)
            
            param_count += 1
            values.append(user_id)
            
            query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_count}
            RETURNING id, email, username, first_name, last_name, level, is_admin, 
                      is_active, download_count, detailed_info_submitted, created_at, updated_at
            """
            
            row = await self.db.fetch_one(query, *values)
            return UserResponse(**dict(row)) if row else None
            
        except asyncpg.UniqueViolationError:
            raise ValueError("Username already taken")
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            raise
    
    async def submit_detailed_info(self, user_id: UUID, detailed_info: UserDetailedInfo) -> Optional[UserResponse]:
        """Submit detailed user info (after 5+ downloads)"""
        query = """
        UPDATE users 
        SET address = $1, phone = $2, organization = $3, research_purpose = $4,
            detailed_info_submitted = true, updated_at = NOW()
        WHERE id = $5
        RETURNING id, email, username, first_name, last_name, level, is_admin, 
                  is_active, download_count, detailed_info_submitted, created_at, updated_at
        """
        
        row = await self.db.fetch_one(
            query,
            detailed_info.address,
            detailed_info.phone,
            detailed_info.organization,
            detailed_info.research_purpose,
            user_id
        )
        
        return UserResponse(**dict(row)) if row else None
    
    async def increment_download_count(self, user_id: UUID) -> bool:
        """Increment user's download count"""
        query = """
        UPDATE users 
        SET download_count = download_count + 1, updated_at = NOW()
        WHERE id = $1
        """
        
        result = await self.db.execute_query(query, user_id)
        return result == "UPDATE 1"
    
    # Admin functions
    async def get_all_users(self, limit: int = 50, offset: int = 0) -> List[UserResponse]:
        """Get all users (admin only)"""
        query = """
        SELECT id, email, username, first_name, last_name, level, is_admin, 
               is_active, download_count, detailed_info_submitted, created_at, updated_at
        FROM users 
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """
        
        rows = await self.db.fetch_all(query, limit, offset)
        return [UserResponse(**dict(row)) for row in rows]
    
    async def update_user_admin(self, user_id: UUID, update_data: UserAdminUpdate) -> Optional[UserResponse]:
        """Update user (admin only)"""
        # Build dynamic update query
        update_fields = []
        values = []
        param_count = 0
        
        for field, value in update_data.dict(exclude_unset=True).items():
            param_count += 1
            update_fields.append(f"{field} = ${param_count}")
            values.append(value)
        
        if not update_fields:
            return await self.get_user_by_id(user_id)
        
        param_count += 1
        values.append(user_id)
        
        query = f"""
        UPDATE users 
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING id, email, username, first_name, last_name, level, is_admin, 
                  is_active, download_count, detailed_info_submitted, created_at, updated_at
        """
        
        row = await self.db.fetch_one(query, *values)
        return UserResponse(**dict(row)) if row else None
    
    async def get_user_stats(self) -> dict:
        """Get user statistics (admin only)"""
        query = """
        SELECT 
            COUNT(*) as total_users,
            COUNT(*) FILTER (WHERE is_active = true) as active_users,
            COUNT(*) FILTER (WHERE detailed_info_submitted = true) as detailed_info_users,
            COUNT(*) FILTER (WHERE is_admin = true) as admin_users,
            AVG(download_count) as avg_downloads
        FROM users
        """
        
        row = await self.db.fetch_one(query)
        return dict(row) if row else {}
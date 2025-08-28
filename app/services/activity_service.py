from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
from app.core.database import DatabaseManager
import logging
import json

logger = logging.getLogger(__name__)

class ActivityService:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def log_activity(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        article_id: Optional[UUID] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Log user activity"""
        try:
            query = """
            INSERT INTO activity_logs (
                user_id, article_id, action, entity_type, entity_id,
                old_values, new_values, ip_address, user_agent
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """
            
            # Convert dictionaries to JSON strings
            old_json = json.dumps(old_values) if old_values else None
            new_json = json.dumps(new_values) if new_values else None
            
            await self.db.execute_query(
                query,
                user_id, article_id, action, entity_type, entity_id,
                old_json, new_json, ip_address, user_agent
            )
            
            logger.info(f"Activity logged: {action} on {entity_type} by user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")
            return False
    
    async def get_user_activity(
        self,
        user_id: UUID,
        days: int = 30,
        limit: int = 50,
        action_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get user's activity history"""
        try:
            conditions = ["user_id = $1", "created_at >= $2"]
            params = [user_id, datetime.now() - timedelta(days=days)]
            param_count = 2
            
            if action_filter:
                param_count += 1
                conditions.append(f"action = ${param_count}")
                params.append(action_filter)
            
            where_clause = " AND ".join(conditions)
            
            query = f"""
            SELECT 
                id, user_id, article_id, action, entity_type, entity_id,
                old_values, new_values, ip_address, user_agent, created_at
            FROM activity_logs
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_count + 1}
            """
            
            params.append(limit)
            rows = await self.db.fetch_all(query, *params)
            
            activities = []
            for row in rows:
                activity = dict(row)
                # Parse JSON fields
                if activity['old_values']:
                    activity['old_values'] = json.loads(activity['old_values'])
                if activity['new_values']:
                    activity['new_values'] = json.loads(activity['new_values'])
                activities.append(activity)
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting user activity: {e}")
            return []
    
    async def get_article_activity(
        self,
        article_id: UUID,
        days: int = 30,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get activity history for a specific article"""
        try:
            query = """
            SELECT 
                al.id, al.user_id, al.article_id, al.action, al.entity_type, 
                al.entity_id, al.old_values, al.new_values, al.ip_address, 
                al.user_agent, al.created_at,
                u.username, u.first_name, u.last_name
            FROM activity_logs al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.article_id = $1 AND al.created_at >= $2
            ORDER BY al.created_at DESC
            LIMIT $3
            """
            
            since_date = datetime.now() - timedelta(days=days)
            rows = await self.db.fetch_all(query, article_id, since_date, limit)
            
            activities = []
            for row in rows:
                activity = dict(row)
                # Parse JSON fields
                if activity['old_values']:
                    activity['old_values'] = json.loads(activity['old_values'])
                if activity['new_values']:
                    activity['new_values'] = json.loads(activity['new_values'])
                activities.append(activity)
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting article activity: {e}")
            return []
    
    async def get_system_activity(
        self,
        days: int = 7,
        limit: int = 100,
        action_filter: Optional[str] = None,
        entity_type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get system-wide activity (admin only)"""
        try:
            conditions = ["created_at >= $1"]
            params = [datetime.now() - timedelta(days=days)]
            param_count = 1
            
            if action_filter:
                param_count += 1
                conditions.append(f"action = ${param_count}")
                params.append(action_filter)
            
            if entity_type_filter:
                param_count += 1
                conditions.append(f"entity_type = ${param_count}")
                params.append(entity_type_filter)
            
            where_clause = " AND ".join(conditions)
            
            query = f"""
            SELECT 
                al.id, al.user_id, al.article_id, al.action, al.entity_type,
                al.entity_id, al.old_values, al.new_values, al.ip_address,
                al.user_agent, al.created_at,
                u.username, u.first_name, u.last_name,
                a.title as article_title
            FROM activity_logs al
            LEFT JOIN users u ON al.user_id = u.id
            LEFT JOIN articles a ON al.article_id = a.id
            WHERE {where_clause}
            ORDER BY al.created_at DESC
            LIMIT ${param_count + 1}
            """
            
            params.append(limit)
            rows = await self.db.fetch_all(query, *params)
            
            activities = []
            for row in rows:
                activity = dict(row)
                # Parse JSON fields
                if activity['old_values']:
                    activity['old_values'] = json.loads(activity['old_values'])
                if activity['new_values']:
                    activity['new_values'] = json.loads(activity['new_values'])
                activities.append(activity)
            
            return activities
            
        except Exception as e:
            logger.error(f"Error getting system activity: {e}")
            return []
    
    async def get_activity_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get activity summary statistics"""
        try:
            since_date = datetime.now() - timedelta(days=days)
            
            query = """
            SELECT 
                action,
                entity_type,
                COUNT(*) as count,
                COUNT(DISTINCT user_id) as unique_users
            FROM activity_logs
            WHERE created_at >= $1
            GROUP BY action, entity_type
            ORDER BY count DESC
            """
            
            rows = await self.db.fetch_all(query, since_date)
            
            summary = {
                "period_days": days,
                "total_activities": 0,
                "activities_by_action": {},
                "activities_by_entity": {},
                "top_activities": []
            }
            
            for row in rows:
                activity_data = dict(row)
                summary["total_activities"] += activity_data["count"]
                
                # Group by action
                if activity_data["action"] not in summary["activities_by_action"]:
                    summary["activities_by_action"][activity_data["action"]] = 0
                summary["activities_by_action"][activity_data["action"]] += activity_data["count"]
                
                # Group by entity type
                if activity_data["entity_type"] not in summary["activities_by_entity"]:
                    summary["activities_by_entity"][activity_data["entity_type"]] = 0
                summary["activities_by_entity"][activity_data["entity_type"]] += activity_data["count"]
                
                # Top activities
                summary["top_activities"].append({
                    "action": activity_data["action"],
                    "entity_type": activity_data["entity_type"],
                    "count": activity_data["count"],
                    "unique_users": activity_data["unique_users"]
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting activity summary: {e}")
            return {}

# Activity logging helper functions
class ActivityLogger:
    """Helper class for common activity logging patterns"""
    
    @staticmethod
    async def log_article_view(
        activity_service: ActivityService,
        article_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log article view activity"""
        await activity_service.log_activity(
            action="view",
            entity_type="article",
            entity_id=article_id,
            article_id=article_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    async def log_article_create(
        activity_service: ActivityService,
        article_id: UUID,
        user_id: UUID,
        new_values: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log article creation"""
        await activity_service.log_activity(
            action="create",
            entity_type="article",
            entity_id=article_id,
            article_id=article_id,
            user_id=user_id,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    async def log_article_update(
        activity_service: ActivityService,
        article_id: UUID,
        user_id: UUID,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log article update"""
        await activity_service.log_activity(
            action="update",
            entity_type="article",
            entity_id=article_id,
            article_id=article_id,
            user_id=user_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    async def log_article_delete(
        activity_service: ActivityService,
        article_id: UUID,
        user_id: UUID,
        old_values: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log article deletion"""
        await activity_service.log_activity(
            action="delete",
            entity_type="article",
            entity_id=article_id,
            article_id=article_id,
            user_id=user_id,
            old_values=old_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    async def log_favorite_add(
        activity_service: ActivityService,
        article_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log adding article to favorites"""
        await activity_service.log_activity(
            action="favorite",
            entity_type="article",
            entity_id=article_id,
            article_id=article_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    async def log_favorite_remove(
        activity_service: ActivityService,
        article_id: UUID,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log removing article from favorites"""
        await activity_service.log_activity(
            action="unfavorite",
            entity_type="article",
            entity_id=article_id,
            article_id=article_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    async def log_file_download(
        activity_service: ActivityService,
        file_id: UUID,
        article_id: Optional[UUID],
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log file download"""
        await activity_service.log_activity(
            action="download",
            entity_type="file",
            entity_id=file_id,
            article_id=article_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    async def log_share(
        activity_service: ActivityService,
        article_id: UUID,
        platform: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log article share"""
        await activity_service.log_activity(
            action="share",
            entity_type="article",
            entity_id=article_id,
            article_id=article_id,
            user_id=user_id,
            new_values={"platform": platform},
            ip_address=ip_address,
            user_agent=user_agent
        )
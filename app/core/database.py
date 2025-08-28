import asyncpg
import asyncio
from typing import Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=settings.DB_POOL_MIN_SIZE,
                max_size=settings.DB_POOL_MAX_SIZE,
                command_timeout=30,
                server_settings={
                    'application_name': 'thaipbs_research',
                }
            )
            logger.info(f"Database pool created with {settings.DB_POOL_MIN_SIZE}-{settings.DB_POOL_MAX_SIZE} connections")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")
    
    async def execute_query(self, query: str, *args):
        """Execute a query that doesn't return results"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            if settings.ENABLE_QUERY_LOGGING:
                logger.debug(f"Executing query: {query} with args: {args}")
            return await connection.execute(query, *args)
    
    async def fetch_one(self, query: str, *args):
        """Execute a query and return one row"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            if settings.ENABLE_QUERY_LOGGING:
                logger.debug(f"Fetching one: {query} with args: {args}")
            return await connection.fetchrow(query, *args)
    
    async def fetch_all(self, query: str, *args):
        """Execute a query and return all rows"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            if settings.ENABLE_QUERY_LOGGING:
                logger.debug(f"Fetching all: {query} with args: {args}")
            return await connection.fetch(query, *args)
    
    async def fetch_val(self, query: str, *args):
        """Execute a query and return a single value"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            if settings.ENABLE_QUERY_LOGGING:
                logger.debug(f"Fetching value: {query} with args: {args}")
            return await connection.fetchval(query, *args)

# Global database manager instance
db = DatabaseManager()

# Database dependency for FastAPI
async def get_database():
    return db
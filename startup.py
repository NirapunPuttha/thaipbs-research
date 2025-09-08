import asyncio
import logging
from app.core.database import db
from app.core.supabase import supabase_client
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

async def startup():
    """Initialize all connections on startup"""
    try:
        # Skip database connection if using dummy URL
        if settings.DATABASE_URL and "dummy" not in settings.DATABASE_URL.lower():
            # Initialize database connection
            await db.connect()
            
            # Test database connection
            result = await db.fetch_val("SELECT 1")
            if result == 1:
                logging.info("Database connection successful")
        else:
            logging.info("Skipping database connection - using dummy URL")
        
        # Initialize Supabase client (skip for now due to version compatibility)
        # supabase_client.initialize()
        
        logging.info("All startup tasks completed successfully")
        
    except Exception as e:
        logging.error(f"Startup failed: {e}")
        raise

async def shutdown():
    """Cleanup on shutdown"""
    try:
        await db.disconnect()
        logging.info("Shutdown completed successfully")
    except Exception as e:
        logging.error(f"Shutdown error: {e}")

if __name__ == "__main__":
    # For testing startup/shutdown
    asyncio.run(startup())
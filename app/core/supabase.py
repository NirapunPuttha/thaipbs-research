from supabase import create_client, Client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        self.client: Client = None
        self.admin_client: Client = None
    
    def initialize(self):
        """Initialize Supabase clients"""
        try:
            # Regular client with anon key (if available)
            if settings.SUPABASE_ANON_KEY:
                self.client = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_ANON_KEY
                )
            
            # Admin client with service role key
            self.admin_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY
            )
            
            logger.info("Supabase clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase clients: {e}")
            raise
    
    def get_client(self) -> Client:
        """Get regular Supabase client"""
        if not self.client:
            raise RuntimeError("Supabase client not initialized")
        return self.client
    
    def get_admin_client(self) -> Client:
        """Get admin Supabase client with full privileges"""
        if not self.admin_client:
            raise RuntimeError("Supabase admin client not initialized")
        return self.admin_client

# Global Supabase instance
supabase_client = SupabaseClient()

# Dependency for FastAPI
def get_supabase() -> Client:
    return supabase_client.get_client() if supabase_client.client else supabase_client.get_admin_client()

def get_supabase_admin() -> Client:
    return supabase_client.get_admin_client()
#!/usr/bin/env python3
"""
Quick database setup script to create essential tables
Run this instead of manually copying SQL to Supabase
"""
import asyncio
import sys
from app.core.database import db
from app.core.config import settings

async def setup_database():
    """Setup database with essential tables"""
    print("🗄️  Setting up database...")
    
    try:
        await db.connect()
        print("✅ Connected to database")
        
        # Create users table
        print("📝 Creating users table...")
        users_sql = """
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            username VARCHAR(100) UNIQUE NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            level INTEGER DEFAULT 1 CHECK (level IN (1, 2, 3)),
            is_admin BOOLEAN DEFAULT false,
            is_active BOOLEAN DEFAULT true,
            download_count INTEGER DEFAULT 0,
            detailed_info_submitted BOOLEAN DEFAULT false,
            address TEXT,
            phone VARCHAR(20),
            organization VARCHAR(255),
            research_purpose TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
        
        await db.execute_query(users_sql)
        print("✅ Users table created")
        
        # Create basic indexes
        print("📊 Creating indexes...")
        indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """
        
        await db.execute_query(indexes_sql)
        print("✅ Indexes created")
        
        # Create triggers
        print("🔧 Creating triggers...")
        trigger_sql = """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        CREATE TRIGGER update_users_updated_at 
            BEFORE UPDATE ON users 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
        
        await db.execute_query(trigger_sql)
        print("✅ Triggers created")
        
        # Test query
        result = await db.fetch_val("SELECT COUNT(*) FROM users")
        print(f"✅ Database setup complete! Current users count: {result}")
        
        await db.disconnect()
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(setup_database())
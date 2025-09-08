-- Update Database Schema - Co-Authors Table & Performance Indexes
-- Run this script in Supabase SQL Editor to update existing database

-- ===============================
-- ADD MISSING TABLES
-- ===============================

-- Article co-authors table (for Co-Authors Management API)
CREATE TABLE IF NOT EXISTS article_co_authors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    role VARCHAR(50) DEFAULT 'Co-Author',
    "order" INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_id, user_id)
);

-- ===============================
-- ADD PERFORMANCE INDEXES
-- ===============================

-- Critical indexes for performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_status_level ON articles(status, access_level);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC) WHERE status = 'published';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_article_views_daily_unique ON article_views(article_id, ip_address, DATE(created_at));

-- Additional useful indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_featured ON articles(is_featured, status) WHERE is_featured = true;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_created_at ON articles(created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_download_logs_user_date ON download_logs(user_id, DATE(created_at));
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_article_favorites_user ON article_favorites(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_article_co_authors_article ON article_co_authors(article_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_logs_user_date ON activity_logs(user_id, DATE(created_at));

-- ===============================
-- VERIFICATION QUERIES
-- ===============================

-- Check if table was created
SELECT EXISTS (
   SELECT FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name = 'article_co_authors'
) AS table_exists;

-- Check indexes
SELECT schemaname, tablename, indexname
FROM pg_indexes 
WHERE tablename IN ('articles', 'article_views', 'download_logs', 'article_favorites', 'article_co_authors', 'activity_logs')
ORDER BY tablename, indexname;

-- Test Co-Authors table with sample query
SELECT COUNT(*) as co_authors_count FROM article_co_authors;
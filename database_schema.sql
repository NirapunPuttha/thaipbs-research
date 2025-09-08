-- Thailand PBS Research Management System Database Schema
-- Execute this script in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===============================
-- CORE TABLES
-- ===============================

-- Users table
CREATE TABLE users (
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
    -- Detailed info fields (filled after 5+ downloads)
    address TEXT,
    phone VARCHAR(20),
    organization VARCHAR(255),
    research_purpose TEXT,
    -- Profile image fields
    profile_image_url TEXT,
    profile_image_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Article types table
CREATE TABLE article_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Topics table
CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tags table
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Articles table
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    slug VARCHAR(500) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    excerpt TEXT,
    cover_image_url TEXT,
    article_type_id INTEGER REFERENCES article_types(id),
    access_level INTEGER DEFAULT 1 CHECK (access_level IN (1, 2, 3)),
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'suspended')),
    is_featured BOOLEAN DEFAULT false,
    view_count_unique INTEGER DEFAULT 0,
    view_count_total INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    favorite_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    created_by UUID REFERENCES users(id) NOT NULL,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ===============================
-- RELATIONSHIP TABLES (Many-to-Many)
-- ===============================

-- Article authors (Many-to-Many)
CREATE TABLE article_authors (
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'co-author',
    added_by UUID REFERENCES users(id),
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (article_id, user_id)
);

-- Article co-authors table (for Co-Authors Management API)
CREATE TABLE article_co_authors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    role VARCHAR(50) DEFAULT 'Co-Author',
    "order" INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_id, user_id)
);

-- Article topics (Many-to-Many)
CREATE TABLE article_topics (
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, topic_id)
);

-- Article tags (Many-to-Many)
CREATE TABLE article_tags (
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

-- ===============================
-- FILE MANAGEMENT
-- ===============================

-- Article files
CREATE TABLE article_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    file_type VARCHAR(20) CHECK (file_type IN ('pdf', 'image', 'youtube')),
    original_name VARCHAR(255),
    file_path TEXT,
    file_url TEXT,
    youtube_url TEXT,
    youtube_embed_id VARCHAR(20),
    file_size BIGINT,
    mime_type VARCHAR(100),
    download_count INTEGER DEFAULT 0,
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===============================
-- ANALYTICS & TRACKING
-- ===============================

-- Article views
CREATE TABLE article_views (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address INET NOT NULL,
    user_agent TEXT,
    referrer TEXT,
    session_id VARCHAR(255),
    view_duration INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_id, ip_address, DATE(created_at))
);

-- Article favorites
CREATE TABLE article_favorites (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, article_id)
);

-- Download logs
CREATE TABLE download_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    file_id UUID REFERENCES article_files(id) ON DELETE SET NULL,
    ip_address INET NOT NULL,
    user_agent TEXT,
    download_size BIGINT,
    completed BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Activity logs
CREATE TABLE activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    article_id UUID REFERENCES articles(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Share tracking
CREATE TABLE share_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    platform VARCHAR(50),
    ip_address INET,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===============================
-- INDEXES FOR PERFORMANCE
-- ===============================

-- Critical indexes
CREATE INDEX CONCURRENTLY idx_articles_status_level ON articles(status, access_level);
CREATE INDEX CONCURRENTLY idx_articles_published_at ON articles(published_at DESC) WHERE status = 'published';
CREATE INDEX CONCURRENTLY idx_article_views_daily_unique ON article_views(article_id, ip_address, DATE(created_at));
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_users_username ON users(username);
CREATE INDEX CONCURRENTLY idx_articles_created_by ON articles(created_by);
CREATE INDEX CONCURRENTLY idx_download_logs_user ON download_logs(user_id);

-- Full-text search preparation
ALTER TABLE articles ADD COLUMN search_vector tsvector;
CREATE INDEX CONCURRENTLY idx_articles_search ON articles USING GIN(search_vector);

-- ===============================
-- TRIGGERS
-- ===============================

-- Update timestamps trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply timestamp triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_articles_updated_at BEFORE UPDATE ON articles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Search vector update trigger function
CREATE OR REPLACE FUNCTION update_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('simple', 
        COALESCE(NEW.title, '') || ' ' || 
        COALESCE(NEW.content, '') || ' ' || 
        COALESCE(NEW.excerpt, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply search vector trigger
CREATE TRIGGER articles_search_update 
    BEFORE INSERT OR UPDATE ON articles 
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- ===============================
-- DEFAULT DATA
-- ===============================

-- Insert default article types
INSERT INTO article_types (name, slug) VALUES 
('Article', 'article'),
('Short Reads', 'short-reads'),
('Full Text', 'full-text'),
('Media', 'media');

-- Insert default topics with 12 main categories
INSERT INTO topics (name, slug, category) VALUES 
-- Trends
('Media Industry', 'media-industry', 'Trends'),
('Technology Society', 'technology-society', 'Trends'),
-- Audience & Platform
('Platforms', 'platforms', 'Audience & Platform'),
('Time Slots', 'time-slots', 'Audience & Platform'),
-- Age & Generation
('Children', 'children', 'Age & Generation'),
('Teenagers', 'teenagers', 'Age & Generation'),
('Working-age Adults', 'working-age-adults', 'Age & Generation'),
('Elderly', 'elderly', 'Age & Generation'),
-- People
('Marginalized Groups', 'marginalized-groups', 'People'),
('Vulnerable People', 'vulnerable-people', 'People'),
-- Public Service Media
('Public Media', 'public-media', 'Public Service Media'),
('Roles', 'roles', 'Public Service Media'),
('Branding', 'branding', 'Public Service Media'),
-- News
('News', 'news', 'News'),
('News Programs', 'news-programs', 'News'),
-- Documentary
('Documentaries', 'documentaries', 'Documentary'),
-- Drama & Entertainment
('Entertainment', 'entertainment', 'Drama & Entertainment'),
('Variety', 'variety', 'Drama & Entertainment'),
('Sports', 'sports', 'Drama & Entertainment'),
('Drama', 'drama', 'Drama & Entertainment'),
('Series', 'series', 'Drama & Entertainment'),
-- Politics & Public Policy
('Social Issues', 'social-issues', 'Politics & Public Policy'),
('Political-Public', 'political-public', 'Politics & Public Policy'),
('Civic Policies', 'civic-policies', 'Politics & Public Policy'),
-- Learning
('Children Programs', 'children-programs', 'Learning'),
('Learning', 'learning', 'Learning'),
-- Culture & History
('Arts & Culture', 'arts-culture', 'Culture & History'),
('History', 'history', 'Culture & History'),
-- Environment & Disaster
('Natural Resources', 'natural-resources', 'Environment & Disaster'),
('Environment', 'environment', 'Environment & Disaster'),
('Disasters', 'disasters', 'Environment & Disaster');

-- ===============================
-- PERFORMANCE INDEXES
-- ===============================

-- Critical indexes for performance
CREATE INDEX CONCURRENTLY idx_articles_status_level ON articles(status, access_level);
CREATE INDEX CONCURRENTLY idx_articles_published_at ON articles(published_at DESC) WHERE status = 'published';
CREATE INDEX CONCURRENTLY idx_article_views_daily_unique ON article_views(article_id, ip_address, DATE(created_at));

-- Additional useful indexes
CREATE INDEX CONCURRENTLY idx_articles_featured ON articles(is_featured, status) WHERE is_featured = true;
CREATE INDEX CONCURRENTLY idx_articles_created_at ON articles(created_at DESC);
CREATE INDEX CONCURRENTLY idx_download_logs_user_date ON download_logs(user_id, DATE(created_at));
CREATE INDEX CONCURRENTLY idx_article_favorites_user ON article_favorites(user_id);
CREATE INDEX CONCURRENTLY idx_article_co_authors_article ON article_co_authors(article_id);
CREATE INDEX CONCURRENTLY idx_activity_logs_user_date ON activity_logs(user_id, DATE(created_at));
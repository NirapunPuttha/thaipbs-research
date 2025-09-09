-- Migration: Add MinIO support to database schema
-- Date: 2025-09-09
-- Description: Add columns to support MinIO object storage alongside local file storage

-- Add MinIO support to users table (profile images)
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS profile_image_minio_object VARCHAR,
ADD COLUMN IF NOT EXISTS profile_storage_type VARCHAR DEFAULT 'local';

-- Add MinIO support to article_files table
ALTER TABLE article_files 
ADD COLUMN IF NOT EXISTS minio_object_name VARCHAR,
ADD COLUMN IF NOT EXISTS storage_type VARCHAR DEFAULT 'local';

-- Add MinIO support to articles table (cover images)
ALTER TABLE articles 
ADD COLUMN IF NOT EXISTS cover_image_minio_object VARCHAR,
ADD COLUMN IF NOT EXISTS cover_storage_type VARCHAR DEFAULT 'local';

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_profile_storage_type ON users(profile_storage_type);
CREATE INDEX IF NOT EXISTS idx_article_files_storage_type ON article_files(storage_type);
CREATE INDEX IF NOT EXISTS idx_articles_cover_storage_type ON articles(cover_storage_type);

-- Add comments for documentation
COMMENT ON COLUMN users.profile_image_minio_object IS 'MinIO object name for profile image (e.g., profiles/uuid.jpg)';
COMMENT ON COLUMN users.profile_storage_type IS 'Storage type: local or minio';

COMMENT ON COLUMN article_files.minio_object_name IS 'MinIO object name for article file (e.g., articles/uuid.pdf)';
COMMENT ON COLUMN article_files.storage_type IS 'Storage type: local or minio';

COMMENT ON COLUMN articles.cover_image_minio_object IS 'MinIO object name for cover image (e.g., covers/uuid.jpg)';
COMMENT ON COLUMN articles.cover_storage_type IS 'Storage type: local or minio';

-- Optional: Create a function to get file URL based on storage type
CREATE OR REPLACE FUNCTION get_file_url(
    storage_type VARCHAR,
    local_path VARCHAR,
    minio_object VARCHAR,
    minio_base_url VARCHAR DEFAULT 'http://188.166.231.229:9000/research-file'
) RETURNS VARCHAR AS $$
BEGIN
    IF storage_type = 'minio' AND minio_object IS NOT NULL THEN
        RETURN minio_base_url || '/' || minio_object;
    ELSIF storage_type = 'local' AND local_path IS NOT NULL THEN
        RETURN local_path;
    ELSE
        RETURN NULL;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create a view for easy file URL access (users)
CREATE OR REPLACE VIEW user_profile_images AS
SELECT 
    id,
    username,
    email,
    profile_storage_type,
    profile_image_path,
    profile_image_minio_object,
    get_file_url(
        profile_storage_type,
        profile_image_url,
        profile_image_minio_object
    ) as profile_image_url_resolved,
    created_at,
    updated_at
FROM users
WHERE is_active = true;

-- Create a view for easy file URL access (article files)
CREATE OR REPLACE VIEW article_files_with_urls AS
SELECT 
    af.*,
    get_file_url(
        af.storage_type,
        af.file_url,
        af.minio_object_name
    ) as file_url_resolved
FROM article_files af;

-- Create a view for easy cover image access (articles)
CREATE OR REPLACE VIEW articles_with_cover_urls AS
SELECT 
    a.*,
    get_file_url(
        a.cover_storage_type,
        a.cover_image_url,
        a.cover_image_minio_object
    ) as cover_image_url_resolved
FROM articles a;
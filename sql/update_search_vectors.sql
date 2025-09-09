-- Update search vector function to use 'simple' language for better multilingual support
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

-- Update existing search vectors for all articles
UPDATE articles SET search_vector = to_tsvector('simple', 
    COALESCE(title, '') || ' ' || 
    COALESCE(content, '') || ' ' || 
    COALESCE(excerpt, '')
);

-- Refresh the search index
REINDEX INDEX idx_articles_search;
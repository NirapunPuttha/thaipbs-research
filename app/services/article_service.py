from typing import Optional, List
from uuid import UUID
import asyncpg
from slugify import slugify
from app.core.database import DatabaseManager
from app.models.article import (
    ArticleCreate, ArticleCreateMinimal, ArticleUpdate, ArticleResponse, ArticleDetail, 
    ArticleListItem, ArticleSearchRequest, ArticleSearchResponse,
    ArticleAdminUpdate, ArticleStats, ArticleStatus, AccessLevel,
    ArticleTypeResponse, TopicResponse, TagResponse, ArticleFileResponse
)
import logging

logger = logging.getLogger(__name__)

class ArticleService:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def create_article(self, article_data: ArticleCreate, created_by: UUID) -> Optional[ArticleDetail]:
        """Create a new article"""
        try:
            # Generate slug from title
            base_slug = slugify(article_data.title)
            slug = await self._generate_unique_slug(base_slug)
            
            # Insert article
            article_query = """
            INSERT INTO articles (title, slug, content, excerpt, cover_image_url, 
                                article_type_id, access_level, is_featured, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, title, slug, content, excerpt, cover_image_url, 
                      article_type_id, access_level, status, is_featured,
                      view_count_unique, view_count_total, share_count, 
                      favorite_count, download_count, created_by, 
                      published_at, created_at, updated_at
            """
            
            article_row = await self.db.fetch_one(
                article_query,
                article_data.title, slug, article_data.content, article_data.excerpt,
                article_data.cover_image_url, article_data.article_type_id,
                article_data.access_level.value, article_data.is_featured, created_by
            )
            
            if not article_row:
                return None
                
            article_id = article_row['id']
            
            # Add topics
            if article_data.topic_ids:
                await self._add_article_topics(article_id, article_data.topic_ids)
            
            # Add tags
            if article_data.tag_names:
                await self._add_article_tags(article_id, article_data.tag_names)
            
            # Get complete article details
            return await self.get_article_detail(article_id)
            
        except Exception as e:
            logger.error(f"Error creating article: {e}")
            raise

    async def get_article_detail(self, article_id: UUID) -> Optional[ArticleDetail]:
        """Get article with full details"""
        try:
            # Get article basic info
            article_query = """
            SELECT a.id, a.title, a.slug, a.content, a.excerpt, a.cover_image_url,
                   a.article_type_id, a.access_level, a.status, a.is_featured,
                   a.view_count_unique, a.view_count_total, a.share_count,
                   a.favorite_count, a.download_count, a.created_by,
                   a.published_at, a.created_at, a.updated_at,
                   at.id as type_id, at.name as type_name, at.slug as type_slug,
                   at.description as type_description
            FROM articles a
            LEFT JOIN article_types at ON a.article_type_id = at.id
            WHERE a.id = $1
            """
            
            article_row = await self.db.fetch_one(article_query, article_id)
            if not article_row:
                return None
            
            # Build article response
            article_dict = dict(article_row)
            article_type = None
            if article_dict['type_id']:
                article_type = ArticleTypeResponse(
                    id=article_dict['type_id'],
                    name=article_dict['type_name'], 
                    slug=article_dict['type_slug'],
                    description=article_dict['type_description'],
                    is_active=True,
                    created_at=article_dict['created_at']
                )
            
            # Get topics
            topics = await self._get_article_topics(article_id)
            
            # Get tags  
            tags = await self._get_article_tags(article_id)
            
            # Get files
            files = await self._get_article_files(article_id)
            
            # Get authors
            authors = await self._get_article_authors(article_id)
            
            article_response = ArticleResponse(**{k: v for k, v in article_dict.items() 
                                                if k not in ['type_id', 'type_name', 'type_slug', 'type_description']})
            
            return ArticleDetail(
                **article_response.model_dump(),
                article_type=article_type,
                topics=topics,
                tags=tags, 
                files=files,
                authors=authors
            )
            
        except Exception as e:
            logger.error(f"Error getting article detail: {e}")
            raise

    async def get_article_by_slug(self, slug: str) -> Optional[ArticleDetail]:
        """Get article by slug with full details"""
        try:
            # Get article basic info by slug
            article_query = """
            SELECT a.id, a.title, a.slug, a.content, a.excerpt, a.cover_image_url,
                   a.article_type_id, a.access_level, a.status, a.is_featured,
                   a.view_count_unique, a.view_count_total, a.share_count,
                   a.favorite_count, a.download_count, a.created_by,
                   a.published_at, a.created_at, a.updated_at,
                   at.id as type_id, at.name as type_name, at.slug as type_slug,
                   at.description as type_description
            FROM articles a
            LEFT JOIN article_types at ON a.article_type_id = at.id
            WHERE a.slug = $1
            """
            
            article_row = await self.db.fetch_one(article_query, slug)
            if not article_row:
                return None
            
            # Use the existing logic from get_article_detail
            article_dict = dict(article_row)
            article_id = article_dict['id']
            
            article_type = None
            if article_dict['type_id']:
                article_type = ArticleTypeResponse(
                    id=article_dict['type_id'],
                    name=article_dict['type_name'], 
                    slug=article_dict['type_slug'],
                    description=article_dict['type_description'],
                    is_active=True,
                    created_at=article_dict['created_at']
                )
            
            # Get topics
            topics = await self._get_article_topics(article_id)
            
            # Get tags  
            tags = await self._get_article_tags(article_id)
            
            # Get files
            files = await self._get_article_files(article_id)
            
            # Get authors
            authors = await self._get_article_authors(article_id)
            
            article_response = ArticleResponse(**{k: v for k, v in article_dict.items() 
                                                if k not in ['type_id', 'type_name', 'type_slug', 'type_description']})
            
            return ArticleDetail(
                **article_response.model_dump(),
                article_type=article_type,
                topics=topics,
                tags=tags, 
                files=files,
                authors=authors
            )
            
        except Exception as e:
            logger.error(f"Error getting article by slug: {e}")
            raise

    async def get_article_list(self, search_req: ArticleSearchRequest, current_user_id: Optional[UUID] = None) -> ArticleSearchResponse:
        """Get paginated list of articles with search/filter"""
        try:
            # Build WHERE conditions
            where_conditions = []
            params = []
            param_count = 0
            
            # Status filter
            if search_req.status:
                param_count += 1
                where_conditions.append(f"a.status = ${param_count}")
                params.append(search_req.status.value)
            
            # Text search (supports both full-text and pattern matching for multilingual content)
            if search_req.query:
                param_count += 1
                search_condition = f"""
                (a.search_vector @@ plainto_tsquery('simple', ${param_count}) OR 
                 a.title ILIKE ${param_count + 1} OR 
                 a.content ILIKE ${param_count + 1} OR 
                 a.excerpt ILIKE ${param_count + 1})
                """
                where_conditions.append(search_condition)
                params.append(search_req.query)  # For full-text search
                param_count += 1
                params.append(f"%{search_req.query}%")  # For ILIKE search
            
            # Author search by name
            if search_req.author_query:
                param_count += 1
                where_conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM users u 
                    WHERE u.id = a.created_by 
                    AND (u.username ILIKE ${param_count} OR u.first_name ILIKE ${param_count} OR u.last_name ILIKE ${param_count})
                ) OR EXISTS (
                    SELECT 1 FROM article_authors aa 
                    JOIN users u ON aa.user_id = u.id 
                    WHERE aa.article_id = a.id 
                    AND (u.username ILIKE ${param_count} OR u.first_name ILIKE ${param_count} OR u.last_name ILIKE ${param_count})
                )
                """)
                params.append(f"%{search_req.author_query}%")
            
            # Author filter by specific IDs
            if search_req.author_ids:
                param_count += 1
                where_conditions.append(f"""
                (a.created_by = ANY(${param_count}) OR 
                 EXISTS (
                    SELECT 1 FROM article_authors aa 
                    WHERE aa.article_id = a.id 
                    AND aa.user_id = ANY(${param_count})
                ))
                """)
                params.append(search_req.author_ids)
            
            # Article type filter
            if search_req.article_type_ids:
                param_count += 1
                where_conditions.append(f"a.article_type_id = ANY(${param_count})")
                params.append(search_req.article_type_ids)
            
            # Access level filter
            if search_req.access_level:
                param_count += 1
                where_conditions.append(f"a.access_level <= ${param_count}")
                params.append(search_req.access_level.value)
            
            # Featured filter
            if search_req.is_featured is not None:
                param_count += 1
                where_conditions.append(f"a.is_featured = ${param_count}")
                params.append(search_req.is_featured)
            
            # Date filters
            if search_req.created_after:
                param_count += 1
                where_conditions.append(f"a.created_at >= ${param_count}")
                params.append(search_req.created_after)
                
            if search_req.created_before:
                param_count += 1
                where_conditions.append(f"a.created_at <= ${param_count}")
                params.append(search_req.created_before)
            
            # Build WHERE clause
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Build ORDER BY
            order_by = f"ORDER BY a.{search_req.sort_by} {search_req.sort_order.upper()}"
            
            # Get total count
            count_query = f"""
            SELECT COUNT(DISTINCT a.id) as total
            FROM articles a
            {where_clause}
            """
            
            count_row = await self.db.fetch_one(count_query, *params)
            total = count_row['total'] if count_row else 0
            
            # Get articles
            param_count += 1
            limit_param = param_count
            param_count += 1
            offset_param = param_count
            
            articles_query = f"""
            SELECT DISTINCT a.id, a.title, a.slug, a.excerpt, a.cover_image_url,
                   a.access_level, a.status, a.is_featured, a.view_count_unique,
                   a.favorite_count, a.created_by, a.published_at, a.created_at,
                   at.id as type_id, at.name as type_name, at.slug as type_slug,
                   at.description as type_description
            FROM articles a
            LEFT JOIN article_types at ON a.article_type_id = at.id
            {where_clause}
            {order_by}
            LIMIT ${limit_param} OFFSET ${offset_param}
            """
            
            params.extend([search_req.page_size, (search_req.page - 1) * search_req.page_size])
            # Get user's favorites if user is authenticated
            user_favorites = set()
            if current_user_id:
                favorites_query = "SELECT article_id FROM article_favorites WHERE user_id = $1"
                favorite_rows = await self.db.fetch_all(favorites_query, current_user_id)
                user_favorites = {row['article_id'] for row in favorite_rows}
            
            articles_rows = await self.db.fetch_all(articles_query, *params)
            
            # Build response items
            items = []
            for row in articles_rows:
                article_dict = dict(row)
                article_type = None
                if article_dict['type_id']:
                    article_type = ArticleTypeResponse(
                        id=article_dict['type_id'],
                        name=article_dict['type_name'],
                        slug=article_dict['type_slug'], 
                        description=article_dict['type_description'],
                        is_active=True,
                        created_at=article_dict['created_at']
                    )
                
                # Get topics, tags, and authors for each article
                topics = await self._get_article_topics(article_dict['id'])
                tags = await self._get_article_tags(article_dict['id'])
                authors = await self._get_article_authors(article_dict['id'])
                
                # Check if article is in user's favorites
                is_favorite = article_dict['id'] in user_favorites
                
                item = ArticleListItem(
                    **{k: v for k, v in article_dict.items() 
                       if k not in ['type_id', 'type_name', 'type_slug', 'type_description']},
                    article_type=article_type,
                    topics=topics,
                    tags=tags,
                    authors=authors,
                    is_favorite=is_favorite
                )
                items.append(item)
            
            total_pages = (total + search_req.page_size - 1) // search_req.page_size
            
            return ArticleSearchResponse(
                items=items,
                total=total,
                page=search_req.page,
                page_size=search_req.page_size,
                total_pages=total_pages
            )
            
        except Exception as e:
            logger.error(f"Error getting article list: {e}")
            raise

    async def create_article_minimal(self, article_data: 'ArticleCreateMinimal', created_by: UUID) -> Optional[ArticleDetail]:
        """Create a new article with minimal data - just type and draft content"""
        try:
            # Generate slug from title (or use default)
            base_slug = slugify(article_data.title) if article_data.title != "Untitled Draft" else f"untitled-draft-{created_by}"
            slug = await self._generate_unique_slug(base_slug)
            
            # Insert article with minimal data and draft status
            article_query = """
            INSERT INTO articles (title, slug, content, article_type_id, 
                                access_level, is_featured, status, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id, title, slug, content, excerpt, cover_image_url, 
                      article_type_id, access_level, status, is_featured,
                      view_count_unique, view_count_total, share_count, 
                      favorite_count, download_count, created_by, 
                      published_at, created_at, updated_at
            """
            
            article_row = await self.db.fetch_one(
                article_query,
                article_data.title,
                slug,
                article_data.content,
                article_data.article_type_id,
                1,  # Default access_level = PUBLIC
                False,  # Default is_featured = False
                'draft',  # Force status to draft
                created_by
            )
            
            if not article_row:
                return None
            
            # Get article detail to return complete object
            article_id = article_row['id']
            return await self.get_article_detail(article_id)
            
        except Exception as e:
            logger.error(f"Error creating minimal article: {e}")
            raise

    async def update_article(self, article_id: UUID, update_data: ArticleUpdate) -> Optional[ArticleDetail]:
        """Update article"""
        try:
            # Build dynamic update query
            update_fields = []
            values = []
            param_count = 0
            
            for field, value in update_data.dict(exclude_unset=True).items():
                if field in ['topic_ids', 'tag_names']:
                    continue  # Handle separately
                    
                param_count += 1
                if field in ['access_level', 'status']:
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(value.value)
                else:
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(value)
            
            # Update slug if title changed
            if update_data.title:
                base_slug = slugify(update_data.title)
                slug = await self._generate_unique_slug(base_slug, exclude_id=article_id)
                param_count += 1
                update_fields.append(f"slug = ${param_count}")
                values.append(slug)
            
            if update_fields:
                param_count += 1
                values.append(article_id)
                
                query = f"""
                UPDATE articles 
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE id = ${param_count}
                """
                
                await self.db.execute_query(query, *values)
            
            # Update topics
            if update_data.topic_ids is not None:
                await self._replace_article_topics(article_id, update_data.topic_ids)
            
            # Update tags
            if update_data.tag_names is not None:
                await self._replace_article_tags(article_id, update_data.tag_names)
            
            return await self.get_article_detail(article_id)
            
        except Exception as e:
            logger.error(f"Error updating article: {e}")
            raise

    async def delete_article(self, article_id: UUID) -> bool:
        """Soft delete article"""
        try:
            query = """
            UPDATE articles 
            SET status = 'suspended', updated_at = NOW()
            WHERE id = $1
            """
            
            result = await self.db.execute_query(query, article_id)
            return result == "UPDATE 1"
            
        except Exception as e:
            logger.error(f"Error deleting article: {e}")
            raise

    async def publish_article(self, article_id: UUID) -> Optional[ArticleDetail]:
        """Publish article"""
        try:
            query = """
            UPDATE articles 
            SET status = 'published', published_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND status = 'draft'
            """
            
            result = await self.db.execute_query(query, article_id)
            if result == "UPDATE 1":
                return await self.get_article_detail(article_id)
            return None
            
        except Exception as e:
            logger.error(f"Error publishing article: {e}")
            raise

    # Helper methods
    async def _generate_unique_slug(self, base_slug: str, exclude_id: UUID = None) -> str:
        """Generate unique slug"""
        slug = base_slug
        counter = 1
        
        while True:
            query = "SELECT id FROM articles WHERE slug = $1"
            params = [slug]
            
            if exclude_id:
                query += " AND id != $2"
                params.append(exclude_id)
            
            existing = await self.db.fetch_one(query, *params)
            if not existing:
                return slug
                
            slug = f"{base_slug}-{counter}"
            counter += 1

    async def _get_article_topics(self, article_id: UUID) -> List[TopicResponse]:
        """Get topics for article"""
        query = """
        SELECT t.id, t.name, t.slug, t.description, t.category, t.is_active, t.created_at
        FROM topics t
        JOIN article_topics at ON t.id = at.topic_id
        WHERE at.article_id = $1 AND t.is_active = true
        ORDER BY t.name
        """
        
        rows = await self.db.fetch_all(query, article_id)
        return [TopicResponse(**dict(row)) for row in rows]

    async def _get_article_tags(self, article_id: UUID) -> List[TagResponse]:
        """Get tags for article"""
        query = """
        SELECT t.id, t.name, t.slug, t.usage_count, t.created_at
        FROM tags t
        JOIN article_tags at ON t.id = at.tag_id
        WHERE at.article_id = $1
        ORDER BY t.name
        """
        
        rows = await self.db.fetch_all(query, article_id)
        return [TagResponse(**dict(row)) for row in rows]

    async def _get_article_files(self, article_id: UUID) -> List[ArticleFileResponse]:
        """Get files for article"""
        query = """
        SELECT id, article_id, file_type, original_name, file_path, file_url,
               youtube_url, youtube_embed_id, file_size, mime_type,
               download_count, uploaded_by, created_at
        FROM article_files
        WHERE article_id = $1
        ORDER BY created_at
        """
        
        rows = await self.db.fetch_all(query, article_id)
        return [ArticleFileResponse(**dict(row)) for row in rows]

    async def _get_article_authors(self, article_id: UUID) -> List[dict]:
        """Get authors for article (both user-based and text-based) ordered by author_order"""
        query = """
        SELECT aa.id, aa.role, aa.author_order,
               -- User-based author info
               u.id as user_id, u.username, u.first_name, u.last_name,
               -- Text-based author info  
               aa.author_name, aa.author_affiliation, aa.author_email
        FROM article_authors aa
        LEFT JOIN users u ON aa.user_id = u.id
        WHERE aa.article_id = $1
        ORDER BY aa.author_order, aa.added_at
        """
        
        rows = await self.db.fetch_all(query, article_id)
        authors = []
        
        for row in rows:
            author = dict(row)
            
            # Format author info based on type
            if author['user_id']:
                # User-based author
                author['type'] = 'user'
                author['display_name'] = f"{author['first_name']} {author['last_name']}".strip()
                author['identifier'] = author['username']
            else:
                # Text-based author  
                author['type'] = 'text'
                author['display_name'] = author['author_name']
                author['identifier'] = author['author_email'] or author['author_affiliation'] or author['author_name']
            
            authors.append(author)
        
        return authors

    async def get_favorite_articles(
        self, 
        favorite_ids: List[UUID], 
        current_user_id: UUID = None,
        page: int = 1, 
        page_size: int = 20,
        search_query: str = None
    ) -> ArticleSearchResponse:
        """Get favorite articles with search and pagination"""
        try:
            # Build WHERE conditions for favorites
            where_conditions = ["a.id = ANY($1)"]  # Only favorite articles
            params = [favorite_ids]
            param_count = 1
            
            # Add search condition
            if search_query:
                param_count += 1
                search_condition = f"""
                (a.title ILIKE ${param_count} OR 
                 EXISTS (
                    SELECT 1 FROM article_authors aa 
                    LEFT JOIN users u ON aa.user_id = u.id
                    WHERE aa.article_id = a.id AND (
                        u.first_name ILIKE ${param_count} OR u.last_name ILIKE ${param_count} OR
                        aa.author_name ILIKE ${param_count}
                    )
                 ))
                """
                where_conditions.append(search_condition)
                params.append(f"%{search_query}%")
            
            # Only show published articles
            param_count += 1
            where_conditions.append(f"a.status = ${param_count}")
            params.append("published")
            
            where_clause = " AND ".join(where_conditions)
            
            # Count total
            count_query = f"""
            SELECT COUNT(DISTINCT a.id) 
            FROM articles a
            WHERE {where_clause}
            """
            
            total_row = await self.db.fetch_one(count_query, *params)
            total = total_row['count'] if total_row else 0
            
            if total == 0:
                return ArticleSearchResponse(
                    items=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                    total_pages=0
                )
            
            # Calculate pagination
            total_pages = (total + page_size - 1) // page_size
            offset = (page - 1) * page_size
            
            # Main query for articles
            articles_query = f"""
            SELECT DISTINCT a.id, a.title, a.slug, a.excerpt, a.cover_image_url,
                   a.article_type_id, a.access_level, a.status, a.is_featured,
                   a.view_count_unique, a.favorite_count, a.created_by,
                   a.published_at, a.created_at,
                   at.id as type_id, at.name as type_name, at.slug as type_slug,
                   at.description as type_description
            FROM articles a
            LEFT JOIN article_types at ON a.article_type_id = at.id
            WHERE {where_clause}
            ORDER BY a.created_at DESC
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
            """
            
            params.extend([page_size, offset])
            
            article_rows = await self.db.fetch_all(articles_query, *params)
            articles = []
            
            for row in article_rows:
                article_dict = dict(row)
                article_id = article_dict['id']
                
                # Build article type
                article_type = None
                if article_dict['type_id']:
                    article_type = ArticleTypeResponse(
                        id=article_dict['type_id'],
                        name=article_dict['type_name'],
                        slug=article_dict['type_slug'], 
                        description=article_dict['type_description'],
                        is_active=True,
                        created_at=article_dict['created_at']
                    )
                
                # Get topics, tags, and authors
                topics = await self._get_article_topics(article_id)
                tags = await self._get_article_tags(article_id)
                authors = await self._get_article_authors(article_id)
                
                # Create article item with is_favorite = True (since these are all favorites)
                article_item = ArticleListItem(
                    **{k: v for k, v in article_dict.items() 
                       if k not in ['type_id', 'type_name', 'type_slug', 'type_description']},
                    article_type=article_type,
                    topics=topics,
                    tags=tags,
                    authors=authors,
                    is_favorite=True  # All items in this list are favorites
                )
                
                articles.append(article_item)
            
            return ArticleSearchResponse(
                items=articles,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
            
        except Exception as e:
            logger.error(f"Error getting favorite articles: {e}")
            raise

    async def _add_article_topics(self, article_id: UUID, topic_ids: List[int]):
        """Add topics to article"""
        if not topic_ids:
            return
            
        values = [(article_id, topic_id) for topic_id in topic_ids]
        query = "INSERT INTO article_topics (article_id, topic_id) VALUES ($1, $2) ON CONFLICT DO NOTHING"
        
        for article_id_val, topic_id in values:
            await self.db.execute_query(query, article_id_val, topic_id)

    async def _add_article_tags(self, article_id: UUID, tag_names: List[str]):
        """Add tags to article"""
        if not tag_names:
            return
            
        for tag_name in tag_names:
            tag_slug = slugify(tag_name)
            
            # Insert or get tag
            tag_query = """
            INSERT INTO tags (name, slug) 
            VALUES ($1, $2) 
            ON CONFLICT (slug) DO UPDATE SET usage_count = tags.usage_count + 1
            RETURNING id
            """
            
            tag_row = await self.db.fetch_one(tag_query, tag_name, tag_slug)
            if tag_row:
                # Link to article
                link_query = """
                INSERT INTO article_tags (article_id, tag_id) 
                VALUES ($1, $2) 
                ON CONFLICT DO NOTHING
                """
                await self.db.execute_query(link_query, article_id, tag_row['id'])

    async def _replace_article_topics(self, article_id: UUID, topic_ids: List[int]):
        """Replace all topics for article"""
        # Remove existing
        await self.db.execute_query("DELETE FROM article_topics WHERE article_id = $1", article_id)
        
        # Add new
        await self._add_article_topics(article_id, topic_ids)

    async def _replace_article_tags(self, article_id: UUID, tag_names: List[str]):
        """Replace all tags for article"""
        # Remove existing
        await self.db.execute_query("DELETE FROM article_tags WHERE article_id = $1", article_id)
        
        # Add new  
        await self._add_article_tags(article_id, tag_names)
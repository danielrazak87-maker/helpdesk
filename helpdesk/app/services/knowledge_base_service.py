from __future__ import annotations
from app.models.knowledge_base import KnowledgeBaseArticle, KnowledgeBaseCategory
from app import db
import re, unicodedata
from datetime import datetime

def generate_slug(text: str) -> str:
    """Slugify text: lowercase, replace spaces with hyphens, remove non-alphanumeric"""
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    # Replace non-alphanumeric with hyphens
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text[:220]  # Max slug length

def search_articles(query: str, category_id: int = None):
    """Case-insensitive search in title and content"""
    if not query:
        return []
    q = KnowledgeBaseArticle.query.filter(
        KnowledgeBaseArticle.is_published == True,
        (KnowledgeBaseArticle.title.ilike(f'%{query}%')) | (KnowledgeBaseArticle.content.ilike(f'%{query}%'))
    )
    if category_id:
        q = q.filter_by(category_id=category_id)
    return q.order_by(KnowledgeBaseArticle.created_at.desc()).all()

def get_article_by_slug(slug: str):
    """Return article or None"""
    return KnowledgeBaseArticle.query.filter_by(slug=slug).first()

def increment_view_count(article: KnowledgeBaseArticle):
    """Increment view count"""
    article.view_count += 1
    db.session.commit()

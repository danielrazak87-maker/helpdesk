from __future__ import annotations
from app import db, utcnow
import re, unicodedata
from datetime import datetime

class KnowledgeBaseCategory(db.Model):
    __tablename__ = 'kb_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)
    parent_id = db.Column(db.Integer, db.ForeignKey('kb_categories.id'))
    created_at = db.Column(db.DateTime, default=utcnow)
    children = db.relationship('KnowledgeBaseCategory', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

class KnowledgeBaseArticle(db.Model):
    __tablename__ = 'kb_articles'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('kb_categories.id'))
    tags = db.Column(db.String(500))
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_published = db.Column(db.Boolean, default=True)
    is_internal = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    category = db.relationship('KnowledgeBaseCategory', backref='articles')
    author = db.relationship('User', foreign_keys=[author_id])

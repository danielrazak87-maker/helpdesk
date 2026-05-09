from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.knowledge_base import KnowledgeBaseArticle, KnowledgeBaseCategory
from app.models.user import User
from app.services.knowledge_base_service import generate_slug, search_articles, get_article_by_slug, increment_view_count

kb_bp = Blueprint('kb', __name__, url_prefix='/kb')

def admin_or_engineer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_user():
            abort(403)
        return f(*args, **kwargs)
    return decorated

# Public Routes
@kb_bp.route('/')
def list_articles():
    categories = KnowledgeBaseCategory.query.order_by(KnowledgeBaseCategory.sort_order.asc()).all()
    articles_by_category = {}
    for cat in categories:
        articles = KnowledgeBaseArticle.query.filter_by(
            category_id=cat.id, 
            is_published=True,
            is_internal=False
        ).order_by(KnowledgeBaseArticle.created_at.desc()).all()
        if articles:
            articles_by_category[cat] = articles
    return render_template('kb/list.html', categories=categories, articles_by_category=articles_by_category)

@kb_bp.route('/<slug>')
def view_article(slug):
    article = get_article_by_slug(slug)
    if not article:
        abort(404)
    if not article.is_published or (article.is_internal and current_user.is_user()):
        abort(403)
    increment_view_count(article)
    categories = KnowledgeBaseCategory.query.order_by(KnowledgeBaseCategory.sort_order.asc()).all()
    return render_template('kb/view.html', article=article, categories=categories)

@kb_bp.route('/search')
def search_articles_route():
    query = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', type=int)
    results = search_articles(query, category_id) if query else []
    return render_template('kb/list.html', 
                          search_query=query, 
                          search_results=results, 
                          categories=KnowledgeBaseCategory.query.order_by(KnowledgeBaseCategory.sort_order.asc()).all())

@kb_bp.route('/category/<slug>')
def category_articles(slug):
    category = KnowledgeBaseCategory.query.filter_by(slug=slug).first_or_404()
    articles = KnowledgeBaseArticle.query.filter_by(
        category_id=category.id,
        is_published=True
    ).order_by(KnowledgeBaseArticle.created_at.desc()).all()
    return render_template('kb/list.html', 
                          current_category=category, 
                          category_articles=articles,
                          categories=KnowledgeBaseCategory.query.order_by(KnowledgeBaseCategory.sort_order.asc()).all())

# Admin/Engineer Routes
@kb_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_or_engineer_required
def create_article():
    categories = KnowledgeBaseCategory.query.order_by(KnowledgeBaseCategory.sort_order.asc()).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category_id = request.form.get('category_id', type=int)
        tags = request.form.get('tags', '').strip()
        is_published = request.form.get('is_published') == 'on'
        is_internal = request.form.get('is_internal') == 'on'

        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('kb/form.html', categories=categories)

        slug = generate_slug(title)
        # Ensure unique slug
        counter = 1
        while KnowledgeBaseArticle.query.filter_by(slug=slug).first():
            slug = f"{generate_slug(title)}-{counter}"
            counter += 1

        article = KnowledgeBaseArticle(
            title=title,
            slug=slug,
            content=content,
            category_id=category_id,
            tags=tags,
            author_id=current_user.id,
            is_published=is_published,
            is_internal=is_internal
        )
        db.session.add(article)
        db.session.commit()
        flash('Article created successfully.', 'success')
        return redirect(url_for('kb.view_article', slug=article.slug))
    return render_template('kb/form.html', categories=categories)

@kb_bp.route('/<int:article_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_or_engineer_required
def edit_article(article_id):
    article = KnowledgeBaseArticle.query.get_or_404(article_id)
    categories = KnowledgeBaseCategory.query.order_by(KnowledgeBaseCategory.sort_order.asc()).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category_id = request.form.get('category_id', type=int)
        tags = request.form.get('tags', '').strip()
        is_published = request.form.get('is_published') == 'on'
        is_internal = request.form.get('is_internal') == 'on'

        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('kb/form.html', article=article, categories=categories)

        # Update slug only if title changed
        if title != article.title:
            new_slug = generate_slug(title)
            counter = 1
            while KnowledgeBaseArticle.query.filter(KnowledgeBaseArticle.slug == new_slug, KnowledgeBaseArticle.id != article.id).first():
                new_slug = f"{generate_slug(title)}-{counter}"
                counter += 1
            article.slug = new_slug

        article.title = title
        article.content = content
        article.category_id = category_id
        article.tags = tags
        article.is_published = is_published
        article.is_internal = is_internal
        db.session.commit()
        flash('Article updated successfully.', 'success')
        return redirect(url_for('kb.view_article', slug=article.slug))
    return render_template('kb/form.html', article=article, categories=categories)

@kb_bp.route('/<int:article_id>/delete', methods=['POST'])
@login_required
def delete_article(article_id):
    article = KnowledgeBaseArticle.query.get_or_404(article_id)
    if not current_user.is_admin() and article.author_id != current_user.id:
        abort(403)
    db.session.delete(article)
    db.session.commit()
    flash('Article deleted successfully.', 'success')
    return redirect(url_for('kb.list_articles'))

@kb_bp.route('/admin')
@login_required
@admin_or_engineer_required
def admin_list():
    search_query = request.args.get('q', '').strip()
    query = KnowledgeBaseArticle.query
    if search_query:
        query = query.filter(
            (KnowledgeBaseArticle.title.ilike(f'%{search_query}%')) |
            (KnowledgeBaseArticle.content.ilike(f'%{search_query}%'))
        )
    articles = query.order_by(KnowledgeBaseArticle.created_at.desc()).all()
    return render_template('kb/admin_list.html', articles=articles, search_query=search_query)

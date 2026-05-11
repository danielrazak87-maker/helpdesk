from __future__ import annotations

from datetime import datetime, timezone
from flask import Flask, session, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.config import Config
import logging
import sys
from typing import Optional

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    """Return a naive datetime representing the current time in UTC.
    Replacement for deprecated datetime.utcnow().
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_app() -> Flask:
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    limiter.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Security headers
    @app.after_request
    def add_security_headers(response):
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
        response.headers['Content-Security-Policy'] = csp
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Custom Jinja2 filters
    import json
    @app.template_filter('fromjson')
    def fromjson_filter(value):
        try:
            return json.loads(value) if value else []
        except:
            return []

    from app.routes.auth import auth_bp
    from app.routes.tickets import tickets_bp
    from app.routes.admin import admin_bp
    from app.routes.engineer import engineer_bp
    from app.routes.reports import reports_bp
    from app.routes.main import main_bp
    # Phase 5 imports
    from app.routes.knowledge_base import kb_bp
    from app.routes.api import api_bp, simple_api_bp
    from app.routes.time_tracking import time_bp
    from app.routes.custom_fields import cf_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(engineer_bp, url_prefix='/engineer')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(main_bp)
    # Phase 5 registrations
    app.register_blueprint(kb_bp)
    app.register_blueprint(api_bp)
    csrf.exempt(api_bp)
    app.register_blueprint(simple_api_bp)
    csrf.exempt(simple_api_bp)  # API-key auth, no CSRF needed
    app.register_blueprint(time_bp)
    app.register_blueprint(cf_bp)

    from app.scheduler.jobs import start_scheduler
    start_scheduler(app)

    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    with app.app_context():
        # ── SAFEGUARD: Never use db.create_all() on startup ──────────────
        # db.create_all() silently recreates empty tables if they were dropped,
        # masking catastrophic data loss. Use "flask db upgrade" for migrations.
        #
        # Startup safety check: if the database exists but critical tables are
        # missing, abort with a clear error instead of silently recreating them.
        _check_database_integrity(app)
        _run_migrations_if_needed(app)
        _seed_defaults(app)

    # Register error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app


def _check_database_integrity(app: Flask) -> None:
    """Verify critical tables exist before allowing the app to start.

    If tables were dropped (manual action, migration error, etc.), abort
    immediately instead of silently recreating empty tables via create_all().
    """
    from sqlalchemy import inspect, text

    # In Flask-SQLAlchemy 3.x, engines are lazily bound. Use direct inspection.
    try:
        engine = db.session.get_bind()
    except Exception:
        # Fallback: use SQLAlchemy directly
        from sqlalchemy import create_engine
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # No tables at all → first run, allow migration to create them
    if not existing_tables:
        logger.info("No tables found — first-run database initialisation expected. "
                    "Run 'flask db upgrade' if migrations are available.")
        return

    # At least one table exists — check that critical tables are present
    critical_tables = {'users', 'tickets'}
    missing = critical_tables - set(existing_tables)

    if missing:
        msg = (
            f"\n{'='*70}\n"
            f"CRITICAL: Database integrity check FAILED on startup!\n"
            f"Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'unknown')}\n"
            f"Existing tables ({len(existing_tables)}): {sorted(existing_tables)}\n"
            f"Missing tables: {sorted(missing)}\n"
            f"\n"
            f"This means critical tables were DROPPED from the database.\n"
            f"The application will NOT start to prevent silent data loss.\n"
            f"\n"
            f"RECOVERY STEPS:\n"
            f"  1. Restore from backup: pg_restore -d helpdesk_db <backup.dump>\n"
            f"  2. Then run: flask db upgrade\n"
            f"  3. Then restart the service: systemctl restart helpdesk\n"
            f"{'='*70}\n"
        )
        logger.critical(msg)
        print(msg, file=sys.stderr)
        sys.exit(1)

    # Tables exist — check row counts to detect empty-recreated tables
    try:
        with engine.connect() as conn:
            user_count = conn.execute(text("SELECT count(*) FROM users")).scalar()
            ticket_count = conn.execute(text("SELECT count(*) FROM tickets")).scalar()

        if user_count == 0 and ticket_count == 0:
            # Possibly a first run with fresh tables from migrations
            logger.info("Database tables exist but are empty — assuming first run. "
                        "Seed data will be populated.")
        else:
            logger.info(f"Database integrity OK: {user_count} users, {ticket_count} tickets, "
                        f"{len(existing_tables)} tables.")
    except Exception as e:
        logger.warning(f"Could not verify row counts (non-fatal): {e}")


def _run_migrations_if_needed(app: Flask) -> None:
    """Handle database initialisation on startup.

    SAFEGUARD: db.create_all() is ONLY called when the database is completely
    empty (zero tables). This is the true first-run case. Once tables exist,
    create_all() is NEVER called again — even on restart, even on crash.

    For schema changes, use "flask db migrate && flask db upgrade" manually.
    This prevents silent table recreation after data loss.
    """
    from sqlalchemy import inspect

    engine = db.session.get_bind()
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Only on TRUE first run (zero tables): create the initial schema.
    # This runs EXACTLY once per database lifetime.
    if not existing_tables:
        logger.info("Empty database detected — performing first-run initialisation.")
        _first_run_setup(app)
        return

    # Tables exist — check migration status (read-only, never auto-upgrade)
    _check_migration_status(app, engine)


def _first_run_setup(app: Flask) -> None:
    """Create the full database schema on first run using db.create_all().

    This is the ONLY place create_all() is called. It runs exactly once per
    database lifetime (when zero tables exist). After tables exist, subsequent
    restarts skip this entirely and use the integrity check instead.
    """
    from app.models.user import User
    from app.models.knowledge_base import KnowledgeBaseArticle, KnowledgeBaseCategory
    from app.models.time_tracking import TimeEntry
    from app.models.custom_field import CustomField, CustomFieldValue
    from app.models.api_token import ApiToken

    db.create_all()
    logger.info("Base tables created via db.create_all() (first-run only).")

    # Stamp the migration version so Alembic knows where we are.
    _stamp_migration_head(app)


def _stamp_migration_head(app: Flask) -> None:
    """Stamp the database with the latest migration revision."""
    import os as _os
    migrations_dir = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), '..', 'migrations'
    )
    alembic_ini = _os.path.join(migrations_dir, 'alembic.ini')

    if not _os.path.exists(alembic_ini):
        logger.warning("alembic.ini not found — skipping migration stamp.")
        return

    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command

        alembic_cfg = AlembicConfig(alembic_ini)
        alembic_cfg.set_main_option('script_location', migrations_dir)
        alembic_cfg.set_main_option(
            'sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI']
        )
        command.stamp(alembic_cfg, 'head')
        logger.info("Migration version stamped to head.")
    except Exception as e:
        logger.warning("Could not stamp migration version (non-fatal): %s", e)


def _check_migration_status(app: Flask, engine) -> None:
    """Check if database migrations are up-to-date (read-only, no auto-upgrade)."""
    import os as _os
    migrations_dir = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), '..', 'migrations'
    )
    alembic_ini = _os.path.join(migrations_dir, 'alembic.ini')

    if not _os.path.exists(alembic_ini):
        logger.warning("alembic.ini not found at %s — skipping migration check.", alembic_ini)
        return

    try:
        from alembic.config import Config as AlembicConfig
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

        alembic_cfg = AlembicConfig(alembic_ini)
        alembic_cfg.set_main_option('script_location', migrations_dir)
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()

        if current_rev != head_rev:
            logger.warning(
                "Database migration version (%s) does not match head (%s). "
                "Run 'flask db upgrade' manually to apply pending migrations.",
                current_rev, head_rev
            )
        else:
            logger.info("Database migrations are up-to-date (revision %s).", current_rev)
    except Exception as e:
        logger.warning("Could not check migration status (non-fatal): %s", e)


def _seed_defaults(app: Flask) -> None:
    """Create default admin, SLA policies, and escalation rules if DB is empty."""
    admin_password = app.config.get('ADMIN_PASSWORD')
    if not admin_password:
        logger.warning("ADMIN_PASSWORD not set in environment — skipping admin seed."
                       " Set ADMIN_PASSWORD in .env for first-run seeding.")
        _seed_sla_policies()
        _seed_kb_categories()
        return

    from app.models.user import User
    from app.models.sla import SLAPolicy
    from werkzeug.security import generate_password_hash

    if not User.query.filter_by(role='admin').first():
        admin = User(
            email=app.config['ADMIN_EMAIL'],
            full_name='System Administrator',
            role='admin',
            is_active=True,
            password_hash=generate_password_hash(admin_password)
        )
        db.session.add(admin)
        db.session.commit()

    _seed_sla_policies()
    _seed_kb_categories()


def _seed_sla_policies() -> None:
    """Seed default SLA policies if table is empty."""
    from app.models.sla import SLAPolicy
    if not SLAPolicy.query.first():
        policies = [
            SLAPolicy(name='Critical SLA',  priority='critical', response_time_mins=15,  resolution_time_mins=60,   escalate_on_breach=True),
            SLAPolicy(name='High SLA',      priority='high',     response_time_mins=60,  resolution_time_mins=240,  escalate_on_breach=True),
            SLAPolicy(name='Medium SLA',    priority='medium',   response_time_mins=240, resolution_time_mins=480,  escalate_on_breach=True),
            SLAPolicy(name='Low SLA',       priority='low',      response_time_mins=480, resolution_time_mins=1440, escalate_on_breach=False),
        ]
        for p in policies:
            db.session.add(p)
        db.session.commit()


def _seed_kb_categories() -> None:
    """Seed default KB categories if table is empty."""
    from app.models.knowledge_base import KnowledgeBaseCategory
    if not KnowledgeBaseCategory.query.first():
        categories = [
            KnowledgeBaseCategory(name='Getting Started', slug='getting-started', description='Setup guides and onboarding', sort_order=1),
            KnowledgeBaseCategory(name='Troubleshooting', slug='troubleshooting', description='Common issues and solutions', sort_order=2),
            KnowledgeBaseCategory(name='Network', slug='network', description='Network configuration and issues', sort_order=3),
            KnowledgeBaseCategory(name='Hardware', slug='hardware', description='Hardware setup and repairs', sort_order=4),
            KnowledgeBaseCategory(name='Software', slug='software', description='Software installation and usage', sort_order=5),
            KnowledgeBaseCategory(name='Security', slug='security', description='Security best practices and policies', sort_order=6),
        ]
        for cat in categories:
            db.session.add(cat)
        db.session.commit()

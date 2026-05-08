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

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # Initialize rate limiter
    limiter.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Security headers
    @app.after_request
    def add_security_headers(response):
        csp = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
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

    from app.routes.auth import auth_bp
    from app.routes.tickets import tickets_bp
    from app.routes.admin import admin_bp
    from app.routes.engineer import engineer_bp
    from app.routes.reports import reports_bp
    from app.routes.main import main_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(engineer_bp, url_prefix='/engineer')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(main_bp)

    from app.scheduler.jobs import start_scheduler
    start_scheduler(app)

    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    with app.app_context():
        from app.models.user import User
        db.create_all()
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


def _seed_defaults(app):
    """Create default admin, SLA policies, and escalation rules if DB is empty."""
    admin_password = app.config.get('ADMIN_PASSWORD')
    if not admin_password:
        logger.warning("ADMIN_PASSWORD not set in environment — skipping admin seed."
                       " Set ADMIN_PASSWORD in .env for first-run seeding.")
        # Still seed SLA policies if empty
        _seed_sla_policies()
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


def _seed_sla_policies():
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

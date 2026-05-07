from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from app.config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

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

    return app


def _seed_defaults(app):
    """Create default admin, SLA policies, and escalation rules if DB is empty."""
    from app.models.user import User
    from app.models.sla import SLAPolicy
    from werkzeug.security import generate_password_hash

    if not User.query.filter_by(role='admin').first():
        admin = User(
            email=app.config['ADMIN_EMAIL'],
            full_name='System Administrator',
            role='admin',
            is_active=True,
            password_hash=generate_password_hash(app.config['ADMIN_PASSWORD'])
        )
        db.session.add(admin)
        db.session.commit()

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

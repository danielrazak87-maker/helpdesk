"""
pytest configuration and shared fixtures for the Helpdesk test suite.
"""
from __future__ import annotations

import os
import sys
import tempfile
import pytest
from datetime import datetime, timezone
from typing import Generator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

# Ensure the app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope='session')
def app():
    """Create a Flask app instance configured for testing."""
    # Override config BEFORE any imports so config.py's load_dotenv doesn't override us
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-pytest'
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['WTF_CSRF_ENABLED'] = 'False'
    os.environ['ADMIN_PASSWORD'] = ''  # prevent seed from creating admin user
    os.environ['MAIL_USERNAME'] = ''   # prevent mail from being configured
    os.environ['RATELIMIT_ENABLED'] = 'False'

    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'test.local'
    app.config['RATELIMIT_ENABLED'] = False

    with app.app_context():
        from app import db
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def client(app):
    """Test client for the app."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """Click test runner."""
    return app.test_cli_runner()


@pytest.fixture(autouse=True)
def _push_context(app):
    """Ensure app context is active for every test."""
    ctx = app.app_context()
    ctx.push()
    yield
    ctx.pop()


@pytest.fixture()
def db_session(app):
    """Provide a database session for test data setup."""
    from app import db
    return db.session


def _get_or_create_user(db_session, email, full_name, role, password, project=None):
    """Get existing user by email or create a new one (idempotent)."""
    from app.models.user import User
    user = User.query.filter_by(email=email).first()
    if user:
        return user
    user = User(
        email=email,
        full_name=full_name,
        role=role,
        project=project,
        is_active=True
    )
    user.set_password(password)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def admin_user(app, db_session):
    """Create and return an admin user (idempotent)."""
    return _get_or_create_user(db_session, 'admin@test.com', 'Test Admin', 'admin', 'Admin@1234')


@pytest.fixture()
def engineer_user(app, db_session):
    """Create and return an engineer user (idempotent)."""
    return _get_or_create_user(db_session, 'engineer@test.com', 'Test Engineer', 'engineer', 'Engineer@1234')


@pytest.fixture()
def regular_user(app, db_session):
    """Create and return a regular (end-user) user (idempotent)."""
    return _get_or_create_user(db_session, 'user@test.com', 'Test User', 'user', 'User@1234', project='Test Project')


@pytest.fixture()
def sample_ticket(app, db_session, regular_user, engineer_user):
    """Create and return a sample ticket (idempotent)."""
    from app.models.ticket import Ticket
    from datetime import datetime

    ticket = Ticket.query.filter_by(ticket_number='HD-TEST-0001').first()
    if ticket:
        return ticket

    ticket = Ticket(
        ticket_number='HD-TEST-0001',
        title='Test Ticket',
        description='A test ticket description',
        status='open',
        priority='high',
        category='network',
        project='Test Project',
        created_by=regular_user.id,
        assigned_to=engineer_user.id,
        created_at=_utcnow(),
        updated_at=_utcnow()
    )
    db_session.add(ticket)
    db_session.commit()
    return ticket


@pytest.fixture()
def sample_sla(app, db_session):
    """Create and return a sample SLA policy (idempotent)."""
    from app.models.sla import SLAPolicy
    sla = SLAPolicy.query.filter_by(name='Test SLA').first()
    if sla:
        return sla
    sla = SLAPolicy(
        name='Test SLA',
        priority='high',
        response_time_mins=60,
        resolution_time_mins=240,
        escalate_on_breach=True
    )
    db_session.add(sla)
    db_session.commit()
    return sla


def login(client, email: str, password: str) -> None:
    """Helper to log a test user in."""
    client.post('/auth/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)


def logout(client) -> None:
    """Helper to log out."""
    client.get('/auth/logout', follow_redirects=True)


@pytest.fixture(autouse=True)
def _reset_limiter(app):
    """Reset the rate limiter before every test to avoid 429 cascades."""
    from app import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
    except Exception:
        pass

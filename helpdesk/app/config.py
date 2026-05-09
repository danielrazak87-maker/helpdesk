import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _required(key: str, hint: str) -> str:
    """Get a required env var or exit with a clear error."""
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} is required but not set in environment.", file=sys.stderr)
        print(f"  Hint: {hint}", file=sys.stderr)
        sys.exit(1)
    return val


def _validate_port(val: str, name: str) -> int:
    try:
        port = int(val)
        if not 1 <= port <= 65535:
            raise ValueError
        return port
    except (ValueError, TypeError):
        print(f"ERROR: {name} must be a valid port number (1-65535), got '{val}'.", file=sys.stderr)
        sys.exit(1)


def _validate_bool(val: str, name: str) -> bool:
    if val.lower() in ('true', '1', 'yes'):
        return True
    if val.lower() in ('false', '0', 'no'):
        return False
    print(f"ERROR: {name} must be 'true' or 'false', got '{val}'.", file=sys.stderr)
    sys.exit(1)


class Config:
    # ─── Required ────────────────────────────────────────────────────────────
    SECRET_KEY: str = _required(
        'SECRET_KEY',
        "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
    )

    DATABASE_URL_RAW: str = _required(
        'DATABASE_URL',
        "Example: sqlite:///helpdesk.db or postgresql+pg8000://user:pass@localhost:5432/helpdesk_db"
    )
    SQLALCHEMY_DATABASE_URI: str = DATABASE_URL_RAW
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # ─── Mail (optional — validated if MAIL_USERNAME is set) ────────────────
    MAIL_SERVER: str = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT: int = _validate_port(os.environ.get('MAIL_PORT', '587'), 'MAIL_PORT')
    MAIL_USE_TLS: bool = _validate_bool(os.environ.get('MAIL_USE_TLS', 'True'), 'MAIL_USE_TLS')
    MAIL_USERNAME: str | None = os.environ.get('MAIL_USERNAME') or None
    MAIL_PASSWORD: str | None = os.environ.get('MAIL_PASSWORD') or None
    MAIL_DEFAULT_SENDER: str = os.environ.get('MAIL_DEFAULT_SENDER', 'Helpdesk <noreply@helpdesk.com>')

    # Validate mail config if SMTP is configured
    if MAIL_USERNAME and not MAIL_PASSWORD:
        print("WARNING: MAIL_USERNAME is set but MAIL_PASSWORD is missing — email sending will be disabled.", file=sys.stderr)

    # ─── Uploads ────────────────────────────────────────────────────────────
    UPLOAD_FOLDER: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'uploads')
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # 10MB

    # ─── Admin seed (ADMIN_PASSWORD required if no admin user exists at first run) ──
    ADMIN_EMAIL: str = os.environ.get('ADMIN_EMAIL', 'admin@helpdesk.com')
    ADMIN_PASSWORD: str | None = os.environ.get('ADMIN_PASSWORD') or None

    # ─── Session ────────────────────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    FLASK_ENV: str = os.environ.get('FLASK_ENV', 'development')
    SESSION_COOKIE_SECURE: bool = os.environ.get('SESSION_COOKIE_SECURE', str(FLASK_ENV == 'production')).lower() == 'true'

    if FLASK_ENV not in ('development', 'production', 'testing'):
        print(f"WARNING: FLASK_ENV='{FLASK_ENV}' is unusual. Expected 'development', 'production', or 'testing'.", file=sys.stderr)

    # ─── Rate limiting ──────────────────────────────────────────────────────
    RATELIMIT_ENABLED: bool = os.environ.get('RATELIMIT_ENABLED', 'True').lower() in ('true', '1', 'yes')
    RATELIMIT_DEFAULT: str = os.environ.get('RATELIMIT_DEFAULT', '100/minute')
    RATELIMIT_STORAGE_URL: str = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')

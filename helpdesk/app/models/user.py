from __future__ import annotations

from app import db, login_manager, utcnow
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from typing import Optional
import json
import pyotp


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id: int = db.Column(db.Integer, primary_key=True)
    email: str = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash: str = db.Column(db.String(256), nullable=False)
    full_name: str = db.Column(db.String(150), nullable=False)
    role: str = db.Column(db.String(20), nullable=False, default='user')  # admin, engineer, user
    department: Optional[str] = db.Column(db.String(100))
    client_id: Optional[int] = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    project: Optional[str] = db.Column(db.String(100))
    phone: Optional[str] = db.Column(db.String(30))
    avatar: Optional[str] = db.Column(db.String(200))
    is_active: bool = db.Column(db.Boolean, default=True)
    created_at: Optional[datetime] = db.Column(db.DateTime, default=utcnow)
    last_login: Optional[datetime] = db.Column(db.DateTime)
    password_updated_at: Optional[datetime] = db.Column(db.DateTime)

    # 2FA fields
    totp_secret: Optional[str] = db.Column(db.String(32))
    is_2fa_enabled: bool = db.Column(db.Boolean, default=False)
    backup_codes: Optional[str] = db.Column(db.Text)  # JSON array of hashed backup codes

    # Relationships
    created_tickets = db.relationship('Ticket', foreign_keys='Ticket.created_by', backref='creator', lazy='dynamic')
    assigned_tickets = db.relationship('Ticket', foreign_keys='Ticket.assigned_to', backref='assignee', lazy='dynamic')
    comments = db.relationship('TicketComment', backref='author', lazy='dynamic')
    attendance_records = db.relationship('Attendance', backref='engineer', lazy='dynamic')
    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        self.password_updated_at = utcnow()

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        return self.role == 'admin'

    def is_engineer(self) -> bool:
        return self.role == 'engineer'

    def is_user(self) -> bool:
        return self.role == 'user'

    def unread_notification_count(self) -> int:
        return self.notifications.filter_by(is_read=False).count()

    def recent_notifications(self, limit: int = 8):
        from app.models.notification import Notification
        return self.notifications.order_by(Notification.created_at.desc()).limit(limit).all()

    # ── 2FA Methods ────────────────────────────────────────────────────────

    def generate_totp_secret(self) -> str:
        """Generate a new TOTP secret and save it."""
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret

    def get_otp_uri(self) -> str:
        """Return the otpauth URI for QR code generation."""
        if not self.totp_secret:
            self.totp_secret = pyotp.random_base32()
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email,
            issuer_name='Kayfalah Helpdesk'
        )

    def verify_totp(self, code: str) -> bool:
        """Verify a TOTP code against the stored secret."""
        if not self.totp_secret:
            return False
        return pyotp.totp.TOTP(self.totp_secret).verify(code.strip())

    def generate_backup_codes(self, count: int = 8) -> list:
        """Generate and store hashed backup codes. Returns plaintext codes (shown once)."""
        import secrets
        plain_codes = []
        hashed = []
        for _ in range(count):
            code = f"{secrets.randbelow(10000):04d}-{secrets.randbelow(10000):04d}"
            plain_codes.append(code)
            hashed.append(generate_password_hash(code))
        self.backup_codes = json.dumps(hashed)
        return plain_codes

    def verify_backup_code(self, code: str) -> bool:
        """Verify and consume a backup code. Returns True if valid."""
        if not self.backup_codes:
            return False
        try:
            codes = json.loads(self.backup_codes)
        except (json.JSONDecodeError, TypeError):
            return False
        for i, hashed in enumerate(codes):
            if check_password_hash(hashed, code.strip()):
                codes.pop(i)
                self.backup_codes = json.dumps(codes)
                db.session.commit()
                return True
        return False

    def disable_2fa(self) -> None:
        """Disable 2FA and clear secrets."""
        self.totp_secret = None
        self.is_2fa_enabled = False
        self.backup_codes = None

    def __repr__(self) -> str:
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    return db.session.get(User, int(user_id))
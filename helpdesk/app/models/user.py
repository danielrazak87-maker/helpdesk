from __future__ import annotations

from app import db, login_manager, utcnow
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from typing import Optional


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id: int = db.Column(db.Integer, primary_key=True)
    email: str = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash: str = db.Column(db.String(256), nullable=False)
    full_name: str = db.Column(db.String(150), nullable=False)
    role: str = db.Column(db.String(20), nullable=False, default='user')  # admin, engineer, user
    department: Optional[str] = db.Column(db.String(100))
    project: Optional[str] = db.Column(db.String(100))
    phone: Optional[str] = db.Column(db.String(30))
    avatar: Optional[str] = db.Column(db.String(200))
    is_active: bool = db.Column(db.Boolean, default=True)
    created_at: Optional[datetime] = db.Column(db.DateTime, default=utcnow)
    last_login: Optional[datetime] = db.Column(db.DateTime)
    password_updated_at: Optional[datetime] = db.Column(db.DateTime)

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

    def __repr__(self) -> str:
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    return db.session.get(User, int(user_id))

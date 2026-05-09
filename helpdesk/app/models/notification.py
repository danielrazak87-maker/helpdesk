from __future__ import annotations

from app import db, utcnow
from datetime import datetime
from typing import Optional


class Notification(db.Model):
    __tablename__ = 'notifications'

    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ticket_id: Optional[int] = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=True)
    title: str = db.Column(db.String(200), nullable=False)
    message: str = db.Column(db.Text, nullable=False)
    type: str = db.Column(db.String(30), default='info')  # info, warning, danger, success
    is_read: bool = db.Column(db.Boolean, default=False)
    created_at: Optional[datetime] = db.Column(db.DateTime, default=utcnow)

    ticket = db.relationship('Ticket', foreign_keys=[ticket_id])

    def __repr__(self) -> str:
        return f'<Notification User#{self.user_id}>'

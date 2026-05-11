from __future__ import annotations

from app import db, utcnow
from datetime import datetime
from typing import Optional


class Client(db.Model):
    __tablename__ = 'clients'

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(150), unique=True, nullable=False, index=True)
    description: Optional[str] = db.Column(db.Text)
    created_at: Optional[datetime] = db.Column(db.DateTime, default=utcnow)

    # SLA Policy fields (per-client SLA)
    response_time_hours: Optional[float] = db.Column(db.Numeric(6, 2), nullable=True)
    resolution_time_hours: Optional[float] = db.Column(db.Numeric(6, 2), nullable=True)
    sla1_time_hours: Optional[float] = db.Column(db.Numeric(6, 2), nullable=True)
    sla2_time_hours: Optional[float] = db.Column(db.Numeric(6, 2), nullable=True)
    sla3_time_hours: Optional[float] = db.Column(db.Numeric(6, 2), nullable=True)
    business_hours_only: bool = db.Column(db.Boolean, default=False)
    active_sla: bool = db.Column(db.Boolean, default=True)

    # Relationship
    users = db.relationship('User', backref='client', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Client {self.name}>'
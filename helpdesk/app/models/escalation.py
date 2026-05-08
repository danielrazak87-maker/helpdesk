from __future__ import annotations

from app import db, utcnow
from datetime import datetime
from typing import Optional


class EscalationRule(db.Model):
    __tablename__ = 'escalation_rules'

    id: int = db.Column(db.Integer, primary_key=True)
    sla_policy_id: int = db.Column(db.Integer, db.ForeignKey('sla_policies.id'), nullable=False)
    escalate_to: int = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    trigger_after_mins: int = db.Column(db.Integer, nullable=False)
    escalation_level: int = db.Column(db.Integer, default=1)  # 1, 2, 3
    created_at: Optional[datetime] = db.Column(db.DateTime, default=utcnow)

    escalation_target = db.relationship('User', foreign_keys=[escalate_to])

    def __repr__(self) -> str:
        return f'<EscalationRule Level {self.escalation_level}>'


class EscalationLog(db.Model):
    __tablename__ = 'escalation_logs'

    id: int = db.Column(db.Integer, primary_key=True)
    ticket_id: int = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    escalated_to: int = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    escalation_level: int = db.Column(db.Integer, nullable=False)
    reason: Optional[str] = db.Column(db.String(255))
    created_at: Optional[datetime] = db.Column(db.DateTime, default=utcnow)

    target_user = db.relationship('User', foreign_keys=[escalated_to])

    def __repr__(self) -> str:
        return f'<EscalationLog Ticket#{self.ticket_id} L{self.escalation_level}>'

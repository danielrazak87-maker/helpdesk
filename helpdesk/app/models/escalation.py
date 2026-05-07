from app import db
from datetime import datetime


class EscalationRule(db.Model):
    __tablename__ = 'escalation_rules'

    id = db.Column(db.Integer, primary_key=True)
    sla_policy_id = db.Column(db.Integer, db.ForeignKey('sla_policies.id'), nullable=False)
    escalate_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    trigger_after_mins = db.Column(db.Integer, nullable=False)
    escalation_level = db.Column(db.Integer, default=1)  # 1, 2, 3
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    escalation_target = db.relationship('User', foreign_keys=[escalate_to])

    def __repr__(self):
        return f'<EscalationRule Level {self.escalation_level}>'


class EscalationLog(db.Model):
    __tablename__ = 'escalation_logs'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    escalated_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    escalation_level = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    target_user = db.relationship('User', foreign_keys=[escalated_to])

    def __repr__(self):
        return f'<EscalationLog Ticket#{self.ticket_id} L{self.escalation_level}>'

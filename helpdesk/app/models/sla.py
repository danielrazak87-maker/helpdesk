from app import db, utcnow
from datetime import datetime


class SLAPolicy(db.Model):
    __tablename__ = 'sla_policies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.String(20), nullable=False)  # critical, high, medium, low
    response_time_mins = db.Column(db.Integer, nullable=False)
    resolution_time_mins = db.Column(db.Integer, nullable=False)
    escalate_on_breach = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    tickets = db.relationship('Ticket', backref='sla_policy', lazy='dynamic')
    escalation_rules = db.relationship('EscalationRule', backref='sla_policy', lazy='dynamic', cascade='all, delete-orphan')

    def response_hours(self):
        return round(self.response_time_mins / 60, 1)

    def resolution_hours(self):
        return round(self.resolution_time_mins / 60, 1)

    def __repr__(self):
        return f'<SLAPolicy {self.name}>'

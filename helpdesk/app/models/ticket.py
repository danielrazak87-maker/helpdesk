from app import db, utcnow
from datetime import datetime
import random
import string


TICKET_STATUSES = ['open', 'in_progress', 'pending', 'review', 'resolved', 'closed']
TICKET_PRIORITIES = ['critical', 'high', 'medium', 'low']
TICKET_CATEGORIES = ['network', 'hardware', 'software', 'security', 'account', 'other']


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open')
    priority = db.Column(db.String(20), nullable=False, default='medium')
    category = db.Column(db.String(50), default='other')
    project = db.Column(db.String(100))

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    original_assignee = db.Column(db.Integer, db.ForeignKey('users.id'))  # saved before review reassignment

    sla_policy_id = db.Column(db.Integer, db.ForeignKey('sla_policies.id'))
    sla_response_due = db.Column(db.DateTime)
    sla_resolution_due = db.Column(db.DateTime)
    sla_breached = db.Column(db.Boolean, default=False)
    sla_responded_at = db.Column(db.DateTime)
    sla_state = db.Column(db.String(20), default='on_track')  # on_track, at_risk, breached, resolved

    attachment = db.Column(db.String(300))
    rating = db.Column(db.Integer)  # 1-5 from user feedback
    feedback = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    comments = db.relationship('TicketComment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    escalation_logs = db.relationship('EscalationLog', backref='ticket', lazy='dynamic')

    @staticmethod
    def generate_ticket_number():
        date_str = utcnow().strftime('%Y%m%d')
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f'HD-{date_str}-{suffix}'

    def sla_status(self):
        """Returns: on_track, at_risk, breached, resolved — from persisted field."""
        if self.status in ['resolved', 'closed']:
            return 'resolved'
        if self.sla_breached:
            return 'breached'
        return self.sla_state or 'on_track'

    def sla_percent(self):
        if not self.sla_resolution_due:
            return 0
        now = utcnow()
        total = (self.sla_resolution_due - self.created_at).total_seconds()
        elapsed = (now - self.created_at).total_seconds()
        if total <= 0:
            return 100
        return min(100, round((elapsed / total) * 100))

    def sla_remaining_mins(self):
        if not self.sla_resolution_due:
            return None
        delta = self.sla_resolution_due - utcnow()
        return int(delta.total_seconds() / 60)

    def resolution_time_mins(self):
        if self.resolved_at:
            return int((self.resolved_at - self.created_at).total_seconds() / 60)
        return None

    def __repr__(self):
        return f'<Ticket {self.ticket_number}>'


class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)  # internal notes not visible to users
    created_at = db.Column(db.DateTime, default=utcnow)

    def __repr__(self):
        return f'<TicketComment Ticket#{self.ticket_id}>'


class TicketHistory(db.Model):
    __tablename__ = 'ticket_history'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    field_changed = db.Column(db.String(50))
    old_value = db.Column(db.String(200))
    new_value = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=utcnow)

    changer = db.relationship('User', foreign_keys=[changed_by])

    def __repr__(self):
        return f'<TicketHistory Ticket#{self.ticket_id} {self.field_changed}>'

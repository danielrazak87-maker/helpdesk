from datetime import datetime, timedelta, timezone
from app import db, utcnow
from app.models.ticket import Ticket
from app.models.sla import SLAPolicy


def assign_sla(ticket: Ticket):
    """Assign SLA policy and calculate due dates for a ticket."""
    policy = SLAPolicy.query.filter_by(priority=ticket.priority).first()
    if not policy:
        return

    ticket.sla_policy_id = policy.id
    ticket.sla_response_due = ticket.created_at + timedelta(minutes=policy.response_time_mins)
    ticket.sla_resolution_due = ticket.created_at + timedelta(minutes=policy.resolution_time_mins)
    db.session.commit()


def check_and_update_sla(ticket: Ticket):
    """Check if SLA is breached and mark accordingly."""
    if ticket.status in ['resolved', 'closed']:
        return False

    if ticket.sla_resolution_due and utcnow() > ticket.sla_resolution_due:
        if not ticket.sla_breached:
            ticket.sla_breached = True
            db.session.commit()
            return True  # just breached
    return False


def get_sla_dashboard_stats():
    """Return summary SLA stats for the dashboard."""
    total = Ticket.query.count()
    breached = Ticket.query.filter_by(sla_breached=True).count()
    resolved = Ticket.query.filter(Ticket.status.in_(['resolved', 'closed'])).count()

    breach_rate = round((breached / total * 100), 1) if total > 0 else 0
    return {
        'total': total,
        'breached': breached,
        'resolved': resolved,
        'breach_rate': breach_rate,
    }

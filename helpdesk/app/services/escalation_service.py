from datetime import datetime, timedelta
from app import db
from app.models.ticket import Ticket
from app.models.escalation import EscalationRule, EscalationLog
from app.models.notification import Notification


def run_escalation_checks():
    """Called by scheduler — check all open tickets for escalation triggers."""
    open_tickets = Ticket.query.filter(
        Ticket.status.notin_(['resolved', 'closed']),
        Ticket.sla_policy_id.isnot(None)
    ).all()

    for ticket in open_tickets:
        _check_ticket_escalation(ticket)


def _check_ticket_escalation(ticket: Ticket):
    """Evaluate escalation rules for a single ticket."""
    rules = EscalationRule.query.filter_by(
        sla_policy_id=ticket.sla_policy_id
    ).order_by(EscalationRule.escalation_level).all()

    elapsed_mins = int((datetime.utcnow() - ticket.created_at).total_seconds() / 60)

    for rule in rules:
        if elapsed_mins >= rule.trigger_after_mins:
            # Check if already escalated at this level
            already = EscalationLog.query.filter_by(
                ticket_id=ticket.id,
                escalation_level=rule.escalation_level
            ).first()
            if not already:
                _escalate(ticket, rule)


def _escalate(ticket: Ticket, rule: EscalationRule):
    """Create escalation log and send notification."""
    log = EscalationLog(
        ticket_id=ticket.id,
        escalated_to=rule.escalate_to,
        escalation_level=rule.escalation_level,
        reason=f'SLA threshold of {rule.trigger_after_mins} minutes exceeded.'
    )
    db.session.add(log)

    notif = Notification(
        user_id=rule.escalate_to,
        ticket_id=ticket.id,
        title=f'🚨 Escalation Level {rule.escalation_level}: {ticket.ticket_number}',
        message=(
            f'Ticket "{ticket.title}" has been escalated to you (Level {rule.escalation_level}). '
            f'It has been open for over {rule.trigger_after_mins} minutes.'
        ),
        type='danger'
    )
    db.session.add(notif)

    # Also notify assigned engineer
    if ticket.assigned_to:
        eng_notif = Notification(
            user_id=ticket.assigned_to,
            ticket_id=ticket.id,
            title=f'⚠️ Ticket {ticket.ticket_number} Escalated',
            message=f'Your ticket has been escalated to Level {rule.escalation_level} due to SLA breach.',
            type='warning'
        )
        db.session.add(eng_notif)

    db.session.commit()

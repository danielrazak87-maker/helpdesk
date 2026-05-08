from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from app import db, utcnow
from app.models.ticket import Ticket
from app.models.escalation import EscalationRule, EscalationLog
from app.models.notification import Notification


def run_escalation_checks() -> None:
    """Called by scheduler — check all open tickets for escalation triggers."""
    open_tickets: list[Ticket] = Ticket.query.filter(
        Ticket.status.notin_(['resolved', 'closed']),
        Ticket.sla_policy_id.isnot(None)
    ).all()

    for ticket in open_tickets:
        _check_ticket_escalation(ticket)


def _check_ticket_escalation(ticket: Ticket) -> None:
    """Evaluate escalation rules for a single ticket."""
    rules: list[EscalationRule] = EscalationRule.query.filter_by(
        sla_policy_id=ticket.sla_policy_id
    ).order_by(EscalationRule.escalation_level).all()

    elapsed_mins = int((utcnow() - ticket.created_at).total_seconds() / 60)

    for rule in rules:
        if elapsed_mins >= rule.trigger_after_mins:
            already: EscalationLog | None = EscalationLog.query.filter_by(
                ticket_id=ticket.id,
                escalation_level=rule.escalation_level
            ).first()
            if not already:
                _escalate(ticket, rule)


def _escalate(ticket: Ticket, rule: EscalationRule) -> None:
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

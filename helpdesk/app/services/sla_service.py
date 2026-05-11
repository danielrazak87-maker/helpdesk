from datetime import datetime, timedelta, timezone
from app import db, utcnow
from app.models.ticket import Ticket
from app.models.sla import SLAPolicy
from app.models.client import Client


def _get_client_sla(ticket: Ticket):
    """Get the client SLA policy for a ticket by looking up the creator's client.
    Returns (response_hours, resolution_hours, business_hours_only) or None.

    Applies SLA tier overrides based on ticket priority:
      SLA 1 → critical priority (overrides resolution_time_hours)
      SLA 2 → high priority (overrides resolution_time_hours)
      SLA 3 → medium/low priority (overrides resolution_time_hours)
    """
    if not ticket.creator or not ticket.creator.client_id:
        return None
    client = db.session.get(Client, ticket.creator.client_id)
    if not client or not client.active_sla:
        return None
    if not client.response_time_hours and not client.resolution_time_hours:
        return None

    resp_hours = client.response_time_hours
    res_hours = client.resolution_time_hours

    # Apply SLA tier overrides based on ticket priority
    sla_tier_map = {
        'critical': 'sla1_time_hours',
        'high': 'sla2_time_hours',
        'medium': 'sla3_time_hours',
        'low': 'sla3_time_hours',
    }
    if ticket.priority in sla_tier_map:
        tier_field = sla_tier_map[ticket.priority]
        tier_hours = getattr(client, tier_field, None)
        if tier_hours is not None:
            res_hours = float(tier_hours)

    if not resp_hours and not res_hours:
        return None
    return (resp_hours, res_hours, client.business_hours_only)


def calculate_deadline(created_at: datetime, hours: float, business_hours_only: bool = False) -> datetime:
    """Calculate SLA deadline from created_at + hours, optionally using business hours."""
    if not hours:
        return None
    total_minutes = int(hours * 60)
    if business_hours_only:
        from app.services.business_hours import add_business_minutes
        return add_business_minutes(created_at, total_minutes)
    return created_at + timedelta(minutes=total_minutes)


def assign_sla(ticket: Ticket):
    """Assign SLA policy and calculate due dates for a ticket.
    Priority: 1) Client SLA (per-client), 2) Priority-based SLA (global).
    """
    client_sla = _get_client_sla(ticket)
    if client_sla:
        resp_hours, res_hours, biz_only = client_sla
        if resp_hours:
            ticket.sla_response_due = calculate_deadline(ticket.created_at, resp_hours, biz_only)
        if res_hours:
            ticket.sla_resolution_due = calculate_deadline(ticket.created_at, res_hours, biz_only)
        # Don't set sla_policy_id — client SLA is 1:1, not the global priority table
        ticket.sla_policy_id = None
        ticket.sla_state = 'on_track'
        db.session.flush()
        return

    # Fallback: global priority-based SLA
    policy = SLAPolicy.query.filter_by(priority=ticket.priority).first()
    if not policy:
        return

    ticket.sla_policy_id = policy.id
    ticket.sla_response_due = ticket.created_at + timedelta(minutes=policy.response_time_mins)
    ticket.sla_resolution_due = ticket.created_at + timedelta(minutes=policy.resolution_time_mins)
    ticket.sla_state = 'on_track'
    db.session.flush()


def calculate_sla_status(ticket: Ticket) -> str:
    """Calculate current SLA status for a ticket. Returns: on_track, at_risk, breached, resolved."""
    if ticket.status in ['resolved', 'closed']:
        return 'resolved'

    if ticket.sla_breached:
        return 'breached'

    if not ticket.sla_resolution_due:
        return 'on_track'

    now = utcnow()
    if now >= ticket.sla_resolution_due:
        return 'breached'

    # Check if within 25% of deadline → at_risk
    total_window = (ticket.sla_resolution_due - ticket.created_at).total_seconds()
    elapsed = (now - ticket.created_at).total_seconds()
    if total_window > 0 and (elapsed / total_window) >= 0.75:
        return 'at_risk'

    return 'on_track'


def check_and_update_sla(ticket: Ticket):
    """Check if SLA is breached/at_risk and update persisted sla_status + sla_breached."""
    if ticket.status in ['resolved', 'closed']:
        ticket.sla_state = 'resolved'
        return False

    if not ticket.sla_resolution_due:
        return False

    now = utcnow()
    new_status = calculate_sla_status(ticket)

    if new_status == 'breached' and not ticket.sla_breached:
        ticket.sla_breached = True
        ticket.sla_state = 'breached'
        db.session.commit()
        return True  # just breached

    if ticket.sla_state != new_status:
        ticket.sla_state = new_status
        db.session.commit()

    return False


def update_all_sla_statuses():
    """Periodic job: recalculate sla_status for all active tickets."""
    active_tickets = Ticket.query.filter(
        Ticket.status.notin_(['resolved', 'closed'])
    ).all()

    updated = 0
    for ticket in active_tickets:
        new_status = calculate_sla_status(ticket)
        if new_status == 'breached' and not ticket.sla_breached:
            ticket.sla_breached = True
            ticket.sla_state = 'breached'
            updated += 1
        elif ticket.sla_state != new_status:
            ticket.sla_state = new_status
            updated += 1

    if updated:
        db.session.commit()
    return updated


def get_sla_dashboard_stats():
    """Return summary SLA stats for the dashboard including compliance."""
    total = Ticket.query.count()
    breached = Ticket.query.filter_by(sla_breached=True).count()
    resolved = Ticket.query.filter(Ticket.status.in_(['resolved', 'closed'])).count()
    at_risk = Ticket.query.filter(
        Ticket.sla_state == 'at_risk',
        Ticket.status.notin_(['resolved', 'closed'])
    ).count()
    active = Ticket.query.filter(
        Ticket.status.notin_(['resolved', 'closed'])
    ).count()

    # Compliance = (active - breached) / active * 100
    compliance = round(((active - breached) / active * 100), 1) if active > 0 else 100.0
    breach_rate = round((breached / total * 100), 1) if total > 0 else 0

    return {
        'total': total,
        'breached': breached,
        'resolved': resolved,
        'at_risk': at_risk,
        'active': active,
        'compliance': compliance,
        'breach_rate': breach_rate,
    }


def get_client_sla_performance():
    """Return SLA performance stats per client for reports."""
    clients = Client.query.all()
    results = []
    for client in clients:
        # Get tickets created by users of this client
        from app.models.user import User
        user_ids = [u.id for u in User.query.filter_by(client_id=client.id).all()]
        if not user_ids:
            continue

        total = Ticket.query.filter(Ticket.created_by.in_(user_ids)).count()
        breached = Ticket.query.filter(
            Ticket.created_by.in_(user_ids),
            Ticket.sla_breached == True
        ).count()
        resolved = Ticket.query.filter(
            Ticket.created_by.in_(user_ids),
            Ticket.status.in_(['resolved', 'closed'])
        ).count()

        active = Ticket.query.filter(
            Ticket.created_by.in_(user_ids),
            Ticket.status.notin_(['resolved', 'closed'])
        ).count()

        compliance = round(((active - breached) / active * 100), 1) if active > 0 else 100.0

        results.append({
            'client': client,
            'total': total,
            'breached': breached,
            'resolved': resolved,
            'compliance': compliance,
            'sla_active': client.active_sla,
            'response_hours': float(client.response_time_hours) if client.response_time_hours else None,
            'resolution_hours': float(client.resolution_time_hours) if client.resolution_time_hours else None,
        })

    # Sort by compliance (lowest first — worst performers)
    results.sort(key=lambda x: x['compliance'])
    return results


def get_monthly_sla_trend(months: int = 6):
    """Return monthly SLA compliance trend for reports."""
    from sqlalchemy import func, extract
    now = utcnow()
    results = []
    for i in range(months - 1, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 31)).replace(day=1)
        if i == 0:
            month_end = now
        else:
            # Last day of that month
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

        total = Ticket.query.filter(
            Ticket.created_at >= month_start,
            Ticket.created_at <= month_end
        ).count()
        breached = Ticket.query.filter(
            Ticket.created_at >= month_start,
            Ticket.created_at <= month_end,
            Ticket.sla_breached == True
        ).count()
        active = Ticket.query.filter(
            Ticket.created_at >= month_start,
            Ticket.created_at <= month_end,
            Ticket.status.notin_(['resolved', 'closed'])
        ).count()

        compliance = round(((active - breached) / active * 100), 1) if active > 0 else 100.0
        results.append({
            'month': month_start.strftime('%b %Y'),
            'total': total,
            'breached': breached,
            'compliance': compliance,
        })
    return results

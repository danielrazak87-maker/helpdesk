from app import db, mail
from app.models.notification import Notification
from flask_mail import Message
from flask import current_app


def send_notification(user_id, title, message, ticket_id=None, ntype='info'):
    """Create an in-app notification."""
    n = Notification(
        user_id=user_id,
        ticket_id=ticket_id,
        title=title,
        message=message,
        type=ntype
    )
    db.session.add(n)
    db.session.commit()


def send_email(subject, recipients, body_text, body_html=None):
    """Send an email notification."""
    try:
        msg = Message(subject=subject, recipients=recipients)
        msg.body = body_text
        if body_html:
            msg.html = body_html
        mail.send(msg)
    except Exception as e:
        current_app.logger.warning(f'Email send failed: {e}')


def notify_ticket_created(ticket, creator):
    """Notify user that their ticket was created."""
    send_notification(
        user_id=creator.id,
        ticket_id=ticket.id,
        title=f'Ticket {ticket.ticket_number} Created',
        message=f'Your ticket "{ticket.title}" has been submitted and will be reviewed shortly.',
        ntype='success'
    )


def notify_ticket_assigned(ticket):
    """Notify engineer of new ticket assignment."""
    if ticket.assigned_to:
        send_notification(
            user_id=ticket.assigned_to,
            ticket_id=ticket.id,
            title=f'New Ticket Assigned: {ticket.ticket_number}',
            message=f'You have been assigned ticket "{ticket.title}" (Priority: {ticket.priority.upper()}).',
            ntype='info'
        )


def notify_ticket_updated(ticket, updated_by_user):
    """Notify ticket creator of status change."""
    if ticket.created_by != updated_by_user.id:
        send_notification(
            user_id=ticket.created_by,
            ticket_id=ticket.id,
            title=f'Ticket {ticket.ticket_number} Updated',
            message=f'Your ticket status changed to: {ticket.status.replace("_", " ").title()}',
            ntype='info'
        )


def notify_ticket_resolved(ticket):
    """Notify user their ticket is resolved."""
    send_notification(
        user_id=ticket.created_by,
        ticket_id=ticket.id,
        title=f'✅ Ticket {ticket.ticket_number} Resolved',
        message=f'Your ticket "{ticket.title}" has been resolved. Please rate your experience.',
        ntype='success'
    )

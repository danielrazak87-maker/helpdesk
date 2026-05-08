from app import db, mail
from app.models.notification import Notification
from app.models.user import User
from flask_mail import Message
from flask import render_template, url_for, current_app


# ─── In-App Notifications ────────────────────────────────────────────────────

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


# ─── Email Notifications ─────────────────────────────────────────────────────

def send_email(subject, recipients, body_text, body_html=None):
    """Send an email notification via Flask-Mail."""
    if not recipients:
        return
    # Skip if SMTP not configured
    if not current_app.config.get('MAIL_USERNAME'):
        current_app.logger.info(f'Mail not configured — skipped email to {recipients}: {subject}')
        return

    try:
        msg = Message(subject=subject, recipients=recipients if isinstance(recipients, list) else [recipients])
        msg.body = body_text
        if body_html:
            msg.html = body_html
        mail.send(msg)
        current_app.logger.info(f'Email sent: {subject} → {recipients}')
    except Exception as e:
        current_app.logger.warning(f'Email send failed ({subject} → {recipients}): {e}')


# ─── Ticket Lifecycle Email + In-App ─────────────────────────────────────────

def notify_ticket_created(ticket, creator):
    """Notify user that their ticket was created (in-app + email)."""
    # In-app notification
    send_notification(
        user_id=creator.id,
        ticket_id=ticket.id,
        title=f'Ticket {ticket.ticket_number} Created',
        message=f'Your ticket "{ticket.title}" has been submitted.',
        ntype='success'
    )

    # Email notification
    ticket_url = url_for('tickets.detail', ticket_id=ticket.id, _external=True)
    html_body = render_template('email/ticket_created.html', user=creator, ticket=ticket, ticket_url=ticket_url)
    text_body = (
        f'Ticket {ticket.ticket_number} Created\n\n'
        f'Title: {ticket.title}\n'
        f'Priority: {ticket.priority}\n'
        f'Category: {ticket.category}\n'
        f'View: {ticket_url}\n'
    )
    send_email(
        subject=f'[Kayfalah Helpdesk] Ticket {ticket.ticket_number} Created',
        recipients=[creator.email],
        body_text=text_body,
        body_html=html_body
    )


def notify_ticket_assigned(ticket):
    """Notify engineer of new ticket assignment (in-app + email)."""
    if not ticket.assigned_to:
        return

    engineer = User.query.get(ticket.assigned_to)
    creator = User.query.get(ticket.created_by) if ticket.created_by else None

    # In-app notification
    send_notification(
        user_id=ticket.assigned_to,
        ticket_id=ticket.id,
        title=f'New Ticket Assigned: {ticket.ticket_number}',
        message=f'You have been assigned ticket "{ticket.title}" (Priority: {ticket.priority.upper()}).',
        ntype='info'
    )

    # Email notification
    ticket_url = url_for('tickets.detail', ticket_id=ticket.id, _external=True)
    html_body = render_template(
        'email/ticket_assigned.html',
        engineer=engineer,
        ticket=ticket,
        reporter=creator or engineer,
        ticket_url=ticket_url
    )
    text_body = (
        f'New Ticket Assigned: {ticket.ticket_number}\n\n'
        f'Title: {ticket.title}\n'
        f'Priority: {ticket.priority.upper()}\n'
        f'Category: {ticket.category}\n'
        f'Reported by: {creator.full_name if creator else "N/A"}\n'
        f'View: {ticket_url}\n'
    )
    send_email(
        subject=f'[Kayfalah Helpdesk] New Ticket: {ticket.ticket_number}',
        recipients=[engineer.email],
        body_text=text_body,
        body_html=html_body
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
    """Notify user their ticket is resolved (in-app + email)."""
    creator = User.query.get(ticket.created_by) if ticket.created_by else None

    # In-app notification
    send_notification(
        user_id=ticket.created_by,
        ticket_id=ticket.id,
        title=f'✅ Ticket {ticket.ticket_number} Resolved',
        message=f'Your ticket "{ticket.title}" has been resolved. Please rate your experience.',
        ntype='success'
    )

    if not creator:
        return

    # Email notification
    ticket_url = url_for('tickets.detail', ticket_id=ticket.id, _external=True)
    html_body = render_template('email/ticket_resolved.html', user=creator, ticket=ticket, ticket_url=ticket_url)
    text_body = (
        f'Ticket {ticket.ticket_number} Resolved\n\n'
        f'Title: {ticket.title}\n'
        f'Please rate your experience: {ticket_url}\n'
    )
    send_email(
        subject=f'[Kayfalah Helpdesk] Ticket {ticket.ticket_number} Resolved',
        recipients=[creator.email],
        body_text=text_body,
        body_html=html_body
    )


# ─── Password Reset Email ────────────────────────────────────────────────────

def send_password_reset_email(user, reset_url):
    """Send password reset email with branded template."""
    html_body = render_template('email/password_reset.html', user=user, reset_url=reset_url)
    text_body = (
        f'Password Reset Request\n\n'
        f'Hello {user.full_name},\n\n'
        f'You requested a password reset. Click the link below to reset your password:\n\n'
        f'{reset_url}\n\n'
        f'This link expires in 1 hour.\n\n'
        f'If you did not request this, please ignore this email.\n'
    )
    send_email(
        subject='[Kayfalah Helpdesk] Password Reset Request',
        recipients=[user.email],
        body_text=text_body,
        body_html=html_body
    )

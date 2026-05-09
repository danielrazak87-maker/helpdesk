from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import datetime, timezone
import os
from werkzeug.utils import secure_filename
from app import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
from app.models.ticket import Ticket, TicketComment, TicketHistory, TICKET_PRIORITIES, TICKET_CATEGORIES, TICKET_STATUSES
from app.models.sla import SLAPolicy
from app.services.sla_service import assign_sla
from app.services.attendance_service import auto_assign_engineer
from app.services.notification import (
    notify_ticket_created, notify_ticket_assigned,
    notify_ticket_updated, notify_ticket_resolved
)
from app.ticket_templates import TICKET_TEMPLATES

tickets_bp = Blueprint('tickets', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'txt', 'zip'}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@tickets_bp.route('/')
@login_required
def my_tickets() -> str:
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')

    if current_user.is_admin():
        query = Ticket.query
    elif current_user.is_engineer():
        query = Ticket.query.filter_by(assigned_to=current_user.id)
    else:
        query = Ticket.query.filter_by(project=current_user.project)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)

    tickets = query.order_by(Ticket.created_at.desc()).paginate(page=page, per_page=15)
    return render_template('tickets/list.html',
                           tickets=tickets,
                           statuses=TICKET_STATUSES,
                           priorities=TICKET_PRIORITIES,
                           status_filter=status_filter,
                           priority_filter=priority_filter)


@tickets_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create() -> str:
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium')
        category = request.form.get('category', 'other')

        if not title or not description:
            flash('Title and description are required.', 'danger')
            return render_template('tickets/create.html', priorities=TICKET_PRIORITIES, categories=TICKET_CATEGORIES, templates=TICKET_TEMPLATES)

        ticket = Ticket(
            ticket_number=Ticket.generate_ticket_number(),
            title=title,
            description=description,
            priority=priority,
            category=category,
            project=current_user.project,
            created_by=current_user.id,
            status='open'
        )

        # Handle file upload
        file = request.files.get('attachment')
        if file and file.filename and allowed_file(file.filename):
            from flask import current_app
            filename = secure_filename(f"{ticket.ticket_number}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            ticket.attachment = filename

        db.session.add(ticket)
        db.session.flush()  # get ticket.id

        assign_sla(ticket)

        engineer = auto_assign_engineer()
        if engineer:
            ticket.assigned_to = engineer.id

        db.session.commit()

        _log_history(ticket.id, current_user.id, 'status', None, 'open')
        notify_ticket_created(ticket, current_user)
        notify_ticket_assigned(ticket)

        flash(f'Ticket {ticket.ticket_number} created successfully!', 'success')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))

    # GET: check for template query param
    selected_template_key = request.args.get('template', '')
    selected_template = None
    default_title = ''
    if selected_template_key in TICKET_TEMPLATES:
        selected_template = TICKET_TEMPLATES[selected_template_key]
        # Build a default title hint from template name
        if selected_template_key != 'other':
            default_title = f'{selected_template["name"]} - '

    return render_template(
        'tickets/create.html',
        priorities=TICKET_PRIORITIES,
        categories=TICKET_CATEGORIES,
        templates=TICKET_TEMPLATES,
        selected_template=selected_template,
        default_title=default_title
    )


@tickets_bp.route('/<int:ticket_id>')
@login_required
def detail(ticket_id: int) -> str:
    ticket = Ticket.query.get_or_404(ticket_id)
    _check_access(ticket)

    comments = ticket.comments.order_by(TicketComment.created_at.asc()).all()
    if current_user.is_user():
        comments = [c for c in comments if not c.is_internal]

    history = TicketHistory.query.filter_by(ticket_id=ticket.id).order_by(TicketHistory.created_at.desc()).all()
    escalations = ticket.escalation_logs.order_by('created_at').all()

    from app.models.user import User
    engineers = User.query.filter_by(role='engineer', is_active=True).all() if not current_user.is_user() else []

    return render_template('tickets/detail.html',
                           ticket=ticket,
                           comments=comments,
                           history=history,
                           escalations=escalations,
                           engineers=engineers,
                           statuses=TICKET_STATUSES)


@tickets_bp.route('/<int:ticket_id>/update', methods=['POST'])
@login_required
def update(ticket_id: int) -> str:
    ticket = Ticket.query.get_or_404(ticket_id)
    _check_access(ticket)

    old_status = ticket.status
    new_status = request.form.get('status', ticket.status)
    new_assigned = request.form.get('assigned_to', type=int)

    if new_status != old_status:
        ticket.status = new_status
        _log_history(ticket.id, current_user.id, 'status', old_status, new_status)
        if new_status == 'resolved':
            ticket.resolved_at = _utcnow()
            notify_ticket_resolved(ticket)
        elif new_status == 'closed':
            ticket.closed_at = _utcnow()
        notify_ticket_updated(ticket, current_user)

    if new_assigned and new_assigned != ticket.assigned_to and not current_user.is_user():
        old_assigned = ticket.assigned_to
        ticket.assigned_to = new_assigned
        _log_history(ticket.id, current_user.id, 'assigned_to', str(old_assigned), str(new_assigned))
        notify_ticket_assigned(ticket)

    ticket.updated_at = _utcnow()
    db.session.commit()
    flash('Ticket updated.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id: int) -> str:
    ticket = Ticket.query.get_or_404(ticket_id)
    _check_access(ticket)

    content = request.form.get('content', '').strip()
    is_internal = request.form.get('is_internal') == 'on' and not current_user.is_user()

    if not content:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))

    comment = TicketComment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content=content,
        is_internal=is_internal
    )
    db.session.add(comment)

    # Mark as responded if engineer is first to comment
    if current_user.is_engineer() and not ticket.sla_responded_at:
        ticket.sla_responded_at = _utcnow()

    db.session.commit()
    flash('Comment added.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket_id))


@tickets_bp.route('/<int:ticket_id>/rate', methods=['POST'])
@login_required
def rate_ticket(ticket_id: int) -> str:
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.created_by != current_user.id:
        abort(403)
    if ticket.status not in ['resolved', 'closed']:
        flash('You can only rate resolved tickets.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))

    rating = request.form.get('rating', type=int)
    feedback = request.form.get('feedback', '').strip()
    if rating and 1 <= rating <= 5:
        ticket.rating = rating
        ticket.feedback = feedback
        db.session.commit()
        flash('Thank you for your feedback!', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket_id))


def _check_access(ticket) -> None:
    if current_user.is_admin():
        return
    if current_user.is_engineer() and ticket.assigned_to == current_user.id:
        return
    if current_user.is_user() and ticket.project == current_user.project:
        return
    abort(403)


def _log_history(ticket_id: int, user_id: int, field: str, old_val: str | None, new_val: str | None) -> None:
    h = TicketHistory(
        ticket_id=ticket_id,
        changed_by=user_id,
        field_changed=field,
        old_value=str(old_val) if old_val else None,
        new_value=str(new_val) if new_val else None
    )
    db.session.add(h)

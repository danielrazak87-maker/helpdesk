from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from functools import wraps
from typing import Any, Callable
from app import db
from app.models.user import User
from app.models.client import Client
from app.models.ticket import Ticket, TICKET_PRIORITIES, TICKET_STATUSES
from app.models.sla import SLAPolicy
from app.models.escalation import EscalationRule, EscalationLog
from app.models.attendance import Attendance
from datetime import datetime, date, timezone, timedelta

admin_bp = Blueprint('admin', __name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def admin_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ─── Dashboard ───────────────────────────────────────────────────────────────

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard() -> str:
    from sqlalchemy import func
    total_tickets = Ticket.query.count()
    open_tickets = Ticket.query.filter_by(status='open').count()
    in_progress = Ticket.query.filter_by(status='in_progress').count()
    resolved = Ticket.query.filter(Ticket.status.in_(['resolved', 'closed'])).count()
    breached = Ticket.query.filter_by(sla_breached=True).count()
    total_users = User.query.filter_by(role='user').count()
    total_engineers = User.query.filter_by(role='engineer').count()

    # Priority breakdown
    priority_stats = db.session.query(
        Ticket.priority, func.count(Ticket.id)
    ).group_by(Ticket.priority).all()

    # Category breakdown
    category_stats = db.session.query(
        Ticket.category, func.count(Ticket.id)
    ).group_by(Ticket.category).all()

    # Status breakdown
    status_stats = db.session.query(
        Ticket.status, func.count(Ticket.id)
    ).group_by(Ticket.status).all()

    # Recent tickets
    recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(10).all()

    # Engineer workload
    engineers = User.query.filter_by(role='engineer', is_active=True).all()
    engineer_workload = []
    for eng in engineers:
        open_count = Ticket.query.filter_by(
            assigned_to=eng.id
        ).filter(Ticket.status.notin_(['resolved', 'closed'])).count()
        engineer_workload.append({'engineer': eng, 'open': open_count})

    # SLA compliance
    from app.services.sla_service import get_sla_dashboard_stats
    sla_stats = get_sla_dashboard_stats()

    # At-risk and breached tickets for quick view
    at_risk_tickets = Ticket.query.filter(
        Ticket.sla_state == 'at_risk',
        Ticket.status.notin_(['resolved', 'closed'])
    ).order_by(Ticket.sla_resolution_due.asc()).limit(5).all()

    breached_tickets = Ticket.query.filter(
        Ticket.sla_state == 'breached',
        Ticket.status.notin_(['resolved', 'closed'])
    ).order_by(Ticket.sla_resolution_due.asc()).limit(5).all()

    return render_template('admin/dashboard.html',
                           total_tickets=total_tickets,
                           open_tickets=open_tickets,
                           in_progress=in_progress,
                           resolved=resolved,
                           breached=breached,
                           total_users=total_users,
                           total_engineers=total_engineers,
                           priority_stats=dict(priority_stats),
                           category_stats=dict(category_stats),
                           status_stats=dict(status_stats),
                           by_status=dict(status_stats),
                           recent_tickets=recent_tickets,
                           engineer_workload=engineer_workload,
                           sla_stats=sla_stats,
                           at_risk_tickets=at_risk_tickets,
                           breached_tickets=breached_tickets)


# ─── User Management ──────────────────────────────────────────────────────────

@admin_bp.route('/users')
@login_required
@admin_required
def users() -> str:
    role_filter = request.args.get('role', '')
    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    users_list = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users_list, role_filter=role_filter)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user() -> str:
    clients = Client.query.order_by(Client.name).all()
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'user')
        department = request.form.get('department', '')
        phone = request.form.get('phone', '')
        password = request.form.get('password', '')
        client_id = request.form.get('client_id', '')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('admin/user_form.html', action='Create', clients=clients)

        user = User(
            email=email,
            full_name=full_name,
            role=role,
            department=department,
            phone=phone,
            client_id=int(client_id) if client_id else None,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f'User {full_name} created successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', action='Create', user=None, clients=clients)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id: int) -> str:
    user = User.query.get_or_404(user_id)
    clients = Client.query.order_by(Client.name).all()
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', user.full_name)
        user.role = request.form.get('role', user.role)
        user.department = request.form.get('department', user.department)
        user.phone = request.form.get('phone', user.phone)
        user.is_active = request.form.get('is_active') == 'on'
        client_id = request.form.get('client_id', '')
        user.client_id = int(client_id) if client_id else None
        new_pass = request.form.get('password', '')
        if new_pass:
            user.set_password(new_pass)
        db.session.commit()
        flash('User updated.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', action='Edit', user=user, clients=clients)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id: int) -> str:
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    state = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.full_name} {state}.', 'info')
    return redirect(url_for('admin.users'))


# ─── SLA Management ──────────────────────────────────────────────────────────

@admin_bp.route('/sla')
@login_required
@admin_required
def sla_list() -> str:
    policies = SLAPolicy.query.all()
    return render_template('admin/sla.html', policies=policies)


@admin_bp.route('/sla/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_sla() -> str:
    if request.method == 'POST':
        policy = SLAPolicy(
            name=request.form.get('name'),
            priority=request.form.get('priority'),
            response_time_mins=int(request.form.get('response_time_mins', 60)),
            resolution_time_mins=int(request.form.get('resolution_time_mins', 480)),
            escalate_on_breach=request.form.get('escalate_on_breach') == 'on'
        )
        db.session.add(policy)
        db.session.commit()
        flash('SLA Policy created.', 'success')
        return redirect(url_for('admin.sla_list'))
    return render_template('admin/sla_form.html', policy=None, priorities=TICKET_PRIORITIES)


@admin_bp.route('/sla/<int:policy_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_sla(policy_id: int) -> str:
    policy = SLAPolicy.query.get_or_404(policy_id)
    if request.method == 'POST':
        policy.name = request.form.get('name', policy.name)
        policy.priority = request.form.get('priority', policy.priority)
        policy.response_time_mins = int(request.form.get('response_time_mins', policy.response_time_mins))
        policy.resolution_time_mins = int(request.form.get('resolution_time_mins', policy.resolution_time_mins))
        policy.escalate_on_breach = request.form.get('escalate_on_breach') == 'on'
        db.session.commit()
        flash('SLA Policy updated.', 'success')
        return redirect(url_for('admin.sla_list'))
    return render_template('admin/sla_form.html', policy=policy, priorities=TICKET_PRIORITIES)


# ─── Escalation Management ────────────────────────────────────────────────────

@admin_bp.route('/escalation')
@login_required
@admin_required
def escalation_list() -> str:
    rules = EscalationRule.query.order_by(EscalationRule.sla_policy_id, EscalationRule.escalation_level).all()
    policies = SLAPolicy.query.all()
    engineers = User.query.filter(User.role.in_(['engineer', 'admin']), User.is_active == True).all()
    return render_template('admin/escalation.html', rules=rules, policies=policies, engineers=engineers)


@admin_bp.route('/escalation/create', methods=['POST'])
@login_required
@admin_required
def create_escalation() -> str:
    rule = EscalationRule(
        sla_policy_id=int(request.form.get('sla_policy_id')),
        escalate_to=int(request.form.get('escalate_to')),
        trigger_after_mins=int(request.form.get('trigger_after_mins', 60)),
        escalation_level=int(request.form.get('escalation_level', 1))
    )
    db.session.add(rule)
    db.session.commit()
    flash('Escalation rule created.', 'success')
    return redirect(url_for('admin.escalation_list'))


@admin_bp.route('/escalation/<int:rule_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_escalation(rule_id: int) -> str:
    rule = EscalationRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash('Escalation rule deleted.', 'info')
    return redirect(url_for('admin.escalation_list'))


# ─── All Tickets (Admin) ─────────────────────────────────────────────────────

@admin_bp.route('/tickets')
@login_required
@admin_required
def all_tickets() -> str:
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')
    sla_filter = request.args.get('sla_status', '')
    query = Ticket.query
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if sla_filter:
        query = query.filter_by(sla_state=sla_filter)
    tickets = query.order_by(Ticket.created_at.desc()).paginate(page=page, per_page=20)
    engineers = User.query.filter_by(role='engineer', is_active=True).all()
    return render_template('admin/tickets.html',
                           tickets=tickets,
                           statuses=TICKET_STATUSES,
                           priorities=TICKET_PRIORITIES,
                           status_filter=status,
                           priority_filter=priority,
                           sla_filter=sla_filter,
                           engineers=engineers)


# ─── Attendance (Admin) ────────────────────────────────────────────────────

@admin_bp.route('/attendance')
@login_required
@admin_required
def attendance() -> str:
    """Admin view: attendance for ALL engineers / R&D members / workers."""
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    start = date(year, month, 1)
    # Last day of month
    if month < 12:
        end = date(year, month + 1, 1) - timedelta(days=1)
    else:
        end = date(year + 1, 1, 1) - timedelta(days=1)

    # Get all active engineers / R&D / workers (non-admin, non-end-user staff)
    members = User.query.filter(
        User.role == 'engineer',
        User.is_active == True
    ).order_by(User.full_name).all()

    # Build attendance data per member
    member_data = []
    all_records = []  # flat list for the table view
    for member in members:
        records = Attendance.query.filter(
            Attendance.engineer_id == member.id,
            Attendance.work_date >= start,
            Attendance.work_date <= end
        ).order_by(Attendance.work_date.desc()).all()
        total_hours = sum(r.working_hours() for r in records)
        present_days = len([r for r in records if r.status == 'present'])
        member_data.append({
            'engineer': member,
            'records': records,
            'total_hours': round(total_hours, 2),
            'present_days': present_days
        })
        for r in records:
            all_records.append({'engineer': member, 'record': r})

    # Sort all_records by work_date desc, then engineer name
    all_records.sort(key=lambda x: (x['record'].work_date, x['engineer'].full_name), reverse=True)

    total_hours_all = sum(m['total_hours'] for m in member_data)
    total_present_all = sum(m['present_days'] for m in member_data)

    return render_template('admin/attendance.html',
                           member_data=member_data,
                           all_records=all_records,
                           total_hours_all=round(total_hours_all, 2),
                           total_present_all=total_present_all,
                           month=month, year=year)


# ─── Bulk Operations ─────────────────────────────────────────────────────────

@admin_bp.route('/tickets/bulk-close', methods=['POST'])
@login_required
@admin_required
def bulk_close_tickets():
    """Close multiple tickets at once."""
    ticket_ids = request.form.getlist('ticket_ids', type=int)
    if not ticket_ids:
        flash('No tickets selected.', 'warning')
        return redirect(url_for('admin.all_tickets'))

    now = _utcnow()
    count = 0
    for tid in ticket_ids:
        ticket = db.session.get(Ticket, tid)
        if ticket and ticket.status not in ('closed',):
            ticket.status = 'closed'
            ticket.closed_at = now
            ticket.updated_at = now
            count += 1
    db.session.commit()
    flash(f'{count} ticket(s) closed successfully.', 'success')
    return redirect(url_for('admin.all_tickets'))


@admin_bp.route('/tickets/bulk-assign', methods=['POST'])
@login_required
@admin_required
def bulk_assign_tickets():
    """Assign multiple tickets to an engineer at once."""
    ticket_ids = request.form.getlist('ticket_ids', type=int)
    engineer_id = request.form.get('engineer_id', type=int)

    if not ticket_ids:
        flash('No tickets selected.', 'warning')
        return redirect(url_for('admin.all_tickets'))
    if not engineer_id:
        flash('No engineer selected.', 'warning')
        return redirect(url_for('admin.all_tickets'))

    engineer = db.session.get(User, engineer_id)
    if not engineer or engineer.role not in ('engineer', 'admin'):
        flash('Invalid engineer selected.', 'danger')
        return redirect(url_for('admin.all_tickets'))

    now = _utcnow()
    count = 0
    for tid in ticket_ids:
        ticket = db.session.get(Ticket, tid)
        if ticket:
            ticket.assigned_to = engineer_id
            ticket.updated_at = now
            count += 1
    db.session.commit()
    flash(f'{count} ticket(s) assigned to {engineer.full_name}.', 'success')
    return redirect(url_for('admin.all_tickets'))


# ─── Client Management ─────────────────────────────────────────────────────────

@admin_bp.route('/clients')
@login_required
@admin_required
def clients() -> str:
    from app.models.client import Client
    clients_list = Client.query.order_by(Client.name).all()
    return render_template('admin/clients.html', clients=clients_list)


@admin_bp.route('/clients/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_client() -> str:
    from app.models.client import Client
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        if not name:
            flash('Client name is required.', 'danger')
            return render_template('admin/client_form.html', action='Create', client=None)
        if Client.query.filter_by(name=name).first():
            flash('A client with that name already exists.', 'danger')
            return render_template('admin/client_form.html', action='Create', client=None)
        client = Client(
            name=name,
            description=description,
            response_time_hours=float(request.form.get('response_time_hours')) if request.form.get('response_time_hours') else None,
            resolution_time_hours=float(request.form.get('resolution_time_hours')) if request.form.get('resolution_time_hours') else None,
            sla1_time_hours=float(request.form.get('sla1_time_hours')) if request.form.get('sla1_time_hours') else None,
            sla2_time_hours=float(request.form.get('sla2_time_hours')) if request.form.get('sla2_time_hours') else None,
            sla3_time_hours=float(request.form.get('sla3_time_hours')) if request.form.get('sla3_time_hours') else None,
            business_hours_only=request.form.get('business_hours_only') == 'on',
            active_sla=request.form.get('active_sla') == 'on'
        )
        db.session.add(client)
        db.session.commit()
        flash(f'Client "{name}" created.', 'success')
        return redirect(url_for('admin.clients'))
    return render_template('admin/client_form.html', action='Create', client=None)


@admin_bp.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_client(client_id: int) -> str:
    from app.models.client import Client
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Client name is required.', 'danger')
            return render_template('admin/client_form.html', action='Edit', client=client)
        existing = Client.query.filter_by(name=name).first()
        if existing and existing.id != client.id:
            flash('A client with that name already exists.', 'danger')
            return render_template('admin/client_form.html', action='Edit', client=client)
        client.name = name
        client.description = request.form.get('description', '').strip()
        client.response_time_hours = float(request.form.get('response_time_hours')) if request.form.get('response_time_hours') else None
        client.resolution_time_hours = float(request.form.get('resolution_time_hours')) if request.form.get('resolution_time_hours') else None
        client.sla1_time_hours = float(request.form.get('sla1_time_hours')) if request.form.get('sla1_time_hours') else None
        client.sla2_time_hours = float(request.form.get('sla2_time_hours')) if request.form.get('sla2_time_hours') else None
        client.sla3_time_hours = float(request.form.get('sla3_time_hours')) if request.form.get('sla3_time_hours') else None
        client.business_hours_only = request.form.get('business_hours_only') == 'on'
        client.active_sla = request.form.get('active_sla') == 'on'
        db.session.commit()
        flash('Client updated.', 'success')
        return redirect(url_for('admin.clients'))
    return render_template('admin/client_form.html', action='Edit', client=client)


@admin_bp.route('/clients/<int:client_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_client(client_id: int) -> str:
    from app.models.client import Client
    client_obj = Client.query.get_or_404(client_id)
    for user in client_obj.users:
        user.client_id = None
    db.session.delete(client_obj)
    db.session.commit()
    flash(f'Client "{client_obj.name}" deleted.', 'info')
    return redirect(url_for('admin.clients'))

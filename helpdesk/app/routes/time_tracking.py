from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.time_tracking import TimeEntry
from app.models.ticket import Ticket
from app.models.user import User
from datetime import date, datetime, timedelta

time_bp = Blueprint('time', __name__, url_prefix='/time')

def engineer_or_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or (not current_user.is_engineer() and not current_user.is_admin()):
            abort(403)
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated

@time_bp.route('/ticket/<int:ticket_id>')
@login_required
def ticket_time(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    # Check access
    if current_user.is_user() and ticket.project != current_user.project:
        abort(403)
    if current_user.is_engineer() and ticket.assigned_to != current_user.id and ticket.created_by != current_user.id:
        abort(403)

    entries = TimeEntry.query.filter_by(ticket_id=ticket_id).order_by(TimeEntry.log_date.desc()).all()
    total_hours = sum(e.hours for e in entries)
    today_date = date.today().isoformat()
    return render_template('time/ticket_time.html', 
                          ticket=ticket, 
                          entries=entries, 
                          total_hours=total_hours,
                          today_date=today_date)

@time_bp.route('/ticket/<int:ticket_id>/add', methods=['POST'])
@login_required
@engineer_or_admin_required
def add_time(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    # Check access
    if current_user.is_engineer() and ticket.assigned_to != current_user.id:
        abort(403)

    hours = request.form.get('hours', type=float)
    description = request.form.get('description', '').strip()
    log_date_str = request.form.get('log_date', date.today().isoformat())

    if not hours or hours <= 0:
        flash('Please enter a valid number of hours.', 'danger')
        return redirect(url_for('time.ticket_time', ticket_id=ticket_id))

    try:
        log_date = date.fromisoformat(log_date_str)
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('time.ticket_time', ticket_id=ticket_id))

    entry = TimeEntry(
        ticket_id=ticket_id,
        user_id=current_user.id,
        description=description,
        hours=hours,
        log_date=log_date
    )
    db.session.add(entry)
    db.session.commit()
    flash('Time logged successfully.', 'success')
    return redirect(url_for('time.ticket_time', ticket_id=ticket_id))

@time_bp.route('/entry/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = TimeEntry.query.get_or_404(entry_id)
    # Can delete own entry or admin can delete any
    if entry.user_id != current_user.id and not current_user.is_admin():
        abort(403)
    db.session.delete(entry)
    db.session.commit()
    flash('Time entry deleted.', 'success')
    return redirect(request.referrer or url_for('time.my_logs'))

@time_bp.route('/my-logs')
@login_required
@engineer_or_admin_required
def my_logs():
    start_str = request.args.get('start', (date.today() - timedelta(days=30)).isoformat())
    end_str = request.args.get('end', date.today().isoformat())

    try:
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
    except ValueError:
        start = date.today() - timedelta(days=30)
        end = date.today()

    entries = TimeEntry.query.filter(
        TimeEntry.user_id == current_user.id,
        TimeEntry.log_date >= start,
        TimeEntry.log_date <= end
    ).order_by(TimeEntry.log_date.desc()).all()

    total_hours = sum(e.hours for e in entries)
    # Daily total
    daily = {}
    for e in entries:
        daily[e.log_date.isoformat()] = daily.get(e.log_date.isoformat(), 0) + e.hours

    return render_template('time/my_logs.html',
                          entries=entries,
                          total_hours=total_hours,
                          daily_totals=daily,
                          start=start.isoformat(),
                          end=end.isoformat())

@time_bp.route('/report')
@login_required
@admin_required
def time_report():
    start_str = request.args.get('start', (date.today() - timedelta(days=30)).isoformat())
    end_str = request.args.get('end', date.today().isoformat())
    engineer_id = request.args.get('engineer_id', type=int)
    project = request.args.get('project', '')

    try:
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
    except ValueError:
        start = date.today() - timedelta(days=30)
        end = date.today()

    query = TimeEntry.query.join(Ticket).filter(
        TimeEntry.log_date >= start,
        TimeEntry.log_date <= end
    )

    if engineer_id:
        query = query.filter(TimeEntry.user_id == engineer_id)
    if project:
        query = query.filter(Ticket.project == project)

    entries = query.order_by(TimeEntry.log_date.desc()).all()
    total_hours = sum(e.hours for e in entries)
    entry_count = len(entries)

    # Group by engineer
    by_engineer = {}
    for e in entries:
        eng = e.user
        if eng.id not in by_engineer:
            by_engineer[eng.id] = {'name': eng.full_name, 'hours': 0, 'count': 0}
        by_engineer[eng.id]['hours'] += e.hours
        by_engineer[eng.id]['count'] += 1

    # Group by project
    by_project = {}
    for e in entries:
        proj = e.ticket.project
        if proj not in by_project:
            by_project[proj] = {'hours': 0, 'count': 0}
        by_project[proj]['hours'] += e.hours
        by_project[proj]['count'] += 1

    engineers = User.query.filter_by(role='engineer', is_active=True).all()
    return render_template('time/report.html',
                          entries=entries,
                          total_hours=total_hours,
                          entry_count=entry_count,
                          by_engineer=by_engineer,
                          by_project=by_project,
                          engineers=engineers,
                          start=start.isoformat(),
                          end=end.isoformat(),
                          selected_engineer=engineer_id,
                          selected_project=project)

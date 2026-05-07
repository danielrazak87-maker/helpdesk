from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from datetime import date, datetime, timedelta
from app import db
from app.models.ticket import Ticket, TICKET_STATUSES
from app.models.attendance import Attendance
from app.services.attendance_service import check_in, check_out

engineer_bp = Blueprint('engineer', __name__)


def engineer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_engineer() or current_user.is_admin()):
            abort(403)
        return f(*args, **kwargs)
    return decorated


@engineer_bp.route('/dashboard')
@login_required
@engineer_required
def dashboard():
    today = date.today()
    my_open = Ticket.query.filter_by(
        assigned_to=current_user.id
    ).filter(Ticket.status.notin_(['resolved', 'closed'])).count()

    my_resolved_today = Ticket.query.filter_by(
        assigned_to=current_user.id, status='resolved'
    ).filter(
        Ticket.resolved_at >= datetime.combine(today, datetime.min.time())
    ).count()

    my_breached = Ticket.query.filter_by(
        assigned_to=current_user.id, sla_breached=True
    ).filter(Ticket.status.notin_(['resolved', 'closed'])).count()

    recent = Ticket.query.filter_by(
        assigned_to=current_user.id
    ).order_by(Ticket.created_at.desc()).limit(10).all()

    attendance_today = Attendance.query.filter_by(
        engineer_id=current_user.id, work_date=today
    ).first()

    week_ago = today - timedelta(days=7)
    weekly_attendance = Attendance.query.filter(
        Attendance.engineer_id == current_user.id,
        Attendance.work_date >= week_ago
    ).all()

    return render_template('engineer/dashboard.html',
                           my_open=my_open,
                           my_resolved_today=my_resolved_today,
                           my_breached=my_breached,
                           recent=recent,
                           attendance_today=attendance_today,
                           weekly_attendance=weekly_attendance)


@engineer_bp.route('/check-in', methods=['POST'])
@login_required
@engineer_required
def do_check_in():
    record, error = check_in(current_user.id)
    if error:
        flash(error, 'warning')
    else:
        flash(f'Checked in at {record.check_in.strftime("%H:%M")}. Have a great day!', 'success')
    return redirect(url_for('engineer.dashboard'))


@engineer_bp.route('/check-out', methods=['POST'])
@login_required
@engineer_required
def do_check_out():
    record, error = check_out(current_user.id)
    if error:
        flash(error, 'warning')
    else:
        flash(f'Checked out at {record.check_out.strftime("%H:%M")}. Hours: {record.working_hours()}h', 'success')
    return redirect(url_for('engineer.dashboard'))


@engineer_bp.route('/attendance')
@login_required
@engineer_required
def attendance():
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    start = date(year, month, 1)
    end = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)

    records = Attendance.query.filter(
        Attendance.engineer_id == current_user.id,
        Attendance.work_date >= start,
        Attendance.work_date <= end
    ).order_by(Attendance.work_date.desc()).all()

    total_hours = sum(r.working_hours() for r in records)
    present_days = len([r for r in records if r.status == 'present'])

    return render_template('engineer/attendance.html',
                           records=records,
                           total_hours=round(total_hours, 2),
                           present_days=present_days,
                           month=month, year=year)

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models.ticket import Ticket
from app.models.user import User
from app.models.notification import Notification
from app import db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_engineer():
        return redirect(url_for('engineer.dashboard'))
    else:
        return redirect(url_for('tickets.my_tickets'))


@main_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return redirect(url_for('main.dashboard'))


@main_bp.route('/notifications/<int:nid>/read')
@login_required
def mark_notification_read(nid):
    n = Notification.query.get_or_404(nid)
    if n.user_id == current_user.id:
        n.is_read = True
        db.session.commit()
    if n.ticket_id:
        return redirect(url_for('tickets.detail', ticket_id=n.ticket_id))
    return redirect(url_for('main.dashboard'))

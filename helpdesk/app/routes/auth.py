from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from datetime import datetime, timezone
import re
import qrcode
import base64
from io import BytesIO
from typing import Optional
from app import db, limiter


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
from app.models.user import User
from app.models.client import Client
from app.services.notification import send_email, send_password_reset_email

auth_bp = Blueprint('auth', __name__)


# ─── Password Validation ──────────────────────────────────────────────────────

def validate_password_strength(password: str) -> Optional[str]:
    """Check password meets minimum complexity requirements."""
    if len(password) < 8:
        return 'Password must be at least 8 characters long.'
    if not re.search(r'[A-Z]', password):
        return 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return 'Password must contain at least one lowercase letter.'
    if not re.search(r'[0-9]', password):
        return 'Password must contain at least one number.'
    return None


def validate_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ─── Token Helpers ────────────────────────────────────────────────────────────

def get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='password-reset')


# ─── Routes ───────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('auth/login.html')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password) and user.is_active:
            # If 2FA is enabled, start challenge flow
            if user.is_2fa_enabled:
                session['_2fa_user_id'] = user.id
                session['_2fa_remember'] = remember
                session['_2fa_next'] = request.args.get('next')
                return redirect(url_for('auth.two_factor_challenge'))

            user.last_login = _utcnow()
            db.session.commit()
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', current_user.full_name)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.department = request.form.get('department', current_user.department)

        new_password = request.form.get('new_password')
        if new_password:
            current_password = request.form.get('current_password')
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('auth.profile'))

            error = validate_password_strength(new_password)
            if error:
                flash(error, 'danger')
                return redirect(url_for('auth.profile'))

            current_user.set_password(new_password)
            flash('Password updated successfully.', 'success')

        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html',
                           is_2fa_enabled=current_user.is_2fa_enabled)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5/minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    clients = Client.query.order_by(Client.name).all()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '')
        project = request.form.get('project', '')
        client_id = request.form.get('client_id', '')

        if not email or not password or not full_name or not project:
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html', clients=clients)

        if not validate_email(email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('auth/register.html', clients=clients)

        error = validate_password_strength(password)
        if error:
            flash(error, 'danger')
            return render_template('auth/register.html', clients=clients)

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered.', 'warning')
            return render_template('auth/register.html', clients=clients)

        user = User(
            email=email,
            full_name=full_name,
            project=project,
            client_id=int(client_id) if client_id else None,
            role='user'
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Registration successful!', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('auth/register.html', clients=clients)


# ─── Password Reset ───────────────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5/minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('auth/forgot_password.html')

        # Always show success regardless of whether email exists (prevents enumeration)
        user = User.query.filter_by(email=email).first()
        if user:
            serializer = get_serializer()
            token = serializer.dumps(user.email)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                send_password_reset_email(user, reset_url)
            except Exception as e:
                current_app.logger.error(f'Password reset email failed for {email}: {e}')

        flash('If an account with that email exists, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit("5/minute")
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    try:
        serializer = get_serializer()
        email = serializer.loads(token, max_age=3600)  # 1 hour expiry
    except SignatureExpired:
        flash('The password reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash('Invalid password reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not password or not confirm:
            flash('Both password fields are required.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        error = validate_password_strength(password)
        if error:
            flash(error, 'danger')
            return render_template('auth/reset_password.html', token=token)

        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Account not found.', 'danger')
            return redirect(url_for('auth.login'))

        user.set_password(password)
        user.password_updated_at = _utcnow()
        db.session.commit()

        flash('Password has been reset successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


# ─── Two-Factor Authentication ───────────────────────────────────────────────


def _get_temporary_user():
    """Retrieve the user stored in session for 2FA challenge."""
    user_id = session.pop('_2fa_user_id', None)
    if not user_id:
        return None
    return db.session.get(User, int(user_id))


@auth_bp.route('/2fa/challenge', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def two_factor_challenge():
    """2FA challenge page — shown during login if 2FA is enabled."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    user_id = session.get('_2fa_user_id')
    if not user_id:
        flash('Session expired. Please log in again.', 'warning')
        return redirect(url_for('auth.login'))

    user = db.session.get(User, int(user_id))
    if not user or not user.is_2fa_enabled:
        session.pop('_2fa_user_id', None)
        flash('Invalid session. Please log in again.', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not code:
            flash('Please enter a verification code.', 'danger')
            return render_template('auth/2fa_challenge.html')

        # Try TOTP first, then backup code
        verified = user.verify_totp(code) or user.verify_backup_code(code)

        if verified:
            session.pop('_2fa_user_id', None)
            remember = session.pop('_2fa_remember', False)
            session.pop('_2fa_next', None)
            user.last_login = _utcnow()
            db.session.commit()
            login_user(user, remember=remember)
            next_page = request.args.get('next') or session.get('_2fa_next')
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid verification code. Please try again.', 'danger')

    return render_template('auth/2fa_challenge.html')


@auth_bp.route('/2fa/setup', methods=['GET', 'POST'])
@login_required
def two_factor_setup():
    """Enable 2FA — generate secret, show QR, verify code."""
    user = current_user

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not code:
            flash('Please enter the verification code from your app.', 'danger')
            return redirect(url_for('auth.two_factor_setup'))

        if user.verify_totp(code):
            backup_codes = user.generate_backup_codes()
            user.is_2fa_enabled = True
            db.session.commit()
            flash('Two-factor authentication has been enabled!', 'success')
            # Show backup codes once
            return render_template('auth/2fa_setup.html',
                                  qr_uri=_qr_data_uri(user.get_totp_uri()),
                                  secret=user.totp_secret,
                                  backup_codes=backup_codes,
                                  setup_done=True)
        else:
            flash('Invalid code. Please try again.', 'danger')
            return render_template('auth/2fa_setup.html',
                                  qr_uri=_qr_data_uri(user.get_totp_uri()),
                                  secret=user.totp_secret,
                                  backup_codes=[],
                                  setup_done=False)

    # Generate new secret if not already pending
    if not user.totp_secret:
        user.generate_totp_secret()
        db.session.commit()

    return render_template('auth/2fa_setup.html',
                          qr_uri=_qr_data_uri(user.get_totp_uri()),
                          secret=user.totp_secret,
                          backup_codes=[],
                          setup_done=False)


@auth_bp.route('/2fa/disable', methods=['POST'])
@login_required
def two_factor_disable():
    """Disable 2FA."""
    user = current_user
    user.disable_2fa()
    db.session.commit()
    flash('Two-factor authentication has been disabled.', 'info')
    return redirect(url_for('auth.profile'))


def _qr_data_uri(provisioning_uri: str) -> str:
    """Generate a data URI PNG for a QR code."""
    if not provisioning_uri:
        return ''
    img = qrcode.make(provisioning_uri, box_size=6, border=2)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f'data:image/png;base64,{b64}'

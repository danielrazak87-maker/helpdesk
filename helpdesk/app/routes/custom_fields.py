from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.custom_field import CustomField, CustomFieldValue
import json

cf_bp = Blueprint('cf', __name__, url_prefix='/admin/custom-fields')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated

@cf_bp.route('/')
@login_required
@admin_required
def list_fields():
    fields = CustomField.query.order_by(CustomField.sort_order.asc()).all()
    return render_template('admin/custom_fields/list.html', fields=fields)

@cf_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_field():
    if request.method == 'POST':
        field_name = request.form.get('field_name', '').strip()
        field_type = request.form.get('field_type', 'string')
        project = request.form.get('project', '').strip() or None
        is_required = request.form.get('is_required') == 'on'
        sort_order = request.form.get('sort_order', 0, type=int)
        field_options = request.form.get('field_options', '').strip()

        if not field_name:
            flash('Field name is required.', 'danger')
            return render_template('admin/custom_fields/form.html')

        # Validate options for select type
        if field_type == 'select' and field_options:
            try:
                json.loads(field_options)
            except json.JSONDecodeError:
                flash('Options must be valid JSON array for select type.', 'danger')
                return render_template('admin/custom_fields/form.html')

        field = CustomField(
            field_name=field_name,
            field_type=field_type,
            project=project,
            is_required=is_required,
            sort_order=sort_order,
            field_options=field_options if field_type == 'select' else None
        )
        db.session.add(field)
        db.session.commit()
        flash('Custom field created successfully.', 'success')
        return redirect(url_for('cf.list_fields'))

    return render_template('admin/custom_fields/form.html')

@cf_bp.route('/<int:field_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_field(field_id):
    field = CustomField.query.get_or_404(field_id)
    if request.method == 'POST':
        field.field_name = request.form.get('field_name', '').strip()
        field.field_type = request.form.get('field_type', 'string')
        field.project = request.form.get('project', '').strip() or None
        field.is_required = request.form.get('is_required') == 'on'
        field.sort_order = request.form.get('sort_order', 0, type=int)
        field_options = request.form.get('field_options', '').strip()

        if not field.field_name:
            flash('Field name is required.', 'danger')
            return render_template('admin/custom_fields/form.html', field=field)

        if field.field_type == 'select' and field_options:
            try:
                json.loads(field_options)
            except json.JSONDecodeError:
                flash('Options must be valid JSON array for select type.', 'danger')
                return render_template('admin/custom_fields/form.html', field=field)
        field.field_options = field_options if field.field_type == 'select' else None
        db.session.commit()
        flash('Custom field updated successfully.', 'success')
        return redirect(url_for('cf.list_fields'))

    return render_template('admin/custom_fields/form.html', field=field)

@cf_bp.route('/<int:field_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_field(field_id):
    field = CustomField.query.get_or_404(field_id)
    db.session.delete(field)
    db.session.commit()
    flash('Custom field deleted successfully.', 'success')
    return redirect(url_for('cf.list_fields'))

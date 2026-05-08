from __future__ import annotations
from app.models.custom_field import CustomField, CustomFieldValue
from app import db
import json

def get_fields_for_project(project: str = None):
    """Return applicable fields (all global + project-specific)"""
    query = CustomField.query
    if project:
        query = query.filter((CustomField.project == project) | (CustomField.project == None))
    else:
        query = query.filter(CustomField.project == None)
    return query.order_by(CustomField.sort_order.asc()).all()

def get_field_values(ticket_id: int):
    """Return dict of {field_name: value} for a ticket"""
    values = CustomFieldValue.query.filter_by(ticket_id=ticket_id).all()
    return {v.field.field_name: v.value for v in values if v.field}

def save_field_values(ticket_id: int, form_data: dict):
    """Save custom field values from form POST data"""
    # Delete existing values first
    CustomFieldValue.query.filter_by(ticket_id=ticket_id).delete()
    # Save new values
    for field in CustomField.query.all():
        field_name = f"custom_{field.id}"
        if field_name in form_data:
            value = form_data[field_name].strip()
            if value:
                cfv = CustomFieldValue(
                    ticket_id=ticket_id,
                    field_id=field.id,
                    value=value
                )
                db.session.add(cfv)
    db.session.commit()

def render_field(field: CustomField, value: str = None) -> str:
    """Return HTML string for a field input"""
    field_name = f"custom_{field.id}"
    required = 'required' if field.is_required else ''
    options = json.loads(field.field_options) if field.field_options else []

    if field.field_type == 'string':
        return f'''
        <div class="form-group">
            <label>{field.field_name} {'' if not field.is_required else '*'}</label>
            <input type="text" name="{field_name}" class="form-control" value="{value or ''}" {required}>
        </div>'''
    elif field.field_type == 'text':
        return f'''
        <div class="form-group">
            <label>{field.field_name} {'' if not field.is_required else '*'}</label>
            <textarea name="{field_name}" class="form-control" rows="3" {required}>{value or ''}</textarea>
        </div>'''
    elif field.field_type == 'number':
        return f'''
        <div class="form-group">
            <label>{field.field_name} {'' if not field.is_required else '*'}</label>
            <input type="number" name="{field_name}" class="form-control" value="{value or ''}" {required}>
        </div>'''
    elif field.field_type == 'date':
        return f'''
        <div class="form-group">
            <label>{field.field_name} {'' if not field.is_required else '*'}</label>
            <input type="date" name="{field_name}" class="form-control" value="{value or ''}" {required}>
        </div>'''
    elif field.field_type == 'select' and options:
        options_html = ''.join([f'<option value="{opt}" {"selected" if opt == value else ""}>{opt}</option>' for opt in options])
        return f'''
        <div class="form-group">
            <label>{field.field_name} {'' if not field.is_required else '*'}</label>
            <select name="{field_name}" class="form-control" {required}>
                <option value="">Select...</option>
                {options_html}
            </select>
        </div>'''
    return ''

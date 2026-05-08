from __future__ import annotations
from app import db, utcnow
from datetime import datetime

class CustomField(db.Model):
    __tablename__ = 'custom_fields'
    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(100))
    field_name = db.Column(db.String(100), nullable=False)
    field_type = db.Column(db.String(20), nullable=False, default='string')
    field_options = db.Column(db.Text)  # JSON for select type
    is_required = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    values = db.relationship('CustomFieldValue', backref='field', lazy='dynamic', cascade='all, delete-orphan')

class CustomFieldValue(db.Model):
    __tablename__ = 'custom_field_values'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey('custom_fields.id'), nullable=False)
    value = db.Column(db.Text)

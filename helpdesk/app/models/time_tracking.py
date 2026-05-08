from __future__ import annotations
from app import db, utcnow
from datetime import date, datetime

class TimeEntry(db.Model):
    __tablename__ = 'time_entries'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.String(500))
    hours = db.Column(db.Float, nullable=False)
    log_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=utcnow)
    ticket = db.relationship('Ticket', backref=db.backref('time_entries', lazy='dynamic', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('time_entries', lazy='dynamic'))

from __future__ import annotations

from app import db, utcnow
from datetime import datetime, date
from typing import Optional


class Attendance(db.Model):
    __tablename__ = 'attendance'

    id: int = db.Column(db.Integer, primary_key=True)
    engineer_id: int = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    work_date: date = db.Column(db.Date, nullable=False, default=utcnow().date)
    check_in: Optional[datetime] = db.Column(db.DateTime)
    check_out: Optional[datetime] = db.Column(db.DateTime)
    status: str = db.Column(db.String(20), default='present')  # present, absent, half_day, leave
    notes: Optional[str] = db.Column(db.Text)

    __table_args__ = (db.UniqueConstraint('engineer_id', 'work_date', name='uq_engineer_date'),)

    def working_hours(self) -> float:
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            return round(delta.total_seconds() / 3600, 2)
        return 0.0

    def is_checked_in(self) -> bool:
        return self.check_in is not None and self.check_out is None

    def __repr__(self) -> str:
        return f'<Attendance Engineer#{self.engineer_id} {self.work_date}>'

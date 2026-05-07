from app import db
from datetime import datetime


class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    engineer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    work_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='present')  # present, absent, half_day, leave
    notes = db.Column(db.Text)

    __table_args__ = (db.UniqueConstraint('engineer_id', 'work_date', name='uq_engineer_date'),)

    def working_hours(self):
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            return round(delta.total_seconds() / 3600, 2)
        return 0

    def is_checked_in(self):
        return self.check_in is not None and self.check_out is None

    def __repr__(self):
        return f'<Attendance Engineer#{self.engineer_id} {self.work_date}>'

from datetime import datetime, date
from app import db
from app.models.attendance import Attendance
from app.models.user import User


def check_in(engineer_id):
    """Record check-in for today."""
    today = date.today()
    record = Attendance.query.filter_by(engineer_id=engineer_id, work_date=today).first()
    if record:
        return None, 'Already checked in today.'
    record = Attendance(
        engineer_id=engineer_id,
        work_date=today,
        check_in=datetime.utcnow(),
        status='present'
    )
    db.session.add(record)
    db.session.commit()
    return record, None


def check_out(engineer_id):
    """Record check-out for today."""
    today = date.today()
    record = Attendance.query.filter_by(engineer_id=engineer_id, work_date=today).first()
    if not record or not record.check_in:
        return None, 'No check-in found for today.'
    if record.check_out:
        return None, 'Already checked out today.'
    record.check_out = datetime.utcnow()
    db.session.commit()
    return record, None


def get_engineer_attendance(engineer_id, start_date, end_date):
    return Attendance.query.filter(
        Attendance.engineer_id == engineer_id,
        Attendance.work_date >= start_date,
        Attendance.work_date <= end_date
    ).order_by(Attendance.work_date.desc()).all()


def get_available_engineers():
    """Return engineers who are currently checked in (available for assignment)."""
    today = date.today()
    checked_in_ids = db.session.query(Attendance.engineer_id).filter(
        Attendance.work_date == today,
        Attendance.check_in.isnot(None),
        Attendance.check_out.is_(None)
    ).subquery()

    return User.query.filter(
        User.role == 'engineer',
        User.is_active == True,
        User.id.in_(checked_in_ids)
    ).all()


def auto_assign_engineer():
    """Round-robin assign to available engineer with fewest open tickets."""
    from app.models.ticket import Ticket
    engineers = get_available_engineers()
    if not engineers:
        # Fall back to all active engineers
        engineers = User.query.filter_by(role='engineer', is_active=True).all()
    if not engineers:
        return None

    # Pick engineer with least open tickets
    best = min(
        engineers,
        key=lambda e: Ticket.query.filter_by(
            assigned_to=e.id
        ).filter(Ticket.status.notin_(['resolved', 'closed'])).count()
    )
    return best

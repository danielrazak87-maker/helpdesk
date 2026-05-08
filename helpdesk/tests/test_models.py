"""
Unit tests for data models: User, Ticket, SLA, Notification, Escalation, Attendance.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from app import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
from app.models.user import User
from app.models.ticket import Ticket, TicketComment, TicketHistory
from app.models.sla import SLAPolicy
from app.models.escalation import EscalationRule, EscalationLog
from app.models.attendance import Attendance
from app.models.notification import Notification


class TestUserModel:
    def test_create_user(self, db_session):
        user = User(
            email='new@test.com',
            full_name='New User',
            role='user',
            is_active=True
        )
        user.set_password('Test@1234')
        db_session.add(user)
        db_session.commit()

        saved = User.query.filter_by(email='new@test.com').first()
        assert saved is not None
        assert saved.full_name == 'New User'
        assert saved.role == 'user'
        assert saved.is_active is True
        assert saved.check_password('Test@1234') is True
        assert saved.check_password('wrong') is False
        assert saved.password_updated_at is not None

    def test_role_methods(self, admin_user, engineer_user, regular_user):
        assert admin_user.is_admin() is True
        assert admin_user.is_engineer() is False
        assert admin_user.is_user() is False

        assert engineer_user.is_admin() is False
        assert engineer_user.is_engineer() is True
        assert engineer_user.is_user() is False

        assert regular_user.is_admin() is False
        assert regular_user.is_engineer() is False
        assert regular_user.is_user() is True

    def test_repr(self, regular_user):
        assert repr(regular_user) == f'<User {regular_user.email}>'

    def test_unread_count(self, db_session, regular_user):
        # Create some notifications
        for i in range(3):
            n = Notification(
                user_id=regular_user.id,
                title=f'Notification {i}',
                message=f'Message {i}',
                is_read=(i == 0)  # first one read
            )
            db_session.add(n)
        db_session.commit()
        assert regular_user.unread_notification_count() == 2


class TestTicketModel:
    def test_create_ticket(self, db_session, regular_user, engineer_user):
        ticket = Ticket(
            ticket_number=Ticket.generate_ticket_number(),
            title='Network Down',
            description='Unable to connect to network',
            status='open',
            priority='critical',
            category='network',
            project='Test Project',
            created_by=regular_user.id,
            assigned_to=engineer_user.id
        )
        db_session.add(ticket)
        db_session.commit()

        assert ticket.id is not None
        assert ticket.ticket_number.startswith('HD-')
        assert ticket.sla_status() == 'on_track'
        assert ticket.sla_percent() >= 0
        assert ticket.resolution_time_mins() is None

    def test_generate_ticket_number(self):
        num = Ticket.generate_ticket_number()
        assert num.startswith('HD-')
        parts = num.split('-')
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 4  # random suffix

    def test_repr(self, sample_ticket):
        assert repr(sample_ticket) == f'<Ticket {sample_ticket.ticket_number}>'

    def test_sla_status_resolved(self, db_session, regular_user, engineer_user):
        ticket = Ticket(
            ticket_number=Ticket.generate_ticket_number(),
            title='Test',
            description='Test',
            status='resolved',
            created_by=regular_user.id,
            assigned_to=engineer_user.id
        )
        db_session.add(ticket)
        db_session.commit()
        assert ticket.sla_status() == 'resolved'

    def test_sla_status_breached(self, db_session, regular_user, engineer_user):
        ticket = Ticket(
            ticket_number=Ticket.generate_ticket_number(),
            title='Test',
            description='Test',
            status='open',
            sla_breached=True,
            created_by=regular_user.id,
            assigned_to=engineer_user.id
        )
        db_session.add(ticket)
        db_session.commit()
        assert ticket.sla_status() == 'breached'

    def test_sla_remaining_mins(self, db_session, regular_user, engineer_user):
        from datetime import timedelta
        ticket = Ticket(
            ticket_number=Ticket.generate_ticket_number(),
            title='Test',
            description='Test',
            status='open',
            created_by=regular_user.id,
            assigned_to=engineer_user.id,
            sla_resolution_due=_utcnow() + timedelta(hours=2)
        )
        db_session.add(ticket)
        db_session.commit()
        rem = ticket.sla_remaining_mins()
        assert rem is not None
        assert 110 <= rem <= 130  # allow some test timing drift

    def test_resolution_time(self, db_session, regular_user, engineer_user):
        from datetime import timedelta
        created = _utcnow() - timedelta(hours=3)
        resolved = _utcnow()
        ticket = Ticket(
            ticket_number=Ticket.generate_ticket_number(),
            title='Test',
            description='Test',
            status='resolved',
            created_by=regular_user.id,
            assigned_to=engineer_user.id,
            created_at=created,
            resolved_at=resolved
        )
        db_session.add(ticket)
        db_session.commit()
        mins = ticket.resolution_time_mins()
        assert mins is not None
        assert 170 <= mins <= 190  # ~3 hours


class TestSLAPolicyModel:
    def test_create_sla(self, db_session):
        sla = SLAPolicy(
            name='Critical SLA',
            priority='critical',
            response_time_mins=15,
            resolution_time_mins=60,
            escalate_on_breach=True
        )
        db_session.add(sla)
        db_session.commit()
        assert sla.response_hours() == round(15/60, 1)  # 0.3
        assert sla.resolution_hours() == 1.0  # 60/60
        assert sla.resolution_hours() == 1.0  # 60/60

    def test_repr(self, sample_sla):
        assert repr(sample_sla) == f'<SLAPolicy {sample_sla.name}>'


class TestNotificationModel:
    def test_create_notification(self, db_session, regular_user, sample_ticket):
        n = Notification(
            user_id=regular_user.id,
            ticket_id=sample_ticket.id,
            title='Test Notification',
            message='This is a test',
            type='info'
        )
        db_session.add(n)
        db_session.commit()
        assert n.is_read is False

    def test_repr(self, db_session, regular_user):
        n = Notification(user_id=regular_user.id, title='Test', message='Test')
        db_session.add(n)
        db_session.commit()
        assert repr(n) == f'<Notification User#{regular_user.id}>'


class TestEscalationModel:
    def test_create_rule_and_log(self, db_session, sample_sla, admin_user):
        rule = EscalationRule(
            sla_policy_id=sample_sla.id,
            escalate_to=admin_user.id,
            trigger_after_mins=120,
            escalation_level=1
        )
        db_session.add(rule)
        db_session.commit()

        log = EscalationLog(
            ticket_id=1,
            escalated_to=admin_user.id,
            escalation_level=1,
            reason='SLA threshold exceeded'
        )
        db_session.add(log)
        db_session.commit()

        assert repr(rule) == f'<EscalationRule Level {rule.escalation_level}>'
        assert repr(log) == f'<EscalationLog Ticket#1 L1>'


class TestAttendanceModel:
    def test_create_attendance(self, db_session, engineer_user):
        from datetime import date
        # Use a past date to avoid unique constraint with other tests
        att = Attendance(
            engineer_id=engineer_user.id,
            work_date=date(2025, 1, 10),
            check_in=_utcnow(),
            status='present'
        )
        db_session.add(att)
        db_session.commit()

        assert att.working_hours() == 0.0  # no check_out yet
        assert att.is_checked_in() is True

    def test_working_hours(self, db_session, engineer_user):
        from datetime import date, timedelta
        # Use a past date to avoid unique constraint with other tests
        past_date = date(2025, 1, 15)
        cin = _utcnow() - timedelta(hours=8)
        cout = _utcnow()
        att = Attendance(
            engineer_id=engineer_user.id,
            work_date=past_date,
            check_in=cin,
            check_out=cout,
            status='present'
        )
        db_session.add(att)
        db_session.commit()
        assert 7.5 <= att.working_hours() <= 8.5

    def test_unique_constraint(self, db_session, engineer_user):
        from datetime import date
        # Use a unique date to avoid conflicts
        past_date = date(2025, 2, 20)
        att1 = Attendance(engineer_id=engineer_user.id, work_date=past_date)
        db_session.add(att1)
        db_session.commit()

        with pytest.raises(Exception):
            att2 = Attendance(engineer_id=engineer_user.id, work_date=past_date)
            db_session.add(att2)
            db_session.commit()

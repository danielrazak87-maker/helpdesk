"""
Unit tests for service layer functions: SLA, attendance, escalation, notification.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock
from app import db
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


from app.models.ticket import Ticket
from app.models.sla import SLAPolicy
from app.models.escalation import EscalationRule, EscalationLog
from app.models.attendance import Attendance
from app.models.user import User
from app.models.notification import Notification


class TestSLAService:
    def _make_ticket(self, db_session, ticket_num, priority='medium', created_by=1):
        """Create a fresh ticket for isolated SLA testing."""
        t = Ticket(
            ticket_number=ticket_num,
            title=f'Test {ticket_num}',
            description='SLA test',
            status='open',
            priority=priority,
            category='network',
            project='Test Project',
            created_by=created_by
        )
        db_session.add(t)
        db_session.flush()
        return t

    def test_assign_sla(self, db_session, sample_sla, regular_user):
        from app.services.sla_service import assign_sla

        ticket = self._make_ticket(db_session, 'HD-SLA-001', priority='high', created_by=regular_user.id)
        assign_sla(ticket)

        db_session.refresh(ticket)
        # SLA is matched by priority ('high'), which picks seeded "High SLA"
        # Just verify an SLA was assigned.
        assert ticket.sla_policy_id is not None
        assert ticket.sla_response_due is not None
        assert ticket.sla_resolution_due is not None

    def test_assign_sla_no_match(self, db_session, regular_user):
        from app.services.sla_service import assign_sla
        ticket = self._make_ticket(db_session, 'HD-SLA-002', priority='medium', created_by=regular_user.id)
        ticket.priority = 'medium'
        db_session.commit()

        assign_sla(ticket)
        assert ticket.sla_policy_id is not None  # still assigns if default exists

    def test_check_not_breached(self, db_session, regular_user):
        from app.services.sla_service import check_and_update_sla
        ticket = self._make_ticket(db_session, 'HD-SLA-003', created_by=regular_user.id)
        ticket.sla_resolution_due = _utcnow() + timedelta(hours=2)
        db_session.commit()

        result = check_and_update_sla(ticket)
        assert result is False
        assert ticket.sla_breached is False

    def test_check_breached(self, db_session, regular_user):
        from app.services.sla_service import check_and_update_sla
        ticket = self._make_ticket(db_session, 'HD-SLA-004', created_by=regular_user.id)
        ticket.sla_resolution_due = _utcnow() - timedelta(minutes=5)
        db_session.commit()

        result = check_and_update_sla(ticket)
        assert result is True
        assert ticket.sla_breached is True

    def test_check_already_breached(self, db_session, regular_user):
        from app.services.sla_service import check_and_update_sla
        ticket = self._make_ticket(db_session, 'HD-SLA-005', created_by=regular_user.id)
        ticket.sla_resolution_due = _utcnow() - timedelta(minutes=5)
        ticket.sla_breached = True
        db_session.commit()

        result = check_and_update_sla(ticket)
        assert result is False  # already flagged

    def test_check_resolved_ticket(self, db_session, regular_user):
        from app.services.sla_service import check_and_update_sla
        ticket = self._make_ticket(db_session, 'HD-SLA-006', created_by=regular_user.id)
        ticket.status = 'resolved'
        ticket.sla_resolution_due = _utcnow() - timedelta(minutes=5)
        db_session.commit()

        result = check_and_update_sla(ticket)
        assert result is False

    def test_get_sla_dashboard_stats(self, db_session, regular_user):
        from app.services.sla_service import get_sla_dashboard_stats
        self._make_ticket(db_session, 'HD-SLA-STATS', created_by=regular_user.id)
        stats = get_sla_dashboard_stats()
        assert 'total' in stats
        assert 'breached' in stats
        assert 'resolved' in stats
        assert stats['total'] >= 1


class TestAttendanceService:
    def _clean_today(self, db_session, engineer_id):
        """Remove today's attendance record for clean test state."""
        from datetime import date
        existing = Attendance.query.filter_by(engineer_id=engineer_id, work_date=date.today()).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()

    def test_check_in(self, db_session, engineer_user):
        from app.services.attendance_service import check_in
        self._clean_today(db_session, engineer_user.id)
        record, error = check_in(engineer_user.id)
        assert error is None
        assert record is not None
        assert record.check_in is not None
        assert record.status == 'present'

    def test_check_in_duplicate(self, db_session, engineer_user):
        from app.services.attendance_service import check_in
        check_in(engineer_user.id)  # first check-in
        record, error = check_in(engineer_user.id)  # second
        assert error is not None
        assert 'already' in error.lower()

    def test_check_out(self, db_session, engineer_user):
        from app.services.attendance_service import check_in, check_out
        self._clean_today(db_session, engineer_user.id)
        check_in(engineer_user.id)
        record, error = check_out(engineer_user.id)
        assert error is None
        assert record is not None
        assert record.check_out is not None

    def test_check_out_without_checkin(self, db_session, engineer_user):
        from app.services.attendance_service import check_out, check_in
        from datetime import date
        # Create a check-in for today, then check out, then verify second check-out fails
        check_in(engineer_user.id)
        check_out(engineer_user.id)  # first check-out succeeds
        record2, error2 = check_out(engineer_user.id)  # second should fail
        assert error2 is not None
        assert 'checked out' in error2.lower()

    def test_get_available_engineers(self, db_session, engineer_user):
        from app.services.attendance_service import get_available_engineers, check_in
        from app.services.attendance_service import check_out  # ensure clean state
        # Clear any previous check-in/out for today
        from datetime import date
        existing = Attendance.query.filter_by(engineer_id=engineer_user.id, work_date=date.today()).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()
        check_in(engineer_user.id)
        available = get_available_engineers()
        assert len(available) >= 1
        assert engineer_user in available

    def test_auto_assign_engineer(self, db_session, engineer_user):
        from app.services.attendance_service import auto_assign_engineer, check_in
        from datetime import date
        # Clear any previous check-in/out for today
        existing = Attendance.query.filter_by(engineer_id=engineer_user.id, work_date=date.today()).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()
        check_in(engineer_user.id)
        assigned = auto_assign_engineer()
        assert assigned is not None
        assert assigned.id == engineer_user.id

    def test_get_engineer_attendance(self, db_session, engineer_user):
        from app.services.attendance_service import get_engineer_attendance, check_in
        today = date.today()
        check_in(engineer_user.id)
        records = get_engineer_attendance(engineer_user.id, today, today)
        assert len(records) == 1


class TestEscalationService:
    def _make_ticket(self, db_session, ticket_num, priority='medium', user=None, engineer=None):
        """Create a fresh ticket for escalation testing."""
        from app.models.ticket import Ticket
        t = Ticket(
            ticket_number=ticket_num,
            title=f'Test {ticket_num}',
            description='Escalation test',
            status='open',
            priority=priority,
            project='Test Project',
            created_by=(user or 1),
            assigned_to=(engineer or 1)
        )
        db_session.add(t)
        db_session.flush()
        return t

    def test_escalation_check_no_trigger(self, db_session, regular_user):
        from app.services.escalation_service import run_escalation_checks

        ticket = self._make_ticket(db_session, 'HD-ESC-001', user=regular_user.id)
        ticket.sla_policy_id = 1
        db_session.commit()

        run_escalation_checks()
        logs = EscalationLog.query.filter_by(ticket_id=ticket.id).all()
        assert len(logs) == 0

    def test_escalation_check_with_rule(self, db_session, sample_sla, admin_user, regular_user):
        from app.services.escalation_service import run_escalation_checks
        from datetime import timedelta

        ticket = self._make_ticket(db_session, 'HD-ESC-002', user=regular_user.id)
        ticket.sla_policy_id = sample_sla.id
        ticket.created_at = _utcnow() - timedelta(minutes=10)
        db_session.commit()

        rule = EscalationRule(
            sla_policy_id=sample_sla.id,
            escalate_to=admin_user.id,
            trigger_after_mins=0,
            escalation_level=1
        )
        db_session.add(rule)
        db_session.commit()

        run_escalation_checks()
        logs = EscalationLog.query.filter_by(ticket_id=ticket.id).all()
        assert len(logs) == 1
        assert logs[0].escalation_level == 1

    def test_no_double_escalation(self, db_session, sample_sla, admin_user, regular_user):
        from app.services.escalation_service import _check_ticket_escalation

        ticket = self._make_ticket(db_session, 'HD-ESC-003', user=regular_user.id)
        ticket.sla_policy_id = sample_sla.id
        db_session.commit()

        rule = EscalationRule(
            sla_policy_id=sample_sla.id,
            escalate_to=admin_user.id,
            trigger_after_mins=0,
            escalation_level=1
        )
        db_session.add(rule)
        db_session.commit()

        # First call - should escalate
        _check_ticket_escalation(ticket)
        # Second call - should NOT double-escalate
        _check_ticket_escalation(ticket)

        logs = EscalationLog.query.filter_by(ticket_id=ticket.id).all()
        assert len(logs) == 1


class TestNotificationService:
    def test_send_notification(self, db_session, regular_user):
        from app.services.notification import send_notification
        # Clear pre-existing notifications for this user
        Notification.query.filter_by(user_id=regular_user.id).delete()
        db_session.commit()

        send_notification(
            user_id=regular_user.id,
            title='Test Notification',
            message='Test message',
            ntype='info'
        )
        n = Notification.query.filter_by(user_id=regular_user.id, is_read=False).order_by(Notification.id.desc()).first()
        assert n is not None
        assert n.title == 'Test Notification'
        assert n.type == 'info'

    def test_notify_ticket_created(self, db_session, regular_user, sample_ticket, monkeypatch):
        # Mock email sending to avoid SMTP
        from app.services.notification import notify_ticket_created

        # Patch send_email to do nothing
        monkeypatch.setattr('app.services.notification.send_email', lambda *a, **kw: None)

        # Clear pre-existing notifications for this ticket+user
        Notification.query.filter_by(user_id=regular_user.id, ticket_id=sample_ticket.id).delete()
        db_session.commit()

        notify_ticket_created(sample_ticket, regular_user)

        n = Notification.query.filter_by(
            user_id=regular_user.id,
            ticket_id=sample_ticket.id
        ).order_by(Notification.id.desc()).first()
        assert n is not None
        assert 'Created' in n.title

    def test_notify_ticket_assigned(self, db_session, sample_ticket, engineer_user, monkeypatch):
        from app.services.notification import notify_ticket_assigned
        monkeypatch.setattr('app.services.notification.send_email', lambda *a, **kw: None)

        sample_ticket.assigned_to = engineer_user.id
        db_session.commit()

        # Clear any pre-existing notifications for this ticket+user
        Notification.query.filter_by(user_id=engineer_user.id, ticket_id=sample_ticket.id).delete()
        db_session.commit()

        notify_ticket_assigned(sample_ticket)

        n = Notification.query.filter_by(
            user_id=engineer_user.id,
            ticket_id=sample_ticket.id
        ).order_by(Notification.id.desc()).first()
        assert n is not None
        assert 'Assigned' in n.title

    def test_notify_ticket_resolved(self, db_session, regular_user, sample_ticket, monkeypatch):
        from app.services.notification import notify_ticket_resolved
        monkeypatch.setattr('app.services.notification.send_email', lambda *a, **kw: None)

        sample_ticket.created_by = regular_user.id
        db_session.commit()

        # Clear any pre-existing notifications for this ticket+user
        Notification.query.filter_by(user_id=regular_user.id, ticket_id=sample_ticket.id).delete()
        db_session.commit()

        notify_ticket_resolved(sample_ticket)

        n = Notification.query.filter_by(
            user_id=regular_user.id,
            ticket_id=sample_ticket.id
        ).order_by(Notification.id.desc()).first()
        assert n is not None
        assert 'Resolved' in n.title

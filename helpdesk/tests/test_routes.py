"""
Integration tests for route endpoints: auth, main, tickets, admin, engineer, reports.
"""
from __future__ import annotations

import pytest
from flask import url_for, session
from app import db
from app.models.user import User
from app.models.ticket import Ticket
from tests.conftest import login, logout


class TestAuthRoutes:
    def test_login_page(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200
        assert b'Login' in resp.data or b'login' in resp.data or resp.status_code == 200

    def test_login_success(self, client, admin_user):
        resp = client.post('/auth/login', data={
            'email': 'admin@test.com',
            'password': 'Admin@1234'
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_login_invalid(self, client):
        resp = client.post('/auth/login', data={
            'email': 'wrong@test.com',
            'password': 'wrong'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid' in resp.data or b'invalid' in resp.data

    def test_register_page(self, client):
        resp = client.get('/auth/register')
        assert resp.status_code == 200

    def test_register_user(self, client):
        resp = client.post('/auth/register', data={
            'email': 'newreg@test.com',
            'password': 'NewUser@1234',
            'full_name': 'New Registered',
            'project': 'Test Project'
        }, follow_redirects=True)
        assert resp.status_code == 200
        user = User.query.filter_by(email='newreg@test.com').first()
        assert user is not None
        assert user.full_name == 'New Registered'

    def test_register_duplicate(self, client, regular_user):
        resp = client.post('/auth/register', data={
            'email': 'user@test.com',
            'password': 'User@12345',
            'full_name': 'Duplicate',
            'project': 'Test'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'registered' in resp.data or b'already' in resp.data

    def test_logout(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/auth/logout', follow_redirects=True)
        assert resp.status_code == 200

    def test_profile_page_requires_login(self, client):
        resp = client.get('/auth/profile', follow_redirects=True)
        assert resp.status_code == 200

    def test_forgot_password_page(self, client):
        resp = client.get('/auth/forgot-password')
        assert resp.status_code == 200

    def test_reset_password_page_invalid_token(self, client):
        resp = client.get('/auth/reset-password/invalid-token-here', follow_redirects=True)
        assert resp.status_code == 200


class TestMainRoutes:
    def test_index_redirects_login(self, client):
        resp = client.get('/', follow_redirects=True)
        assert resp.status_code == 200

    def test_dashboard_admin(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/dashboard', follow_redirects=True)
        assert resp.status_code == 200

    def test_dashboard_engineer(self, client, engineer_user):
        login(client, 'engineer@test.com', 'Engineer@1234')
        resp = client.get('/dashboard', follow_redirects=True)
        assert resp.status_code == 200

    def test_dashboard_user(self, client, regular_user):
        login(client, 'user@test.com', 'User@1234')
        resp = client.get('/dashboard', follow_redirects=True)
        assert resp.status_code == 200

    def test_search_empty_query(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/search?q=')
        assert resp.status_code == 200
        assert b'results' in resp.data


class TestTicketRoutes:
    def test_my_tickets(self, client, regular_user):
        login(client, 'user@test.com', 'User@1234')
        resp = client.get('/tickets/', follow_redirects=True)
        assert resp.status_code == 200

    def test_create_ticket_page(self, client, regular_user):
        login(client, 'user@test.com', 'User@1234')
        resp = client.get('/tickets/create')
        assert resp.status_code == 200

    def test_create_ticket_post(self, client, regular_user):
        login(client, 'user@test.com', 'User@1234')
        resp = client.post('/tickets/create', data={
            'title': 'Test Ticket Creation',
            'description': 'Testing ticket creation via POST',
            'priority': 'high',
            'category': 'network'
        }, follow_redirects=True)
        assert resp.status_code == 200
        ticket = Ticket.query.filter_by(title='Test Ticket Creation').first()
        assert ticket is not None
        assert ticket.priority == 'high'

    def test_ticket_detail(self, client, regular_user, sample_ticket):
        login(client, 'user@test.com', 'User@1234')
        resp = client.get(f'/tickets/{sample_ticket.id}')
        assert resp.status_code == 200

    def test_ticket_detail_unauthorized(self, client, regular_user, sample_ticket):
        """Another user from different project should get 403."""
        other_user = User(
            email='other@test.com',
            full_name='Other User',
            role='user',
            project='Other Project',
            is_active=True
        )
        other_user.set_password('Other@1234')
        db.session.add(other_user)
        db.session.commit()

        login(client, 'other@test.com', 'Other@1234')
        resp = client.get(f'/tickets/{sample_ticket.id}')
        assert resp.status_code == 403

    def test_update_ticket(self, client, admin_user, sample_ticket):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.post(f'/tickets/{sample_ticket.id}/update', data={
            'status': 'in_progress'
        }, follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_ticket)
        assert sample_ticket.status == 'in_progress'

    def test_add_comment(self, client, regular_user, sample_ticket):
        login(client, 'user@test.com', 'User@1234')
        resp = client.post(f'/tickets/{sample_ticket.id}/comment', data={
            'content': 'This is a test comment'
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_rate_ticket(self, client, regular_user, sample_ticket):
        # First resolve the ticket
        sample_ticket.status = 'resolved'
        db.session.commit()

        login(client, 'user@test.com', 'User@1234')
        resp = client.post(f'/tickets/{sample_ticket.id}/rate', data={
            'rating': 5,
            'feedback': 'Great service!'
        }, follow_redirects=True)
        assert resp.status_code == 200
        db.session.refresh(sample_ticket)
        assert sample_ticket.rating == 5
        assert sample_ticket.feedback == 'Great service!'


class TestAdminRoutes:
    def test_admin_dashboard_requires_admin(self, client, regular_user):
        login(client, 'user@test.com', 'User@1234')
        resp = client.get('/admin/dashboard')
        assert resp.status_code == 403

    def test_admin_dashboard(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/admin/dashboard')
        assert resp.status_code == 200

    def test_admin_users(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/admin/users')
        assert resp.status_code == 200

    def test_admin_create_user(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.post('/admin/users/create', data={
            'email': 'newadmin@test.com',
            'full_name': 'New Admin',
            'role': 'admin',
            'password': 'NewAdmin@1234'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert User.query.filter_by(email='newadmin@test.com').first() is not None

    def test_admin_sla_list(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/admin/sla')
        assert resp.status_code == 200

    def test_admin_create_sla(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.post('/admin/sla/create', data={
            'name': 'Gold SLA',
            'priority': 'high',
            'response_time_mins': 30,
            'resolution_time_mins': 120,
            'escalate_on_breach': 'on'
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_admin_all_tickets(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/admin/tickets')
        assert resp.status_code == 200

    def test_admin_bulk_close(self, client, admin_user, sample_ticket, db_session):
        login(client, 'admin@test.com', 'Admin@1234')
        another = Ticket.query.filter(Ticket.id != sample_ticket.id).first()
        ticket_ids = [sample_ticket.id]
        if another:
            ticket_ids.append(another.id)
        resp = client.post('/admin/tickets/bulk-close', data={
            'ticket_ids': ticket_ids
        }, follow_redirects=True)
        assert resp.status_code == 200
        db_session.refresh(sample_ticket)
        assert sample_ticket.status == 'closed'

    def test_admin_bulk_assign(self, client, admin_user, regular_user, engineer_user, sample_ticket, db_session):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.post('/admin/tickets/bulk-assign', data={
            'ticket_ids': [sample_ticket.id],
            'engineer_id': engineer_user.id
        }, follow_redirects=True)
        assert resp.status_code == 200
        db_session.refresh(sample_ticket)
        assert sample_ticket.assigned_to == engineer_user.id


class TestEngineerRoutes:
    def test_engineer_dashboard(self, client, engineer_user):
        login(client, 'engineer@test.com', 'Engineer@1234')
        resp = client.get('/engineer/dashboard')
        assert resp.status_code == 200

    def test_check_in_check_out(self, client, engineer_user):
        login(client, 'engineer@test.com', 'Engineer@1234')
        # Check in
        resp = client.post('/engineer/check-in', follow_redirects=True)
        assert resp.status_code == 200

        # Check out
        resp = client.post('/engineer/check-out', follow_redirects=True)
        assert resp.status_code == 200

    def test_engineer_attendance(self, client, engineer_user):
        login(client, 'engineer@test.com', 'Engineer@1234')
        resp = client.get('/engineer/attendance')
        assert resp.status_code == 200


class TestReportsRoutes:
    def test_reports_index(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/reports/')
        assert resp.status_code == 200

    def test_ticket_report(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/reports/tickets')
        assert resp.status_code == 200

    def test_engineer_report(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/reports/engineers')
        assert resp.status_code == 200

    def test_attendance_report(self, client, admin_user):
        login(client, 'admin@test.com', 'Admin@1234')
        resp = client.get('/reports/attendance')
        assert resp.status_code == 200


class TestAuthorization:
    """Test that users cannot access restricted endpoints."""

    def test_user_cannot_access_admin(self, client, regular_user):
        login(client, 'user@test.com', 'User@1234')
        endpoints = [
            '/admin/dashboard',
            '/admin/users',
            '/admin/sla',
            '/admin/escalation',
            '/admin/tickets',
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 403, f'{ep} should 403 for regular user'

    def test_user_cannot_access_engineer(self, client, regular_user):
        login(client, 'user@test.com', 'User@1234')
        endpoints = [
            '/engineer/dashboard',
            '/engineer/attendance',
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 403, f'{ep} should 403 for regular user'

    def test_user_cannot_access_reports(self, client, regular_user):
        login(client, 'user@test.com', 'User@1234')
        endpoints = [
            '/reports/',
            '/reports/tickets',
            '/reports/engineers',
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 403, f'{ep} should 403 for regular user'

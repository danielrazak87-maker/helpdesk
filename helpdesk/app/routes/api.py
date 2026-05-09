from __future__ import annotations
from flask import Blueprint, request, jsonify, abort
from flask_login import current_user, login_required
from functools import wraps
from app import db
from app.models.ticket import Ticket, TicketComment, TICKET_STATUSES, TICKET_PRIORITIES
from app.models.user import User
from app.models.api_token import ApiToken
from datetime import datetime

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

def api_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        token_string = auth_header.split(' ')[1]
        user = ApiToken.get_user_from_token(token_string)
        if not user:
            return jsonify({'error': 'Invalid or inactive token'}), 401
        # Attach user to request context
        request.api_user = user
        return f(*args, **kwargs)
    return decorated

# Ticket Endpoints
@api_bp.route('/tickets', methods=['GET'])
@api_auth_required
def list_tickets():
    user = request.api_user
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    priority = request.args.get('priority')

    query = Ticket.query
    if status and status in TICKET_STATUSES:
        query = query.filter_by(status=status)
    if priority and priority in TICKET_PRIORITIES:
        query = query.filter_by(priority=priority)
    # Restrict non-admins to their own tickets or assigned tickets
    if not user.is_admin() and not user.is_engineer():
        query = query.filter_by(project=user.project)
    elif user.is_engineer():
        query = query.filter((Ticket.assigned_to == user.id) | (Ticket.created_by == user.id))

    paginated = query.order_by(Ticket.created_at.desc()).paginate(page=page, per_page=per_page)
    return jsonify({
        'tickets': [{
            'id': t.id,
            'ticket_number': t.ticket_number,
            'title': t.title,
            'status': t.status,
            'priority': t.priority,
            'category': t.category,
            'created_at': t.created_at.isoformat(),
            'sla_breached': t.sla_breached
        } for t in paginated.items],
        'total': paginated.total,
        'page': paginated.page,
        'per_page': paginated.per_page,
        'pages': paginated.pages
    })

@api_bp.route('/tickets/<int:ticket_id>', methods=['GET'])
@api_auth_required
def get_ticket(ticket_id):
    user = request.api_user
    ticket = Ticket.query.get_or_404(ticket_id)
    # Check access
    if user.is_user() and ticket.project != user.project:
        return jsonify({'error': 'Forbidden'}), 403
    if user.is_engineer() and ticket.assigned_to != user.id and ticket.created_by != user.id:
        return jsonify({'error': 'Forbidden'}), 403

    return jsonify({
        'id': ticket.id,
        'ticket_number': ticket.ticket_number,
        'title': ticket.title,
        'description': ticket.description,
        'status': ticket.status,
        'priority': ticket.priority,
        'category': ticket.category,
        'project': ticket.project,
        'created_by': ticket.created_by,
        'assigned_to': ticket.assigned_to,
        'created_at': ticket.created_at.isoformat(),
        'updated_at': ticket.updated_at.isoformat(),
        'sla_breached': ticket.sla_breached,
        'comments': [{
            'id': c.id,
            'content': c.content,
            'is_internal': c.is_internal,
            'created_at': c.created_at.isoformat(),
            'user': c.user_id
        } for c in ticket.comments if not c.is_internal or not user.is_user()]
    })

@api_bp.route('/tickets', methods=['POST'])
@api_auth_required
def create_ticket():
    user = request.api_user
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    data = request.get_json()
    required = ['title', 'description', 'priority', 'category']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    if user.is_user():
        data['project'] = user.project
    else:
        if 'project' not in data:
            return jsonify({'error': 'Project is required for non-user tickets'}), 400

    from app.models.ticket import Ticket
    ticket = Ticket(
        ticket_number=Ticket.generate_ticket_number(),
        title=data['title'],
        description=data['description'],
        priority=data['priority'],
        category=data['category'],
        project=data['project'],
        created_by=user.id,
        status='open'
    )
    db.session.add(ticket)
    db.session.commit()

    from app.services.sla_service import assign_sla
    assign_sla(ticket)
    from app.services.attendance_service import auto_assign_engineer
    engineer = auto_assign_engineer()
    if engineer:
        ticket.assigned_to = engineer.id
    db.session.commit()

    return jsonify({
        'id': ticket.id,
        'ticket_number': ticket.ticket_number,
        'message': 'Ticket created successfully'
    }), 201

@api_bp.route('/tickets/<int:ticket_id>', methods=['PATCH'])
@api_auth_required
def update_ticket(ticket_id):
    user = request.api_user
    ticket = Ticket.query.get_or_404(ticket_id)
    # Check access: admin, assigned engineer, or creator
    if not user.is_admin() and ticket.assigned_to != user.id and ticket.created_by != user.id:
        return jsonify({'error': 'Forbidden'}), 403

    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    data = request.get_json()

    allowed_fields = ['status', 'assigned_to', 'priority']
    for field in allowed_fields:
        if field in data:
            setattr(ticket, field, data[field])
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Ticket updated successfully'})

@api_bp.route('/tickets/<int:ticket_id>', methods=['DELETE'])
@api_auth_required
def delete_ticket(ticket_id):
    user = request.api_user
    ticket = Ticket.query.get_or_404(ticket_id)
    # Only admin or ticket creator can delete
    if not user.is_admin() and ticket.created_by != user.id:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(ticket)
    db.session.commit()
    return jsonify({'message': 'Ticket deleted successfully'})

# User Endpoints
@api_bp.route('/users', methods=['GET'])
@api_auth_required
def list_users():
    user = request.api_user
    if not user.is_admin() and not user.is_engineer():
        return jsonify({'error': 'Forbidden'}), 403
    users = User.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': u.id,
        'full_name': u.full_name,
        'email': u.email,
        'role': u.role,
        'department': u.department
    } for u in users])

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@api_auth_required
def get_user(user_id):
    user = request.api_user
    if not user.is_admin() and not user.is_engineer() and user.id != user_id:
        return jsonify({'error': 'Forbidden'}), 403
    target = User.query.get_or_404(user_id)
    return jsonify({
        'id': target.id,
        'full_name': target.full_name,
        'email': target.email,
        'role': target.role,
        'department': target.department,
        'is_active': target.is_active
    })

# Comment Endpoints
@api_bp.route('/tickets/<int:ticket_id>/comments', methods=['GET'])
@api_auth_required
def list_comments(ticket_id):
    user = request.api_user
    ticket = Ticket.query.get_or_404(ticket_id)
    # Check access
    if user.is_user() and ticket.project != user.project:
        return jsonify({'error': 'Forbidden'}), 403
    comments = ticket.comments.order_by(TicketComment.created_at.asc()).all()
    return jsonify([{
        'id': c.id,
        'content': c.content,
        'is_internal': c.is_internal,
        'created_at': c.created_at.isoformat(),
        'user_id': c.user_id
    } for c in comments if not c.is_internal or not user.is_user()])

@api_bp.route('/tickets/<int:ticket_id>/comments', methods=['POST'])
@api_auth_required
def add_comment(ticket_id):
    user = request.api_user
    ticket = Ticket.query.get_or_404(ticket_id)
    # Check access
    if user.is_user() and ticket.project != user.project:
        return jsonify({'error': 'Forbidden'}), 403
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    data = request.get_json()
    if 'content' not in data:
        return jsonify({'error': 'Missing content field'}), 400

    is_internal = data.get('is_internal', False)
    if user.is_user():
        is_internal = False

    comment = TicketComment(
        ticket_id=ticket_id,
        user_id=user.id,
        content=data['content'],
        is_internal=is_internal
    )
    db.session.add(comment)
    # Update SLA responded if engineer
    if user.is_engineer() and not ticket.sla_responded_at:
        ticket.sla_responded_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Comment added successfully', 'id': comment.id}), 201

# Token Management (Admin-only)
@api_bp.route('/tokens', methods=['GET'])
@api_auth_required
def list_tokens():
    user = request.api_user
    if not user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    tokens = ApiToken.query.filter_by(user_id=user.id).all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'is_active': t.is_active,
        'last_used_at': t.last_used_at.isoformat() if t.last_used_at else None,
        'created_at': t.created_at.isoformat()
    } for t in tokens])

@api_bp.route('/tokens', methods=['POST'])
@api_auth_required
def create_token():
    user = request.api_user
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    data = request.get_json()
    name = data.get('name', 'Default Token')

    token_str = ApiToken.generate_token()
    token = ApiToken(
        user_id=user.id,
        token=token_str,
        name=name
    )
    db.session.add(token)
    db.session.commit()
    return jsonify({
        'id': token.id,
        'token': token_str,
        'name': token.name,
        'message': 'Token created. Store this token securely, it will not be shown again.'
    }), 201

@api_bp.route('/tokens/<int:token_id>', methods=['DELETE'])
@api_auth_required
def revoke_token(token_id):
    user = request.api_user
    token = ApiToken.query.get_or_404(token_id)
    if token.user_id != user.id and not user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    token.is_active = False
    db.session.commit()
    return jsonify({'message': 'Token revoked successfully'})

from __future__ import annotations
from app import db, utcnow
import secrets

class ApiToken(db.Model):
    __tablename__ = 'api_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User', backref=db.backref('api_tokens', lazy='dynamic'))

    @staticmethod
    def generate_token():
        return secrets.token_hex(32)

    @staticmethod
    def get_user_from_token(token_string):
        token = ApiToken.query.filter_by(token=token_string, is_active=True).first()
        return token.user if token else None

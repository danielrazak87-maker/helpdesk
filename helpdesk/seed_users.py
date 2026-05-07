import sys
import os

# Ensure the app can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.user import User

app = create_app()

engineers = [
    {"full_name": "Daniel", "email": "daniel@kayfalah.com", "role": "engineer", "password": "abc123"},
    {"full_name": "Fattah", "email": "fattah@kayfalah.com", "role": "engineer", "password": "abc123"},
    {"full_name": "Muhaimin", "email": "muhaimin@kayfalah.com", "role": "engineer", "password": "abc123"},
    {"full_name": "Faris", "email": "faris@kayfalah.com", "role": "engineer", "password": "abc123"}
]

users = [
    {"full_name": "Saril", "email": "saril@kayfalah.com", "role": "user", "password": "abc123", "project": "Project A"},
    {"full_name": "Abul", "email": "abul@kayfalah.com", "role": "user", "password": "abc123", "project": "Project B"}
]

with app.app_context():
    for data in engineers + users:
        existing = User.query.filter_by(email=data['email']).first()
        if not existing:
            u = User(
                full_name=data['full_name'],
                email=data['email'],
                role=data['role']
            )
            if 'project' in data:
                u.project = data['project']
            u.set_password(data['password'])
            db.session.add(u)
    
    db.session.commit()
    print("Users seeded successfully!")

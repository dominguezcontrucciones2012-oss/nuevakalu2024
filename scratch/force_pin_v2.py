import sys
import os
sys.path.append(os.getcwd())

from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin:
        admin.pin = 'kalu2024'
        admin.password = generate_password_hash('kalu2024', method='pbkdf2:sha256')
        admin.role = 'admin'
        db.session.commit()
        print(f"DEBUG: Success for {admin.username}")
    else:
        print("DEBUG: Admin not found")

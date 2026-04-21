from app import app, db
from models import User, Proveedor
from werkzeug.security import generate_password_hash

with app.app_context():
    # Check if user already exists
    u = User.query.filter_by(username='dersy').first()
    if not u:
        u = User(
            username='dersy', 
            password=generate_password_hash('dersy2024'), 
            role='productor', 
            proveedor_id=1
        )
        db.session.add(u)
        db.session.commit()
        print('User dersy created and linked to producer 1')
    else:
        u.role = 'productor'
        u.proveedor_id = 1
        db.session.commit()
        print('User dersy updated and linked to producer 1')

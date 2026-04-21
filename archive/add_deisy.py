from app import app
from models import db, User

with app.app_context():
    name = "deisy corro"
    email = "deisycorro77@gmail.com"
    
    # Buscar si ya existe
    u = User.query.filter(User.username.ilike(f'%{name}%')).first()
    
    if u:
        print(f"User {u.username} found. Updating role to 'admin' and setting email.")
        u.role = 'admin'
        u.email = email
    else:
        print(f"User {name} not found. Creating new admin user.")
        # Asignar una contraseña por defecto (aunque usará Google)
        from werkzeug.security import generate_password_hash
        u = User(
            username=name,
            role='admin',
            email=email,
            password=generate_password_hash("kalu2024") # Password temporal
        )
        db.session.add(u)
        
    db.session.commit()
    print("Operation complete.")

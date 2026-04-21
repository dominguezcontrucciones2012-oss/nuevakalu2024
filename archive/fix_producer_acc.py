from app import app, db
from models import User, Proveedor
from werkzeug.security import generate_password_hash

with app.app_context():
    # Fix account for Producer ID 1
    p = Proveedor.query.get(1)
    if p:
        username = p.rif # 11120033
        password = username[-4:] # 0033
        
        # Check if there is already a user with this RIF
        u_rif = User.query.filter_by(username=username).first()
        if u_rif:
            u_rif.password = generate_password_hash(password)
            u_rif.proveedor_id = p.id
            u_rif.role = 'productor'
            print(f"Updated existing user {username} with new password {password}")
        else:
            # Check user 'dersy'
            u_dersy = User.query.filter_by(username='dersy').first()
            if u_dersy:
                u_dersy.username = username
                u_dersy.password = generate_password_hash(password)
                print(f"Renamed user 'dersy' to {username} and set password {password}")
            else:
                # Create new
                new_u = User(
                    username=username,
                    password=generate_password_hash(password),
                    role='productor',
                    proveedor_id=p.id
                )
                db.session.add(new_u)
                print(f"Created new user {username} for producer {p.nombre}")
        
    db.session.commit()

from app import app
from models import db, User

with app.app_context():
    email = "dominguezcontrucciones2012@gmail.com"
    
    # 1. Encontrar al usuario actual con ese email
    u_admin = User.query.filter_by(email=email).first()
    if u_admin:
        print(f"User {u_admin.username} currently has the email. Removing it to avoid conflict.")
        u_admin.email = None
    
    # 2. Encontrar a Juan Dominguez y asignarle el correo y el rol de dueño
    u_juan = User.query.filter(User.username.ilike('%juan dominguez%')).first()
    if u_juan:
        print(f"Updating {u_juan.username}: Role -> dueno, Email -> {email}")
        u_juan.role = 'dueno'
        u_juan.email = email
    else:
        print("User 'juan dominguez' not found!")
        
    db.session.commit()
    print("Update complete.")

from app import app, db
from models import User
from werkzeug.security import generate_password_hash

def force_kalu_pin():
    with app.app_context():
        # Reset para el admin
        admin = User.query.filter_by(username='admin').first()
        if admin:
            admin.pin = 'kalu2024'
            admin.password = generate_password_hash('kalu2024', method='pbkdf2:sha256')
            admin.role = 'admin'
            print(f"DEBUG: Admin {admin.username} updated. PIN: {admin.pin}, Role: {admin.role}")
        
        # Opcional: Si hay un usuario 'supervisor', también resetearlo
        supervisor = User.query.filter_by(role='supervisor').first()
        if supervisor:
            supervisor.pin = 'kalu2024'
            print(f"DEBUG: Supervisor {supervisor.username} updated. PIN: {supervisor.pin}")
        
        db.session.commit()
        print("FORCED_RESET_SUCCESSFUL")

if __name__ == "__main__":
    force_kalu_pin()

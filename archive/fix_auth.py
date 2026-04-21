import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from app import app
    from models import db, User
    from werkzeug.security import generate_password_hash

    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if admin:
            admin.password = generate_password_hash('kalu2024')
            admin.pin = 'kalu2024'
            db.session.commit()
            print("Successfully updated admin password and PIN to 'kalu2024'")
        else:
            print("Error: admin user not found")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from app import app
    from models import db, User

    with app.app_context():
        users = User.query.all()
        print("Listing all users:")
        for u in users:
            print(f"User: {u.username}, Role: {u.role}, PIN: {u.pin}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

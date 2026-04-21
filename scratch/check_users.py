from app import app
from models import db, User

with app.app_context():
    users = User.query.all()
    print("Listing all users:")
    for u in users:
        print(f"User: {u.username}, Role: {u.role}, PIN: {u.pin}")

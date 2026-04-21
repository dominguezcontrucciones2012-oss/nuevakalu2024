from app import app
from models import User

with app.app_context():
    users = User.query.all()
    print("Listing all users:")
    for u in users:
        print(f"ID: {u.id} | User: {u.username} | Email: {u.email} | Role: {u.role}")

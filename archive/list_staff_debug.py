from app import app
from models import User

with app.app_context():
    users = User.query.filter((User.email != None) | (User.role.in_(['admin', 'dueno', 'cajero', 'supervisor']))).all()
    print("Listing staff and email users:")
    for u in users:
        print(f"ID: {u.id} | User: {u.username} | Email: {u.email} | Role: {u.role}")

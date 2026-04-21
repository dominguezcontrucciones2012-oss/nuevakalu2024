import os
import sys

# Add root to sys.path
sys.path.append(os.getcwd())

from app import app
from models import User

with app.app_context():
    users = User.query.all()
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"ID: {u.id} | Username: {u.username} | CID: {u.cliente_id} | PID: {u.proveedor_id} | Role: {u.role}")

from app import app
from models import db, User

with app.app_context():
    usuarios = User.query.all()
    print("--- LISTADO DE USUARIOS ---")
    for u in usuarios:
        print(f"ID: {u.id} | User: {u.username} | Role: {u.role} | Desc: {u.nombre}")

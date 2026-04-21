from app import app, db
from models import Cliente

with app.app_context():
    print("--- CLIENTES ---")
    clientes = Cliente.query.all()
    for c in clientes:
        print(f"ID: {c.id}, Nombre: {c.nombre}, Cedula: '{c.cedula}'")

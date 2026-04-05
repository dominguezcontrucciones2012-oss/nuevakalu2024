from app import app
from models import User

with app.app_context():
    usuarios = User.query.order_by(User.id).all()

    print("\n===== USUARIOS DEL SISTEMA =====\n")
    if not usuarios:
        print("No hay usuarios registrados.")
    else:
        for u in usuarios:
            print(f"ID: {u.id}")
            print(f"Username: {u.username}")
            print(f"Role: {u.role}")
            print(f"Cliente ID: {u.cliente_id}")
            print(f"Proveedor ID: {u.proveedor_id}")
            print("-" * 40)
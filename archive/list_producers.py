from app import app
from models import Proveedor

with app.app_context():
    productores = Proveedor.query.all()
    print("--- LISTADO DE PRODUCTORES ---")
    for p in productores:
        print(f"ID: {p.id} | Nombre: {p.nombre} | Saldo: {p.saldo_pendiente_usd}")

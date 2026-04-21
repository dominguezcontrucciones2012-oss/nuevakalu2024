from app import app, db
from models import User, Proveedor

with app.app_context():
    print("--- TODOS LOS PROVEEDORES ---")
    proveedores = Proveedor.query.all()
    for p in proveedores:
        print(f"ID: {p.id}, Nombre: {p.nombre}, RIF: '{p.rif}', EsProductor: {p.es_productor}")

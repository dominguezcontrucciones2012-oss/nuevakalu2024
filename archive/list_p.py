from app import app, db
from models import User, Proveedor

with app.app_context():
    print("--- PRODUCTORES ---")
    proveedores = Proveedor.query.filter_by(es_productor=True).all()
    for p in proveedores:
        print(f"ID: {p.id}, Nombre: {p.nombre}, RIF: '{p.rif}'")

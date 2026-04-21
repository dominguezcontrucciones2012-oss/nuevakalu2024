from app import app, db
from models import User, Proveedor

with app.app_context():
    print("--- USUARIOS ---")
    usuarios = User.query.all()
    for u in usuarios:
        print(f"ID: {u.id}, User: '{u.username}', Role: {u.role}, ProvID: {u.proveedor_id}")
    
    print("\n--- PRODUCTORES ---")
    proveedores = Proveedor.query.filter_by(es_productor=True).all()
    for p in proveedores:
        # Check how to access the user
        username = "N/A"
        try:
            if hasattr(p, 'usuario'):
                u = p.usuario
                if isinstance(u, list):
                    username = ", ".join([x.username for x in u]) if u else "None (List empty)"
                else:
                    username = u.username if u else "None"
        except Exception as e:
            username = f"Error: {str(e)}"
            
        print(f"ID: {p.id}, Nombre: {p.nombre}, RIF: '{p.rif}', User: {username}")

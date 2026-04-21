from app import app, db
from models import User, Proveedor

with app.app_context():
    users_productor = User.query.filter_by(role='productor').all()
    print(f"Users with role 'productor': {len(users_productor)}")
    for u in users_productor:
        print(f"  - User ID: {u.id}, Username: {u.username}, Role: {u.role}, Proveedor ID: {u.proveedor_id}")

    producers = Proveedor.query.filter_by(es_productor=True).all()
    print(f"Total producers in Proveedor table: {len(producers)}")
    for p in producers[:10]: # Print first 10 for sample
        print(f"  - Proveedor ID: {p.id}, Nombre: {p.nombre}")
    
    linked_users = User.query.filter(User.proveedor_id.isnot(None)).all()
    print(f"Total users linked to any provider: {len(linked_users)}")
    for u in linked_users:
        print(f"  - User: {u.username}, Linked Proveedor ID: {u.proveedor_id}")

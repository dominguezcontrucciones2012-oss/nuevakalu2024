import json
from app import app
from models import db, Producto, Cliente, Proveedor

def restaurar():
    with app.app_context():
        print("📥 Restaurando datos...")
        
        # Restaurar Productos
        with open('respaldo_productos.json', 'r') as f:
            for p in json.load(f):
                db.session.add(Producto(**p))
            
        # Restaurar Clientes
        with open('respaldo_clientes.json', 'r') as f:
            for c in json.load(f):
                db.session.add(Cliente(**c))
            
        # Restaurar Productores
        with open('respaldo_productores.json', 'r') as f:
            for pr in json.load(f):
                db.session.add(Proveedor(**pr))
            
        db.session.commit()
        print("🚀 ¡SISTEMA REINICIADO! Todo limpio y datos cargados.")

if __name__ == '__main__':
    restaurar()
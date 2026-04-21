import os
import sys
import traceback

# Add root to sys.path
sys.path.append(os.getcwd())

from app import app
from models import db, User, Cliente, Proveedor
from werkzeug.security import generate_password_hash

def sync_users():
    with app.app_context():
        print("--- INICIANDO SINCRONIZACION DE USUARIOS PARA PORTALES ---")
        
        # 1. CLIENTES
        clientes = Cliente.query.all()
        print(f"Procesando {len(clientes)} clientes...")
        c_count = 0
        for c in clientes:
            if not c.cedula or len(c.cedula.strip()) < 4: 
                # print(f"Saltando cliente {c.nombre} por cedula invalida: {c.cedula}")
                continue
            
            cedula = c.cedula.strip()
            
            # Buscamos si ya existe por cedula (username) o por cliente_id
            user = User.query.filter((User.username == cedula) | (User.cliente_id == c.id)).first()
            
            raw_pass = cedula[-4:]
            hashed_pass = generate_password_hash(raw_pass)
            
            if not user:
                # Verificar si el username ya lo tiene otro usuario (ej: un admin con esa cedula por error)
                existing_username = User.query.filter_by(username=cedula).first()
                if existing_username:
                    print(f"Conflicto: El username {cedula} ya lo tiene el usuario ID {existing_username.id}")
                    continue

                user = User(
                    username=cedula,
                    password=hashed_pass,
                    role='cliente',
                    cliente_id=c.id,
                    nombre_completo=c.nombre
                )
                db.session.add(user)
                c_count += 1
            else:
                # Si es un admin, supervisor, etc., NO le cambiamos el username ni el rol!
                # Solo vinculamos si el rol es cliente o nulo
                if user.role not in ['cliente', None]:
                    print(f"Saltando usuario ID {user.id} ({user.username}) porque tiene rol: {user.role}")
                    continue
                    
                user.username = cedula
                user.password = hashed_pass
                user.role = 'cliente'
                user.cliente_id = c.id
                user.nombre_completo = c.nombre
                c_count += 1
        
        # 2. PRODUCTORES
        productores = Proveedor.query.filter_by(es_productor=True).all()
        print(f"Procesando {len(productores)} productores...")
        p_count = 0
        for p in productores:
            if not p.rif or len(p.rif.strip()) < 4: continue
            
            username = p.rif.strip().upper()
            
            user = User.query.filter((User.username == username) | (User.proveedor_id == p.id)).first()
            
            raw_pass = username[-4:]
            hashed_pass = generate_password_hash(raw_pass)
            
            if not user:
                existing_username = User.query.filter_by(username=username).first()
                if existing_username:
                    print(f"Conflicto: El username {username} ya lo tiene el usuario ID {existing_username.id}")
                    continue

                user = User(
                    username=username,
                    password=hashed_pass,
                    role='productor',
                    proveedor_id=p.id,
                    nombre_completo=p.nombre
                )
                db.session.add(user)
                p_count += 1
            else:
                if user.role not in ['productor', None]:
                    print(f"Saltando usuario ID {user.id} ({user.username}) porque tiene rol: {user.role}")
                    continue

                user.username = username
                user.password = hashed_pass
                user.role = 'productor'
                user.proveedor_id = p.id
                user.nombre_completo = p.nombre
                p_count += 1
        
        try:
            db.session.commit()
            print(f"EXITO: Se sincronizaron {c_count} clientes y {p_count} productores.")
        except Exception as e:
            db.session.rollback()
            print(f"ERROR al guardar en DB: {str(e)}")
            traceback.print_exc()

if __name__ == "__main__":
    sync_users()

import os
import sys
import sqlite3
from werkzeug.security import generate_password_hash

# Asegurar que el directorio actual esté en el path para importar app y models
sys.path.append(os.getcwd())

from app import app
from models import db, Cliente, Proveedor, User

def vincular_usuarios_masivo():
    with app.app_context():
        print("--- INICIANDO VINCULACIÓN MASIVA DE USUARIOS (V2) ---")
        
        # 1. CLIENTES
        clientes = Cliente.query.all()
        print(f"Total Clientes encontrados: {len(clientes)}")
        c_creados = 0
        c_vínculos = 0
        c_faltantes = 0
        
        for i, cli in enumerate(clientes):
            if not cli.cedula:
                c_faltantes += 1
                continue
            
            username = "".join(filter(str.isalnum, cli.cedula)).upper()
            existente = User.query.filter_by(username=username).first()
            
            if existente:
                if not existente.cliente_id:
                    existente.cliente_id = cli.id
                    c_vínculos += 1
                continue
            
            # Generar Clave (últimos 4 dígitos de números)
            solo_numeros = "".join(filter(str.isdigit, username))
            password_final = solo_numeros[-4:] if len(solo_numeros) >= 4 else (username[-4:] if len(username) >= 4 else "1234")
            
            nuevo = User(
                username=username,
                password=generate_password_hash(password_final, method='pbkdf2:sha256'),
                role='cliente',
                cliente_id=cli.id
            )
            db.session.add(nuevo)
            c_creados += 1
            
            # Commit cada 20 para no saturar y mostar progreso
            if i % 20 == 0 and i > 0:
                db.session.commit()
                print(f"... procesados {i} clientes")
            
        db.session.commit()
        print(f"REPORT CLIENTES: {c_creados} nuevos, {c_vínculos} vinculados, {c_faltantes} sin cédula.")
        
        # 2. PRODUCTORES (PROVEEDORES)
        productores = Proveedor.query.filter_by(es_productor=True).all()
        print(f"\nTotal Productores encontrados: {len(productores)}")
        p_creados = 0
        p_vínculos = 0
        p_faltantes = 0
        
        for prod in productores:
            raw_id = prod.rif
            if not raw_id:
                p_faltantes += 1
                continue
                
            username = "".join(filter(str.isalnum, raw_id)).upper()
            existente = User.query.filter_by(username=username).first()
            
            if existente:
                if not existente.proveedor_id:
                    existente.proveedor_id = prod.id
                    p_vínculos += 1
                continue
                
            solo_numeros = "".join(filter(str.isdigit, username))
            password_final = solo_numeros[-4:] if len(solo_numeros) >= 4 else (username[-4:] if len(username) >= 4 else "1234")
            
            nuevo = User(
                username=username,
                password=generate_password_hash(password_final, method='pbkdf2:sha256'),
                role='productor',
                proveedor_id=prod.id
            )
            db.session.add(nuevo)
            p_creados += 1
            
        db.session.commit()
        print(f"REPORT PRODUCTORES: {p_creados} nuevos, {p_vínculos} vinculados, {p_faltantes} sin RIF.")
        print("\n--- PROCESO FINALIZADO CON ÉXITO ---")

if __name__ == "__main__":
    vincular_usuarios_masivo()

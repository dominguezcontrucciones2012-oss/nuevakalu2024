import sqlite3
from werkzeug.security import generate_password_hash
import os

db_path = os.path.join('instance', 'kalu_master.db')

def migrate_users():
    if not os.path.exists(db_path):
        print(f"❌ No se encontro la base de datos en {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Obtener todos los clientes que NO tienen un usuario asociado
    cursor.execute("""
        SELECT id, nombre, cedula FROM clientes 
        WHERE id NOT IN (SELECT cliente_id FROM users WHERE cliente_id IS NOT NULL)
    """)
    clientes_sin_acceso = cursor.fetchall()

    if not clientes_sin_acceso:
        print("OK: Todos los clientes ya tienen su acceso creado.")
    else:
        print(f"INFO: Creando acceso para {len(clientes_sin_acceso)} clientes...")
        for c_id, nombre, cedula in clientes_sin_acceso:
            username = str(cedula).strip()
            # Password: last 4 digits
            password_plain = username[-4:] if len(username) >= 4 else "1234"
            password_hashed = generate_password_hash(password_plain)
            
            try:
                cursor.execute("""
                    INSERT INTO users (username, password, role, cliente_id)
                    VALUES (?, ?, ?, ?)
                """, (username, password_hashed, 'cliente', c_id))
                print(f"   + Acceso: {nombre} (User: {username} | Pass: {password_plain})")
            except Exception as e:
                print(f"   x Error con {nombre}: {e}")

    conn.commit()
    conn.close()
    print("\nPROCESO TERMINADO: Ya todos pueden entrar.")

if __name__ == "__main__":
    migrate_users()

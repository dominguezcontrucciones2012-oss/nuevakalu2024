import sqlite3
import os

db_path = os.path.join('instance', 'kalu_master.db')

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        print("Intentando añadir columna 'activo' a la tabla 'users'...")
        cursor.execute("ALTER TABLE users ADD COLUMN activo BOOLEAN DEFAULT 1;")
        conn.commit()
        print("✅ Columna añadida exitosamente.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ La columna 'activo' ya existe.")
        else:
            print(f"❌ Error al añadir columna: {e}")
    finally:
        conn.close()
else:
    print(f"❌ No se encontró la base de datos en {db_path}")

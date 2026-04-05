import sqlite3
import os

# 🔍 Buscamos la base de datos en la carpeta instance
db_path = 'd:/nuevakalu2024/instance/kalu_master.db'
if not os.path.exists(db_path):
    print(f"❌ Error: {db_path} no existe.")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Obtener columnas existentes
        cursor.execute("PRAGMA table_info(users)")
        existing = [row[1] for row in cursor.fetchall()]
        
        # Columnas a agregar para Google Login
        new_columns = [
            ('email', 'TEXT'),
            ('google_id', 'TEXT'),
            ('nombre_completo', 'TEXT'),
            ('avatar_url', 'TEXT')
        ]
        
        added = False
        for name, typ in new_columns:
            if name not in existing:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {name} {typ}")
                print(f"✅ Columna '{name}' agregada con éxito.")
                added = True
            else:
                print(f"ℹ️ La columna '{name}' ya existe.")
        
        # También actualizamos la versión de alembic para que no se queje
        # (Esto es opcional pero ayuda si existe la tabla alembic_version)
        try:
            cursor.execute("UPDATE alembic_version SET version_num = '388271f5b475'")
            print("📦 Versión de migraciones sincronizada.")
        except:
            pass

        conn.commit()
        conn.close()
        if added:
            print("🚀 Base de datos curada y lista para despegar.")
        else:
            print("ℹ️ Todo estaba ya en orden.")
            
    except Exception as e:
        print(f"❌ Error crítico: {e}")

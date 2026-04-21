import sqlite3
import os

db_path = 'd:/nuevakalu2024/instance/kalu_master.db'

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Attempting to add column 'es_obrero' to 'proveedores' table...")
    cursor.execute("ALTER TABLE proveedores ADD COLUMN es_obrero BOOLEAN DEFAULT 0")
    conn.commit()
    print("Column 'es_obrero' added successfully.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("Column 'es_obrero' already exists.")
    else:
        print(f"SQLite Error: {e}")
except Exception as e:
    print(f"General Error: {e}")
finally:
    conn.close()

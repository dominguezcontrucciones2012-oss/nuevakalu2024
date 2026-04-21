import sqlite3
import sys
import os

# Asegurar que el directorio actual esté en el path
sys.path.append(os.getcwd())

from app import app
from models import db

def get_db_columns(table_name):
    try:
        conn = sqlite3.connect('instance/kalu_master.db')
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return columns
    except:
        return []

def compare_models_with_db():
    with app.app_context():
        # Obtener todas las tablas registradas en SQLAlchemy
        for table_name, table in db.metadata.tables.items():
            db_cols = get_db_columns(table_name)
            if not db_cols:
                print(f"MISSING TABLE: {table_name}")
                continue
            
            model_cols = table.columns.keys()
            missing = [c for c in model_cols if c not in db_cols]
            
            if missing:
                print(f"TABLE '{table_name}' - MISSING COLUMNS: {missing}")
            else:
                pass 

if __name__ == "__main__":
    compare_models_with_db()

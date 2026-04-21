import sqlite3
import os

db_path = 'd:/nuevakalu2024/instance/kalu_master.db'

def run_sql(sql):
    print(f"Running: {sql}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        conn.close()
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")

# Agregar PIN a User
run_sql("ALTER TABLE users ADD COLUMN pin VARCHAR(10)")

# Agregar user_id a Venta
run_sql("ALTER TABLE ventas ADD COLUMN user_id INTEGER REFERENCES users(id)")

# Agregar user_id a HistorialPago
run_sql("ALTER TABLE historial_pagos ADD COLUMN user_id INTEGER REFERENCES users(id)")

# Agregar user_id a Asiento
run_sql("ALTER TABLE asientos ADD COLUMN user_id INTEGER REFERENCES users(id)")

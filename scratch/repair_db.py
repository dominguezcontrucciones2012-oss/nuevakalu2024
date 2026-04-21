import sqlite3

def repair_db():
    conn = sqlite3.connect('instance/kalu_master.db')
    cursor = conn.cursor()
    
    # Lista de alteraciones necesarias (tabla, columna, tipo)
    alterations = [
        ('users', 'pin', 'VARCHAR(10)'),
        ('ventas', 'pago_debito_bs', 'NUMERIC(10, 2) DEFAULT 0'),
        ('ventas', 'pago_otros_usd', 'NUMERIC(10, 2) DEFAULT 0'),
        ('ventas', 'user_id', 'INTEGER'),
        ('historial_pagos', 'user_id', 'INTEGER'),
        ('proveedores', 'es_obrero', 'BOOLEAN DEFAULT 0'),
        ('asientos', 'user_id', 'INTEGER'),
        ('cierres_caja', 'tarjeta_debito', 'NUMERIC(15, 2) DEFAULT 0'),
        ('cierres_caja', 'monto_real_usd', 'NUMERIC(10, 2) DEFAULT 0'),
        ('cierres_caja', 'monto_real_bs', 'NUMERIC(15, 2) DEFAULT 0'),
        ('cierres_caja', 'diferencia_usd', 'NUMERIC(10, 2) DEFAULT 0'),
        ('cierres_caja', 'diferencia_bs', 'NUMERIC(15, 2) DEFAULT 0'),
        ('cierres_caja', 'observaciones', 'TEXT')
    ]
    
    for table, column, col_type in alterations:
        try:
            print(f"Adding column '{column}' to table '{table}'...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print(f"DONE: Added {column} to {table}.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"INFO: Column '{column}' already exists, skipping.")
            else:
                print(f"ERROR adding '{column}' to '{table}': {e}")
                
    conn.commit()
    conn.close()
    print("\nDatabase repair complete.")

if __name__ == "__main__":
    repair_db()

import sqlite3

conn = sqlite3.connect('instance/kalu_master.db')  # Ajusta la ruta si es diferente
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE cuentas_por_pagar ADD COLUMN fecha DATETIME DEFAULT CURRENT_TIMESTAMP")
    print("Columna 'fecha' agregada correctamente.")
except sqlite3.OperationalError as e:
    print(f"Error al agregar columna: {e}")

conn.commit()
conn.close()
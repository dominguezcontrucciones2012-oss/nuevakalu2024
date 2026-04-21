import sqlite3

# Conexión a la base de datos
conn = sqlite3.connect('kalu_master.db')
cursor = conn.cursor()

# Obtener información de las columnas de la tabla ventas
cursor.execute("PRAGMA table_info(ventas);")
columns = cursor.fetchall()

print("Columnas de la tabla 'ventas':")
for col in columns:
    print(f"- {col[1]}")

conn.close()

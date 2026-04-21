import sqlite3
import os

db_path = os.path.join('d:\\nuevakalu2024', 'instance', 'kalu_master.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("UPDATE users SET role = 'admin' WHERE username = 'maestro'")
conn.commit()
conn.close()
print("Role changed to admin successfully!")


from werkzeug.security import generate_password_hash
import sqlite3
import os

# Path preferido en instance
db_path = os.path.join('instance', 'kalu_master.db')
if not os.path.exists(db_path):
    db_path = 'kalu_master.db'

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Contraseña nueva: kalu2024
new_password = 'kalu2024'
hashed_password = generate_password_hash(new_password)

try:
    cursor.execute("UPDATE users SET password = ? WHERE username = 'admin'", (hashed_password,))
    conn.commit()
    if cursor.rowcount > 0:
        print("✅ Password for 'admin' has been reset to: kalu2024")
    else:
        print("⚠️ No user named 'admin' found.")
except Exception as e:
    print(f"❌ Error updating database: {e}")
finally:
    conn.close()

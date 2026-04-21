import sqlite3
import os

def check_db(path):
    print(f"\n--- Checking {path} ---")
    if not os.path.exists(path):
        print("File does not exist.")
        return
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM productos")
        p_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM ventas")
        v_count = cur.fetchone()[0]
        print(f"Products: {p_count}")
        print(f"Total Sales: {v_count}")
        
        # Check today's sales
        cur.execute("SELECT sum(total_usd) FROM ventas WHERE date(fecha) = date('now', 'localtime')")
        v_today = cur.fetchone()[0]
        print(f"Sales Today (USD): {v_today}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

check_db(r"d:\nuevakalu2024\instance\kalu_master.db")
check_db(r"d:\folden_prueva\kalu_master.db")

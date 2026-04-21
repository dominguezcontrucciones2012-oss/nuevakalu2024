import sqlite3
import os

db_path = 'd:/nuevakalu2024/instance/kalu_master.db'

def check_table(table_name):
    print(f"\n--- Checking table: {table_name} ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"ID: {col[0]} | Name: {col[1]} | Type: {col[2]} | Nullable: {col[3]} | Default: {col[4]} | PK: {col[5]}")
        conn.close()
    except Exception as e:
        print(f"Error checking {table_name}: {e}")

tables = ['ventas', 'historial_pagos', 'asientos', 'movimientos_caja', 'users']
for t in tables:
    check_table(t)

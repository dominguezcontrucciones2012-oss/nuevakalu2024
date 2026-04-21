import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app
from models import Cliente

def check_balances():
    with app.app_context():
        clientes = Cliente.query.all()
        found = False
        for c in clientes:
            if c.saldo_usd and abs(c.saldo_usd) > 0.01:
                print(f"ID: {c.id} | {c.nombre} | Saldo: {c.saldo_usd}")
                found = True
        if not found:
            print("No clients with non-zero balance found.")

if __name__ == "__main__":
    check_balances()

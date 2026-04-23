from flask import Flask
from models import db, User
import os

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
# Note: we are in 'scratch', so we need to go up one level to find 'instance'
db_path = os.path.join(basedir, '..', 'instance', 'kalu_master.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    print("\n--- LISTA DE DEUDORES (MOROSOS) ---")
    # Assuming clients with debt are in User table or a separate table. 
    # Let's check models.py first to be sure.
    # Actually, I'll just check if there's a 'saldo' column or similar in User or Cliente.
    from models import Cliente
    deudores = Cliente.query.filter(Cliente.saldo_usd > 0).all()
    if not deudores:
        print("No se encontraron deudores con saldo_usd > 0.")
    for c in deudores:
        print(f"ID: {c.id} | Cliente: {c.nombre} | Saldo USD: ${c.saldo_usd:.2f}")
    print("-----------------------------------\n")

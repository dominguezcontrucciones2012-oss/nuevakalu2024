
from app import app
from models import db, MovimientoProductor, Proveedor
from decimal import Decimal

def full_audit(producer_id):
    with app.app_context():
        p = Proveedor.query.get(producer_id)
        if not p:
            print(f"ID {producer_id} not found")
            return
        
        print(f"\nAUDIT FOR {p.nombre} (ID {p.id})")
        print(f"Current balance in Proveedor table: {p.saldo_pendiente_usd}")
        
        movs = MovimientoProductor.query.filter_by(proveedor_id=p.id).order_by(MovimientoProductor.id).all()
        
        calc_bal = Decimal('0')
        for m in movs:
            debe = m.debe or Decimal('0')
            haber = m.haber or Decimal('0')
            calc_bal += (haber - debe)
            print(f"ID: {m.id} | Tipo: {m.tipo:15} | D: {debe:8.2f} | H: {haber:8.2f} | SM: {m.saldo_momento:8.2f} | CB: {calc_bal:8.2f} | Desc: {m.descripcion}")
        
        print(f"Final calculated balance: {calc_bal}")
        if calc_bal != p.saldo_pendiente_usd:
            print(f"!!!! DISCREPANCY DETECTED: DB says {p.saldo_pendiente_usd}, Calc says {calc_bal}")

if __name__ == "__main__":
    full_audit(2)
    full_audit(6)

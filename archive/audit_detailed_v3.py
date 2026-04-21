
from app import app
from models import db, MovimientoProductor, Proveedor
from decimal import Decimal

def full_audit():
    with app.app_context():
        # Encontrar a Andres y Diana por nombre para estar seguros de los IDs
        andres = Proveedor.query.filter(Proveedor.nombre.ilike('%ANDRES%')).first()
        diana = Proveedor.query.filter(Proveedor.nombre.ilike('%DIANA%')).first()
        
        target_ids = []
        if andres: target_ids.append(andres.id)
        if diana: target_ids.append(diana.id)
        
        for p_id in target_ids:
            p = Proveedor.query.get(p_id)
            print(f"\nAUDIT FOR {p.nombre} (ID {p.id})")
            print(f"Current balance in Proveedor table: {p.saldo_pendiente_usd}")
            
            movs = MovimientoProductor.query.filter_by(proveedor_id=p.id).order_by(MovimientoProductor.id).all()
            
            calc_bal = Decimal('0')
            for m in movs:
                debe = m.debe or Decimal('0')
                haber = m.haber or Decimal('0')
                calc_bal += (haber - debe)
                print(f"ID: {m.id} | Fecha: {m.fecha} | Tipo: {m.tipo:15} | D: {debe:8.2f} | H: {haber:8.2f} | SM: {m.saldo_momento:8.2f} | CB: {calc_bal:8.2f} | Desc: {m.descripcion}")
            
            print(f"Final calculated balance: {calc_bal}")
            if abs(calc_bal - (p.saldo_pendiente_usd or Decimal('0'))) > Decimal('0.01'):
                print(f"!!!! DISCREPANCY DETECTED: DB says {p.saldo_pendiente_usd}, Calc says {calc_bal}")

if __name__ == "__main__":
    full_audit()

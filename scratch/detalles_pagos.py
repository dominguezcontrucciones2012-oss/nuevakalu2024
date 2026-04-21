import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app
from models import db, Venta, Cliente, MovimientoCaja
from decimal import Decimal

def check_sale_payments():
    with app.app_context():
        ventas = Venta.query.order_by(Venta.id.desc()).limit(5).all()
        for v in ventas:
            print(f"Venta ID: {v.id} | Total: {v.total_usd} | Fiado: {v.es_fiado} | Pending: {v.saldo_pendiente_usd}")
            movs = MovimientoCaja.query.filter_by(referencia_id=v.id, modulo_origen='Venta').all()
            if not movs:
                print("   No payments recorded in MovimientoCaja.")
            for m in movs:
                print(f"   -> Pago: {m.tipo_caja} | Monto: {m.monto} | Desc: {m.descripcion}")
            
            if v.cliente:
                print(f"   -> Cliente: {v.cliente.nombre} | Saldo DB: {v.cliente.saldo_usd}")
            print("-" * 40)

if __name__ == "__main__":
    check_sale_payments()

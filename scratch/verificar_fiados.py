import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app
from models import db, Venta, Cliente, Proveedor
from decimal import Decimal

def check_last_fiado_sales():
    with app.app_context():
        # Last 5 sales
        ventas = Venta.query.order_by(Venta.fecha.desc()).limit(10).all()
        print(f"{'ID':<5} | {'Fecha':<20} | {'Cliente':<20} | {'Total':<8} | {'Fiado':<5} | {'Saldo Pendiente':<15}")
        print("-" * 80)
        for v in ventas:
            c_name = v.cliente.nombre if v.cliente else (v.nombre_cliente_final if hasattr(v, 'nombre_cliente_final') else "S/N")
            print(f"{v.id:<5} | {str(v.fecha):<20} | {c_name:<20} | {v.total_usd:<8} | {v.es_fiado:<5} | {v.saldo_pendiente_usd:<15}")
            
            if v.es_fiado and v.cliente:
                print(f"   -> Cliente {v.cliente.nombre} Saldo Actual: {v.cliente.saldo_usd}")

        print("\n--- PRODUCTORES ---")
        pros = Proveedor.query.filter(Proveedor.saldo_pendiente_usd != 0).all()
        for p in pros:
            print(f"Productor: {p.nombre} | Saldo: {p.saldo_pendiente_usd}")

if __name__ == "__main__":
    check_last_fiado_sales()

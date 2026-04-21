from app import app
from models import db, HistorialPago, Venta, Cliente
from decimal import Decimal

def ver_detalle():
    with app.app_context():
        # Juan Dominguez (ID 1)
        pagos = HistorialPago.query.filter_by(cliente_id=1).all()
        print(f"--- PAGOS DE JUAN DOMINGUEZ ---")
        for p in pagos:
            print(f"ID: {p.id}, Fecha: {p.fecha}, USD: {p.monto_usd}, Metodo: {p.metodo_pago}, Venta: {p.venta_id}")
        
        ventas = Venta.query.filter_by(cliente_id=1, es_fiado=True).all()
        print(f"\n--- VENTAS FIADAS DE JUAN DOMINGUEZ ---")
        for v in ventas:
            print(f"ID: {v.id}, Fecha: {v.fecha}, Total: {v.total_usd}, Saldo: {v.saldo_pendiente_usd}")

if __name__ == "__main__":
    ver_detalle()

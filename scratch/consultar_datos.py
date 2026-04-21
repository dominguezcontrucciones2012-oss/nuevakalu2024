from app import app
from models import db, Venta, Cliente, HistorialPago
from decimal import Decimal

def consultar():
    with app.app_context():
        # Venta 17
        v17 = Venta.query.get(17)
        if v17:
            print(f"--- VENTA 17 ---")
            print(f"ID: {v17.id}, Fecha: {v17.fecha}")
            print(f"Total USD: {v17.total_usd}")
            print(f"Saldo Pendiente: {v17.saldo_pendiente_usd}")
            print(f"Pagos: Efectivo={v17.pago_efectivo_usd}, Bs={v17.pago_efectivo_bs}, PM={v17.pago_movil_bs}, Deb={v17.pago_debito_bs}")
            print(f"Es Fiado: {v17.es_fiado}")
        else:
            print("Venta 17 no encontrada.")

        # Juan Dominguez
        juan = Cliente.query.filter(Cliente.nombre.ilike('%Juan Dominguez%')).first()
        if juan:
            print(f"\n--- JUAN DOMINGUEZ ---")
            print(f"ID: {juan.id}, Nombre: {juan.nombre}")
            print(f"Saldo USD (Actual): {juan.saldo_usd}")
            print(f"Saldo BS (Actual): {juan.saldo_bs}")
            
            # Historial de pagos
            pagos = HistorialPago.query.filter_by(cliente_id=juan.id).all()
            total_abonos = sum(p.monto_usd for p in pagos)
            print(f"Total Abonos Históricos: {total_abonos}")
            
            # Ventas fiadas
            ventas = Venta.query.filter_by(cliente_id=juan.id, es_fiado=True).all()
            total_ventas = sum(v.total_usd for v in ventas)
            print(f"Total Ventas Fiadas: {total_ventas}")
            print(f"Deuda Teórica (Ventas - Abonos): {total_ventas - total_abonos}")
        else:
            print("\nJuan Dominguez no encontrado.")

if __name__ == "__main__":
    consultar()

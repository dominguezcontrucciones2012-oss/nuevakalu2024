
from app import app, db
from models import Venta, Cliente, HistorialPago
from decimal import Decimal

with app.app_context():
    print("--- ULTIMAS 5 VENTAS ---")
    ventas = Venta.query.order_by(Venta.id.desc()).limit(5).all()
    for v in ventas:
        cliente_nombre = v.cliente.nombre if v.cliente else "N/A"
        print(f"ID: {v.id} | Fecha: {v.fecha} | Cliente: {cliente_nombre} | Total: {v.total_usd} | Fiado: {v.es_fiado} | Saldo Pend: {v.saldo_pendiente_usd}")
    
    print("\n--- CLIENTES CON SALDO > 0 ---")
    clientes = Cliente.query.filter(Cliente.saldo_usd > 0).all()
    for c in clientes:
        print(f"ID: {c.id} | Nombre: {c.nombre} | Saldo USD: {c.saldo_usd}")

    print("\n--- ULTIMOS 5 PAGOS ---")
    pagos = HistorialPago.query.order_by(HistorialPago.id.desc()).limit(5).all()
    for p in pagos:
        print(f"ID: {p.id} | Cliente: {p.cliente.nombre if p.cliente else 'N/A'} | Monto: {p.monto_usd} | Venta ID: {p.venta_id}")

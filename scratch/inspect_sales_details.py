
from app import app, db
from models import Venta, Cliente, HistorialPago
from decimal import Decimal

with app.app_context():
    print("--- DETALLE DE ULTIMAS 5 VENTAS ---")
    ventas = Venta.query.order_by(Venta.id.desc()).limit(5).all()
    for v in ventas:
        cliente_nombre = v.cliente.nombre if v.cliente else "N/A"
        print(f"ID: {v.id} | Cliente: {cliente_nombre} | Total: {v.total_usd}")
        print(f"  Pagos: Efect.$={v.pago_efectivo_usd}, Efect.Bs={v.pago_efectivo_bs}, PM={v.pago_movil_bs}, Transf={v.pago_transferencia_bs}, Debito={v.pago_debito_bs}, Bio={v.biopago_bdv}")
        print(f"  Fiado: {v.es_fiado} | Saldo Pendiente: {v.saldo_pendiente_usd}")
        print("-" * 50)
    
    print("\n--- SALDOS DE CLIENTES ---")
    clientes = Cliente.query.all()
    for c in clientes:
        if c.saldo_usd > 0:
            print(f"ID: {c.id} | {c.nombre} | Saldo: ${c.saldo_usd}")

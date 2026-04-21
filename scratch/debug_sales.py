from app import app
from models import db, Venta, Asiento, DetalleAsiento, Cliente, CuentaContable

with app.app_context():
    print("--- RECENT SALES ---")
    ventas = Venta.query.order_by(Venta.id.desc()).limit(5).all()
    for v in ventas:
        print(f"Venta ID: {v.id}, Total: {v.total_usd}, Fiado: {v.es_fiado}, Saldo Pendiente: {v.saldo_pendiente_usd}, Cliente: {v.nombre_cliente_final}")
        
    print("\n--- RECENT ACCOUNTING ENTRIES ---")
    asientos = Asiento.query.order_by(Asiento.id.desc()).limit(10).all()
    for a in asientos:
        print(f"Asiento ID: {a.id}, Desc: {a.descripcion}, Ref: {a.referencia_tipo} #{a.referencia_id}")
        for d in a.detalles:
            print(f"  - Cuenta: {d.cuenta.codigo} ({d.cuenta.nombre}), Debe USD: {d.debe_usd}, Haber USD: {d.haber_usd}")

    print("\n--- CLIENTS WITH BALANCE ---")
    clientes = Cliente.query.filter(Cliente.saldo_usd > 0).all()
    for c in clientes:
        print(f"Cliente: {c.nombre}, Saldo USD: {c.saldo_usd}")

    print("\n--- PRODUCTORES WITH DEBT (OR BALANCE) ---")
    # In this system, producers have saldo_pendiente_usd (what shop owes them)
    from models import Proveedor
    prods = Proveedor.query.filter(Proveedor.es_productor == True).all()
    for p in prods:
        print(f"Productor: {p.nombre}, Saldo Pendiente USD: {p.saldo_pendiente_usd}")

from app import app
from models import db, Proveedor, MovimientoProductor

with app.app_context():
    # Encontrar a Andres y Diana
    productores = Proveedor.query.filter(Proveedor.nombre.ilike('%andres%') | Proveedor.nombre.ilike('%diana%')).all()
    
    print("--- AUDITORIA DE BALANCES ---")
    for p in productores:
        print(f"\nProductor: {p.nombre} (ID: {p.id})")
        print(f"Saldo actual en Tabla: {p.saldo_pendiente_usd}")
        
        movs = MovimientoProductor.query.filter_by(proveedor_id=p.id).order_by(MovimientoProductor.fecha.asc()).all()
        calc_saldo = 0
        print("ID | Fecha | Tipo | Haber (+) | Debe (-) | Saldo Momento | Calc Saldo")
        for m in movs:
            calc_saldo += (m.haber - m.debe)
            print(f"{m.id} | {m.fecha} | {m.tipo} | {m.haber} | {m.debe} | {m.saldo_momento} | {calc_saldo}")
        
        if abs(calc_saldo - p.saldo_pendiente_usd) > 0.01:
            print(f"⚠️ DISCREPANCIA ENCONTRADA: DB p.saldo={p.saldo_pendiente_usd} vs Calculado={calc_saldo}")
        else:
            print("✅ Saldo sincronizado con movimientos.")

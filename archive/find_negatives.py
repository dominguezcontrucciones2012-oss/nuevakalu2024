from app import app
from models import db, Proveedor, MovimientoProductor

with app.app_context():
    productores = Proveedor.query.filter(Proveedor.saldo_pendiente_usd < 0).all()
    
    print("--- PRODUCTORES CON SALDO NEGATIVO ---")
    for p in productores:
        print(f"\nProductor: {p.nombre} (ID: {p.id})")
        print(f"Saldo actual en Tabla: {p.saldo_pendiente_usd}")
        
        movs = MovimientoProductor.query.filter_by(proveedor_id=p.id).order_by(MovimientoProductor.fecha.asc()).all()
        for m in movs:
            print(f"  {m.id} | {m.tipo} | {m.haber} | {m.debe} | {m.saldo_momento}")

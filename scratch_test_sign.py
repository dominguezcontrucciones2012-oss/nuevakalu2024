from app import app
from models import db, Proveedor, MovimientoProductor
from decimal import Decimal
from datetime import datetime

with app.app_context():
    p = Proveedor.query.filter_by(rif='11120033').first()
    print(f"Saldo Inicial: {p.saldo_pendiente_usd}")
    monto = Decimal('10.00')
    
    # Simular lo que hace clientes.py
    p.saldo_pendiente_usd += monto
    db.session.add(MovimientoProductor(
        proveedor_id=p.id,
        tipo='TEST_SIGN',
        haber=monto,
        saldo_momento=p.saldo_pendiente_usd, # Aquí ya está sumado
        fecha=datetime.now()
    ))
    db.session.commit()
    print(f"Saldo Final: {p.saldo_pendiente_usd}")

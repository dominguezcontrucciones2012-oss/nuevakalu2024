from app import app
from models import db, MovimientoCaja
from datetime import datetime
import pytz
from sqlalchemy import func
from decimal import Decimal

with app.app_context():
    TZ = pytz.timezone('America/Caracas')
    hoy = datetime.now(TZ).date()
    
    # Check Caja USD
    q_ing = db.session.query(func.sum(MovimientoCaja.monto)).filter(
        func.date(MovimientoCaja.fecha) == hoy,
        MovimientoCaja.tipo_caja == 'Caja USD',
        MovimientoCaja.tipo_movimiento == 'INGRESO'
    ).scalar() or Decimal('0')
    
    q_egr = db.session.query(func.sum(MovimientoCaja.monto)).filter(
        func.date(MovimientoCaja.fecha) == hoy,
        MovimientoCaja.tipo_caja == 'Caja USD',
        MovimientoCaja.tipo_movimiento == 'EGRESO'
    ).scalar() or Decimal('0')
    
    print(f"--- Caja USD ---")
    print(f"  Ingresos: {q_ing}")
    print(f"  Egresos:  {q_egr}")
    print(f"  Neto:     {q_ing - q_egr}")

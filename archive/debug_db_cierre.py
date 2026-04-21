from app import app
from models import db, MovimientoCaja, CierreCaja
from datetime import datetime
import pytz
from sqlalchemy import func

with app.app_context():
    TZ = pytz.timezone('America/Caracas')
    hoy = datetime.now(TZ).date()
    print(f"--- ESTADO PARA {hoy} ---")
    
    # 1. ¿Existe un cierre ya guardado hoy?
    c = CierreCaja.query.filter_by(fecha=hoy).first()
    if c:
        print(f"Cierre YA EXISTE: ID={c.id}, Bs={c.monto_bs}, PM={c.pago_movil}")
        print(f"Observaciones: {c.observaciones}")
    else:
        print("Cierre NO existe todavía para hoy.")
        
    # 2. ¿Hay movimientos con monto negativo en la DB?
    neg = MovimientoCaja.query.filter(MovimientoCaja.monto < 0).all()
    if neg:
        print(f"ALERTA: Se encontraron {len(neg)} movimientos con monto NEGATIVO:")
        for m in neg:
            print(f"  - ID: {m.id} | Monto: {m.monto} | Fecha: {m.fecha} | Desc: {m.descripcion}")
    else:
        print("No hay movimientos con monto negativo (campo monto < 0).")

    # 3. Calcular lo que el sistema reportará con la NUEVA lógica
    def get_ingreso_puro(tipo_caja, metodos=None):
        q = db.session.query(func.sum(MovimientoCaja.monto)).filter(
            func.date(MovimientoCaja.fecha) == hoy,
            MovimientoCaja.tipo_caja == tipo_caja,
            MovimientoCaja.tipo_movimiento == 'INGRESO'
        )
        if metodos:
            from sqlalchemy import or_
            filtros = [MovimientoCaja.descripcion.ilike(f'%{m}%') for m in metodos]
            q = q.filter(or_(*filtros))
        return q.scalar() or 0

    bs_ing = get_ingreso_puro('Caja Bs')
    pm_ing = get_ingreso_puro('Banco', ['Pago Móvil', 'PAGO_MOVIL', 'PM'])
    
    print(f"\nReporte que verá el usuario (NUEVA LÓGICA):")
    print(f"  Caja Bs: {bs_ing}")
    print(f"  Pago Móvil: {pm_ing}")

from app import app
from models import db, MovimientoCaja
from datetime import datetime
import pytz
from sqlalchemy import func
from decimal import Decimal

with app.app_context():
    TZ = pytz.timezone('America/Caracas')
    hoy = datetime.now(TZ).date()
    print(f"Analizando movimientos para: {hoy}")
    
    # query_monto logic from routes/cierre.py
    def get_resumen_caja(tipo_caja, metodos=None):
        def query_monto(tipo_mov):
            q = db.session.query(func.sum(MovimientoCaja.monto)).filter(
                func.date(MovimientoCaja.fecha) == hoy,
                MovimientoCaja.tipo_caja == tipo_caja,
                MovimientoCaja.tipo_movimiento == tipo_mov
            )
            if metodos:
                from sqlalchemy import or_
                filtros = [MovimientoCaja.descripcion.ilike(f'%{m}%') for m in metodos]
                q = q.filter(or_(*filtros))
            return q.scalar() or Decimal('0')

        ingresos = query_monto('INGRESO')
        egresos = query_monto('EGRESO')
        return ingresos, egresos, ingresos - egresos

    cajas = [
        ('Caja USD', None),
        ('Caja Bs', None),
        ('Banco', ['Pago Móvil', 'PAGO_MOVIL', 'PM'])
    ]

    for nombre, metodos in cajas:
        ing, egr, neto = get_resumen_caja(nombre, metodos)
        print(f"--- {nombre} ({metodos if metodos else 'Todo'}) ---")
        print(f"  Ingresos: {ing}")
        print(f"  Egresos:  {egr}")
        print(f"  Neto:     {neto}")
        
        if neto < 0:
            print("  [!] NEGATIVO DETECTADO. Listando egresos:")
            q_egr = MovimientoCaja.query.filter(
                func.date(MovimientoCaja.fecha) == hoy,
                MovimientoCaja.tipo_caja == nombre,
                MovimientoCaja.tipo_movimiento == 'EGRESO'
            )
            if metodos:
                from sqlalchemy import or_
                filtros = [MovimientoCaja.descripcion.ilike(f'%{m}%') for m in metodos]
                q_egr = q_egr.filter(or_(*filtros))
            
            for m in q_egr.all():
                print(f"    - ID: {m.id} | Monto: {m.monto} | Categoria: {m.categoria} | Desc: {m.descripcion}")
            
            print("  Listando ingresos:")
            q_ing = MovimientoCaja.query.filter(
                func.date(MovimientoCaja.fecha) == hoy,
                MovimientoCaja.tipo_caja == nombre,
                MovimientoCaja.tipo_movimiento == 'INGRESO'
            )
            if metodos:
                from sqlalchemy import or_
                filtros = [MovimientoCaja.descripcion.ilike(f'%{m}%') for m in metodos]
                q_ing = q_ing.filter(or_(*filtros))
            
            for m in q_ing.all():
                print(f"    - ID: {m.id} | Monto: {m.monto} | Categoria: {m.categoria} | Desc: {m.descripcion}")

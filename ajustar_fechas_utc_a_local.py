# ajustar_fechas_utc_a_local.py
from app import app
from models import db, Venta, HistorialPago, MovimientoProductor, Compra, PagoProductor, LiquidacionCiudad, AuditoriaInventario
from datetime import timedelta
import sys

# Ajuste en horas (ej: Venezuela UTC-4 => restar 4)
AJUSTE_HORAS = 4

TABLAS_Y_COLUMNAS = [
    (Venta, 'fecha'),
    (HistorialPago, 'fecha'),
    (MovimientoProductor, 'fecha'),
    (Compra, 'fecha'),
    (PagoProductor, 'fecha'),
    (LiquidacionCiudad, 'fecha'),
    (AuditoriaInventario, 'fecha'),
    # Agrega otras clases/columnas si hace falta
]

DRY_RUN = True if '--dry' in sys.argv else False

def ajustar():
    with app.app_context():
        print("DB URI:", app.config.get('SQLALCHEMY_DATABASE_URI'))
        ajuste = timedelta(hours=AJUSTE_HORAS)
        for modelo, columna in TABLAS_Y_COLUMNAS:
            q = db.session.query(modelo)
            total = q.count()
            print(f"\nProcesando {modelo.__tablename__} ({total} filas)...")
            # Muestra min/max antes
            primero = q.order_by(getattr(modelo, columna)).first()
            ultimo  = q.order_by(getattr(modelo, columna).desc()).first()
            if primero:
                print("  Antes: min:", getattr(primero, columna), " max:", getattr(ultimo, columna))
            else:
                print("  Tabla vacía, saltando.")
                continue

            if DRY_RUN:
                print("  DRY RUN: no se aplicarán cambios. Para aplicar, re-ejecuta sin --dry")
                # Muestra 5 ejemplos
                ejemplos = q.order_by(getattr(modelo, columna).desc()).limit(5).all()
                for e in ejemplos:
                    v = getattr(e, columna)
                    v_new = v - ajuste
                    print(f"    id={e.id} | antes={v} -> despues={v_new}")
                continue

            # Aplicar cambios en bloque
            filas = q.all()
            for fila in filas:
                v = getattr(fila, columna)
                if v is None: 
                    continue
                nuevo = v - ajuste
                setattr(fila, columna, nuevo)
            db.session.commit()
            print(f"  OK: ajustadas {total} filas en {modelo.__tablename__} restando {AJUSTE_HORAS} horas.")

if __name__ == "__main__":
    print("=== Ajuste de fechas UTC -> Local ===")
    print("Modo:", "DRY RUN (no modifica)" if DRY_RUN else "APLICAR (modifica filas)")
    ajustar()
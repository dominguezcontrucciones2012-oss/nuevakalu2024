
import os
import sys
from datetime import datetime, timedelta

# Añadir el directorio raíz al path para poder importar los modelos
sys.path.append('d:/nuevakalu2024')

from app import app
from models import db, MovimientoCaja

def analizar_movimientos():
    with app.app_context():
        # Ver los movimientos de los últimos 2 días
        hace_2_dias = datetime.now() - timedelta(days=2)
        movs = MovimientoCaja.query.filter(MovimientoCaja.fecha >= hace_2_dias).all()
        
        print(f"{'Fecha':<20} | {'Caja':<12} | {'Monto':<8} | {'Descripción'}")
        print("-" * 80)
        for m in movs:
            print(f"{str(m.fecha):<20} | {m.tipo_caja:<12} | {m.monto:<8} | {m.descripcion}")

if __name__ == "__main__":
    analizar_movimientos()

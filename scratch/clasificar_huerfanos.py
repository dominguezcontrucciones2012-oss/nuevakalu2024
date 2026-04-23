from app import app, db
from models import Venta, Cliente
from datetime import datetime, timedelta
import pytz
from decimal import Decimal

VE_TZ = pytz.timezone('America/Caracas')

def clasificar_huerfanos():
    with app.app_context():
        # 1. Buscar todas las ventas fiadas sin cliente
        huerfanas = Venta.query.filter(Venta.cliente_id == None, Venta.saldo_pendiente_usd > 0).all()
        
        limite_7_dias = datetime.now(VE_TZ) - timedelta(days=7)
        
        recientes = 0
        viejas = 0
        monto_reciente = Decimal('0.00')
        monto_viejo = Decimal('0.00')
        
        for v in huerfanas:
            v_fecha = v.fecha
            if v_fecha.tzinfo is None:
                v_fecha = VE_TZ.localize(v_fecha)
                
            if v_fecha > limite_7_dias:
                recientes += 1
                monto_reciente += v.saldo_pendiente_usd
            else:
                viejas += 1
                monto_viejo += v.saldo_pendiente_usd
        
        print(f"RESULTADO DEL ESCANEO:")
        print(f"--------------------------")
        print(f"RECIENTES (7 Dias): {recientes} facturas | Total: ${monto_reciente:.2f}")
        print(f"VIEJAS (Para Archivar): {viejas} facturas | Total: ${monto_viejo:.2f}")
        print(f"--------------------------")
        print(f"TOTAL DEUDA POR RECUPERAR: ${monto_reciente + monto_viejo:.2f}")

if __name__ == "__main__":
    clasificar_huerfanos()

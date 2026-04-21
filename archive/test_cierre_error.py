from app import app
from routes.cierre import _calcular_resumen
from datetime import datetime
import pytz
from decimal import Decimal

with app.app_context():
    try:
        TZ = pytz.timezone('America/Caracas')
        hoy = datetime.now(TZ).date()
        print(f"Probando _calcular_resumen para {hoy}...")
        r = _calcular_resumen(hoy)
        print("Resumen calculado con éxito:")
        for k, v in r.items():
            print(f"  {k}: {v}")
    except Exception as e:
        import traceback
        print(f"ERROR en _calcular_resumen: {e}")
        traceback.print_exc()

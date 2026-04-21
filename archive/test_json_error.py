from app import app
from routes.cierre import _generar_json_detalles
from datetime import datetime
import pytz

with app.app_context():
    try:
        TZ = pytz.timezone('America/Caracas')
        hoy = datetime.now(TZ).date()
        print(f"Probando _generar_json_detalles para {hoy}...")
        j1, j2 = _generar_json_detalles(hoy)
        print("Snapshots generados con éxito.")
        # print(j1[:100])
    except Exception as e:
        import traceback
        print(f"ERROR en _generar_json_detalles: {e}")
        traceback.print_exc()

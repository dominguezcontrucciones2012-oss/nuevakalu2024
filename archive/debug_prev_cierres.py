from app import app
from models import db, CierreCaja
from datetime import datetime, timedelta
import pytz

with app.app_context():
    TZ = pytz.timezone('America/Caracas')
    ahora = datetime.now(TZ)
    ayer = (ahora - timedelta(days=1)).date()
    # Let's check the last few cierres
    cierres = CierreCaja.query.order_by(CierreCaja.fecha.desc()).limit(5).all()
    print("--- ULTIMOS CIERRES ---")
    for c in cierres:
        print(f"Fecha: {c.fecha} | USD Real: {c.monto_real_usd} | Bs Real: {c.monto_real_bs} | PM: {c.pago_movil}")

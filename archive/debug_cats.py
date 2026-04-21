from app import app
from models import db, MovimientoCaja
from datetime import datetime
import pytz
from sqlalchemy import func

with app.app_context():
    TZ = pytz.timezone('America/Caracas')
    hoy = datetime.now(TZ).date()
    cats = db.session.query(MovimientoCaja.categoria, func.count()).filter(func.date(MovimientoCaja.fecha) == hoy).group_by(MovimientoCaja.categoria).all()
    print('Categorias de hoy:', cats)

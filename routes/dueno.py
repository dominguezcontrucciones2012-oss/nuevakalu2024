from flask import Blueprint, render_template, current_app
from models import Venta, Producto, CierreCaja, db
from datetime import datetime, date
from sqlalchemy import func

from decimal import Decimal, InvalidOperation
from utils import seguro_decimal
from flask_login import login_required
from routes.decorators import staff_required

dueno_bp = Blueprint('dueno', __name__)

@dueno_bp.route('/gerencia/dashboard')
@login_required
@staff_required
def dashboard():
    hoy = date.today()

    # 1. Ventas del día
    ventas_hoy = Venta.query.filter(
        func.date(Venta.fecha) == hoy
    ).all()

    ventas_normales = [v for v in ventas_hoy if not v.es_fiado]
    ventas_fiadas   = [v for v in ventas_hoy if v.es_fiado]

    total_usd   = sum(seguro_decimal(v.total_usd) for v in ventas_normales)
    fiados_usd  = sum(seguro_decimal(v.total_usd) for v in ventas_fiadas)

    # 2. Métodos de pago del día
    pago_usd      = sum(seguro_decimal(v.pago_efectivo_usd) for v in ventas_hoy)
    pago_bs       = sum(seguro_decimal(v.pago_efectivo_bs) for v in ventas_hoy)
    pago_movil    = sum(seguro_decimal(v.pago_movil_bs) for v in ventas_hoy)
    pago_transfer = sum(seguro_decimal(v.pago_transferencia_bs) for v in ventas_hoy)
    pago_bio      = sum(seguro_decimal(v.biopago_bdv) for v in ventas_hoy)

    # 3. Stock crítico (usa stock_minimo de cada producto)
    stock_bajo = Producto.query.filter(
        Producto.stock <= Producto.stock_minimo
    ).order_by(Producto.stock.asc()).all()

    # 4. Total Histórico (para tranquilidad del usuario)
    total_historico_ventas = Venta.query.count()
    
    # 5. Último cierre de caja
    cierre = CierreCaja.query.order_by(CierreCaja.fecha.desc()).first()

    stats = {
        "fecha": hoy.strftime('%d/%m/%Y'),
        "hora": datetime.now().strftime('%I:%M %p'),
        "ventas_usd": round(total_usd, 2),
        "fiados_usd": round(fiados_usd, 2),
        "total_historico": total_historico_ventas,
        "num_ventas": len(ventas_normales),
        "num_fiados": len(ventas_fiadas),
        "pago_usd": round(pago_usd, 2),
        "pago_bs": round(pago_bs, 2),
        "pago_movil": round(pago_movil, 2),
        "pago_transfer": round(pago_transfer, 2),
        "pago_bio": round(pago_bio, 2),
        "stock_critico": stock_bajo,
        "cierre": cierre
    }

    return render_template('dueno_dashboard.html', stats=stats)
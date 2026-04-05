from flask import Blueprint, render_template, current_app
from models import Venta, Producto, CierreCaja, db
from datetime import datetime, date
from sqlalchemy import func

dueno_bp = Blueprint('dueno', __name__)

@dueno_bp.route('/gerencia/dashboard')
def dashboard():
    hoy = date.today()

    # 1. Ventas del día
    ventas_hoy = Venta.query.filter(
        func.date(Venta.fecha) == hoy
    ).all()

    ventas_normales = [v for v in ventas_hoy if not v.es_fiado]
    ventas_fiadas   = [v for v in ventas_hoy if v.es_fiado]

    total_usd   = sum(float(v.total_usd or 0) for v in ventas_normales)
    fiados_usd  = sum(float(v.total_usd or 0) for v in ventas_fiadas)

    # 2. Métodos de pago del día
    pago_usd      = sum(float(v.pago_efectivo_usd or 0) for v in ventas_hoy)
    pago_bs       = sum(float(v.pago_efectivo_bs or 0) for v in ventas_hoy)
    pago_movil    = sum(float(v.pago_movil_bs or 0) for v in ventas_hoy)
    pago_transfer = sum(float(v.pago_transferencia_bs or 0) for v in ventas_hoy)
    pago_bio      = sum(float(v.biopago_bdv or 0) for v in ventas_hoy)

    # 3. Stock crítico (usa stock_minimo de cada producto)
    stock_bajo = Producto.query.filter(
        Producto.stock <= Producto.stock_minimo
    ).order_by(Producto.stock.asc()).all()

    # 4. Último cierre de caja
    cierre = CierreCaja.query.order_by(CierreCaja.fecha.desc()).first()

    stats = {
        "fecha": hoy.strftime('%d/%m/%Y'),
        "hora": datetime.now().strftime('%I:%M %p'),
        "ventas_usd": round(total_usd, 2),
        "fiados_usd": round(fiados_usd, 2),
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
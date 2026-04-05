from flask import Blueprint, render_template
from models import db, Venta
from sqlalchemy.orm import joinedload
from sqlalchemy import func

historial_bp = Blueprint('historial', __name__)

@historial_bp.route('/historial')
def ver_historial():
    # Traemos ventas con cliente cargado (evita errores lazy loading)
    ventas = (
        Venta.query
        .options(joinedload(Venta.cliente))
        .order_by(Venta.fecha.desc())
        .all()
    )

    # Total histórico vendido
    total_historico = (
        db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
        .scalar()
    )

    return render_template(
        'historial.html',
        ventas=ventas,
        total_historico=float(total_historico)
    )
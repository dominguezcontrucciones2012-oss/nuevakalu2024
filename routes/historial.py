from flask import Blueprint, render_template, request
from models import db, Venta
from sqlalchemy.orm import joinedload
from sqlalchemy import func

historial_bp = Blueprint('historial', __name__)

@historial_bp.route('/historial')
def ver_historial():
    from models import DetalleVenta
    page = request.args.get('page', 1, type=int)
    
    # Traemos ventas con cliente y detalles cargados (paginado a 50 por página)
    ventas_paginadas = (
        Venta.query
        .options(
            joinedload(Venta.cliente),
            joinedload(Venta.detalles).joinedload(DetalleVenta.producto)
        )
        .order_by(Venta.fecha.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )

    # Total histórico vendido
    total_historico = (
        db.session.query(func.coalesce(func.sum(Venta.total_usd), 0))
        .scalar()
    )

    return render_template(
        'historial.html',
        ventas_paginadas=ventas_paginadas,
        ventas=ventas_paginadas.items,
        total_historico=float(total_historico)
    )
import os
import shutil
from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from routes.decorators import staff_required
from functools import wraps
from models import db, Venta, DetalleVenta, Producto, CierreCaja, TasaBCV, MovimientoCaja, HistorialPago
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func
from utils import seguro_decimal

reportes_bp = Blueprint('reportes', __name__)

# ============================================================
# 🔒 DECORADOR DE SEGURIDAD (solo para funciones críticas)
# ============================================================
def solo_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("⚠️ Debes iniciar sesión primero.", "warning")
            return redirect(url_for('auth.ingresar'))
        if current_user.role not in ['admin', 'supervisor', 'dueno']:
            flash("🚫 No tienes permiso para esta acción.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# No local helper needed, using seguro_decimal from utils


# CIERRE DE CAJA centralizado en routes/cierre.py


# ─────────────────────────────────────────────────────────────
#  3. ANÁLISIS Y UTILIDAD  →  /reportes  🔒 Solo Admin
# ─────────────────────────────────────────────────────────────
@reportes_bp.route('/reportes')
@login_required
@solo_admin
def panel_reportes():
    fecha_inicio = request.args.get('inicio', datetime.now().strftime('%Y-%m-%d'))
    fecha_fin    = request.args.get('fin',    datetime.now().strftime('%Y-%m-%d'))

    start = datetime.strptime(fecha_inicio, '%Y-%m-%d')
    end   = datetime.strptime(fecha_fin,    '%Y-%m-%d') + timedelta(days=1)

    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = seguro_decimal(tasa_obj.valor) if tasa_obj else Decimal('1.00')

    ventas = Venta.query.filter(Venta.fecha >= start, Venta.fecha < end).all()
    total_ventas_usd = sum(seguro_decimal(v.total_usd) for v in ventas)
    total_ventas_bs  = (total_ventas_usd * tasa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    num_ventas       = len(ventas)

    detalles = DetalleVenta.query.join(Venta)\
        .filter(Venta.fecha >= start, Venta.fecha < end).all()
    total_costo_usd = sum((seguro_decimal(d.producto.costo_usd) * d.cantidad for d in detalles), Decimal('0.00'))
    utilidad_usd = (total_ventas_usd - total_costo_usd).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    top_productos = db.session.query(
        Producto.nombre.label('nombre_producto'),
        func.sum(DetalleVenta.cantidad).label('total')
    ).join(DetalleVenta, Producto.id == DetalleVenta.producto_id)\
     .join(Venta, Venta.id == DetalleVenta.venta_id)\
     .filter(Venta.fecha >= start, Venta.fecha < end)\
     .group_by(Producto.nombre)\
     .order_by(func.sum(DetalleVenta.cantidad).desc())\
     .limit(10).all()

    return render_template('panel_reportes.html',
        total_usd     = total_ventas_usd,
        total_bs      = total_ventas_bs,
        num_ventas    = num_ventas,
        utilidad      = utilidad_usd,
        top_productos = top_productos,
        inicio        = fecha_inicio,
        fin           = fecha_fin,
    )


# ─────────────────────────────────────────────────────────────
#  4. GENERAR RESPALDO  →  /respaldar_db  🔒 Solo Admin
# ─────────────────────────────────────────────────────────────
@reportes_bp.route('/respaldar_db')
@login_required
@solo_admin
def respaldar_db():
    try:
        fecha_hoy       = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        nombre_respaldo = f"respaldo_kalu_{fecha_hoy}.db"

        carpeta_instance = os.path.join(os.getcwd(), 'instance')
        archivos_db = [f for f in os.listdir(carpeta_instance) if f.endswith('.db')]
        if not archivos_db:
            raise FileNotFoundError("No se encontró ningún .db en instance/")
        origen = os.path.join(carpeta_instance, archivos_db[0])

        carpeta_backups = os.path.join(os.getcwd(), 'backups')
        os.makedirs(carpeta_backups, exist_ok=True)
        destino = os.path.join(carpeta_backups, nombre_respaldo)

        shutil.copy2(origen, destino)
        flash(f"✅ Respaldo creado: {nombre_respaldo}", "success")
        return send_file(destino, as_attachment=True)

    except Exception as e:
        flash(f"❌ Error al respaldar: {str(e)}", "danger")
        return redirect(url_for('reportes.panel_reportes'))
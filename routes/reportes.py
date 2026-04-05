import os
import shutil
from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from functools import wraps
from models import db, Venta, DetalleVenta, Producto, CierreCaja, TasaBCV, MovimientoCaja, HistorialPago
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func

reportes_bp = Blueprint('reportes', __name__)

# ============================================================
# 🔒 DECORADOR DE SEGURIDAD (solo para funciones críticas)
# ============================================================
def solo_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("⚠️ Debes iniciar sesión primero.", "warning")
            return redirect(url_for('auth.login'))
        if current_user.role not in ['admin', 'supervisor']:
            flash("🚫 No tienes permiso para esta acción.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ─────────────────────────────────────────────────────────────
#  HELPER: convierte cualquier valor a Decimal seguro
# ─────────────────────────────────────────────────────────────
def _d(valor):
    if valor is None:
        return Decimal('0.00')
    return Decimal(str(valor))


# ─────────────────────────────────────────────────────────────
#  1. CIERRE DE CAJA DIARIO  →  /reporte_cierre
#     ✅ SIN @solo_admin → el cajero puede verlo
# ─────────────────────────────────────────────────────────────
@reportes_bp.route('/reporte_cierre')
@login_required
def vista_reportes():
    hoy = datetime.now().date()
    ventas_hoy = Venta.query.filter(func.date(Venta.fecha) == hoy).all()

    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = _d(tasa_obj.valor) if tasa_obj else Decimal('1.00')

    class Resumen: pass
    r = Resumen()

    # ✅ VENTAS DEL POS
    r.efectivo_usd  = sum(_d(v.pago_efectivo_usd)    for v in ventas_hoy)
    r.efectivo_bs   = sum(_d(v.pago_efectivo_bs)      for v in ventas_hoy)
    r.pago_movil    = sum(_d(v.pago_movil_bs)         for v in ventas_hoy)
    r.transferencia = sum(_d(v.pago_transferencia_bs) for v in ventas_hoy)
    r.biopago       = sum(_d(v.biopago_bdv)           for v in ventas_hoy)
    r.fiado         = sum(_d(v.total_usd) for v in ventas_hoy if v.es_fiado)
    r.fiado_libreta = sum(_d(v.saldo_pendiente_usd)   for v in ventas_hoy)
    r.conteo        = len(ventas_hoy)

    # ✅ ABONOS DE CLIENTES (morosos que pagan hoy)
    abonos_hoy = HistorialPago.query.filter(
        func.date(HistorialPago.fecha) == hoy
    ).all()
    r.abonos_usd    = sum(_d(a.monto_usd) for a in abonos_hoy)
    r.abonos_bs     = sum(_d(a.monto_bs)  for a in abonos_hoy)
    r.conteo_abonos = len(abonos_hoy)

    # ✅ MOVIMIENTOS DE CAJA DEL DÍA
    movs_hoy = MovimientoCaja.query.filter(
        func.date(MovimientoCaja.fecha) == hoy
    ).all()

    # Entradas de caja
    r.entradas_caja_usd = sum(
        _d(m.monto) for m in movs_hoy
        if m.tipo_movimiento == 'ENTRADA' and m.tipo_caja == 'CAJA_USD'
    )
    r.entradas_caja_bs = sum(
        _d(m.monto) for m in movs_hoy
        if m.tipo_movimiento == 'ENTRADA' and m.tipo_caja == 'CAJA_BS'
    )

    # Salidas de caja (compras, pagos productor, gastos)
    r.salidas_usd = sum(
        _d(m.monto) for m in movs_hoy
        if m.tipo_movimiento == 'SALIDA' and m.tipo_caja == 'CAJA_USD'
    )
    r.salidas_bs = sum(
        _d(m.monto) for m in movs_hoy
        if m.tipo_movimiento == 'SALIDA' and m.tipo_caja == 'CAJA_BS'
    )

    # Desglose de salidas por categoría
    r.compras_usd = sum(
        _d(m.monto) for m in movs_hoy
        if m.tipo_movimiento == 'SALIDA' and 'Compras' in (m.categoria or '')
    )
    r.compras_bs = sum(
        _d(m.monto) for m in movs_hoy
        if m.tipo_movimiento == 'SALIDA'
        and 'Compras' in (m.categoria or '')
        and m.tipo_caja == 'CAJA_BS'
    )
    r.pagos_productor_usd = sum(
        _d(m.monto) for m in movs_hoy
        if m.tipo_movimiento == 'SALIDA' and 'Productor' in (m.categoria or '')
    )
    r.gastos_usd = sum(
        _d(m.monto) for m in movs_hoy
        if m.tipo_movimiento == 'SALIDA' and 'Gasto' in (m.categoria or '')
    )

    # ✅ TOTAL REAL EN CAJA
    r.total_general = (
        r.efectivo_usd
        + r.abonos_usd
        - r.salidas_usd
        + (r.efectivo_bs + r.pago_movil + r.transferencia + r.biopago - r.salidas_bs) / tasa
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cierres_historial = CierreCaja.query.order_by(CierreCaja.fecha.desc()).limit(10).all()
    ya_cerrado = CierreCaja.query.filter(CierreCaja.fecha == hoy).first() is not None

    return render_template('cierre_diario.html',
        fecha             = hoy,
        tasa              = tasa,
        r                 = r,
        cierres_historial = cierres_historial,
        ya_cerrado        = ya_cerrado,
        ventas_hoy        = ventas_hoy,
        abonos_hoy        = abonos_hoy,
        movs_hoy          = movs_hoy,
    )


# ─────────────────────────────────────────────────────────────
#  2. EJECUTAR CIERRE OFICIAL  →  /cierre/ejecutar
#     🔒 SOLO ADMIN puede cerrar la caja
# ─────────────────────────────────────────────────────────────
@reportes_bp.route('/cierre/ejecutar', methods=['POST'])
@login_required
@solo_admin
def ejecutar_cierre():
    hoy = datetime.now().date()

    if CierreCaja.query.filter(CierreCaja.fecha == hoy).first():
        flash("⚠️ La caja ya fue cerrada hoy.", "warning")
        return redirect(url_for('reportes.vista_reportes'))

    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = _d(tasa_obj.valor) if tasa_obj else Decimal('1.00')

    ventas_hoy = Venta.query.filter(func.date(Venta.fecha) == hoy).all()

    nuevo_cierre = CierreCaja(
        fecha         = hoy,
        monto_usd     = sum(_d(v.pago_efectivo_usd)    for v in ventas_hoy),
        monto_bs      = sum(_d(v.pago_efectivo_bs)      for v in ventas_hoy),
        pago_movil    = sum(_d(v.pago_movil_bs)         for v in ventas_hoy),
        transferencia = sum(_d(v.pago_transferencia_bs) for v in ventas_hoy),
        biopago       = sum(_d(v.biopago_bdv)           for v in ventas_hoy),
        tasa_cierre   = tasa,
    )
    db.session.add(nuevo_cierre)
    db.session.commit()
    flash("✅ Caja cerrada exitosamente.", "success")
    return redirect(url_for('reportes.vista_reportes'))


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
    tasa = _d(tasa_obj.valor) if tasa_obj else Decimal('1.00')

    ventas = Venta.query.filter(Venta.fecha >= start, Venta.fecha < end).all()
    total_ventas_usd = sum(_d(v.total_usd) for v in ventas)
    total_ventas_bs  = (total_ventas_usd * tasa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    num_ventas       = len(ventas)

    detalles = DetalleVenta.query.join(Venta)\
        .filter(Venta.fecha >= start, Venta.fecha < end).all()
    total_costo_usd = sum((_d(d.producto.costo_usd) * d.cantidad for d in detalles), Decimal('0.00'))
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
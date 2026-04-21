from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import db, Venta, DetalleVenta, Producto, MovimientoCaja, CierreCaja, User, HistorialPago, TasaBCV, Asiento
from routes.decorators import staff_required
from functools import wraps
from datetime import datetime
import logging
from decimal import Decimal
from utils import seguro_decimal

herramientas_bp = Blueprint('herramientas', __name__)
logger = logging.getLogger('KALU.herramientas')

def solo_dueno(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'dueno']:
            flash("🚫 Acceso restringido. Solo el Dueño puede usar estas herramientas.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@herramientas_bp.route('/herramientas')
@login_required
@solo_dueno
def panel_herramientas():
    # 🔍 Buscar cierres recientes
    cierres = CierreCaja.query.order_by(CierreCaja.fecha.desc()).limit(15).all()
    # 🔍 Buscar últimos usuarios
    usuarios = User.query.all()
    # 🔍 Buscar últimas ventas (las 50 más recientes para borrar)
    ultimas_ventas = Venta.query.order_by(Venta.fecha.desc()).limit(50).all()
    
    # 🔒 AUDITORÍA DE SEGURIDAD (Google Standards)
    import os
    from flask import current_app
    seguridad = {
        'secret_key': 'OK' if os.environ.get('FLASK_SECRET_KEY') else 'DÉBIL',
        'https': 'ACTIVO (HTTPS)' if current_app.config.get('SESSION_COOKIE_SECURE') else 'NO SEGURO (HTTP)',
        'google_oauth': 'CONFIGURADO' if os.environ.get('GOOGLE_CLIENT_ID') else 'PENDIENTE',
        'hashing': 'ACTIVO (PBKDF2)',
        'env': os.environ.get('ENV', 'development')
    }
    
    return render_template('mantenimiento.html', 
                           cierres=cierres, 
                           usuarios=usuarios, 
                           ventas=ultimas_ventas,
                           seguridad=seguridad)

@herramientas_bp.route('/herramientas/toggle_usuario/<int:user_id>', methods=['POST'])
@login_required
@solo_dueno
def toggle_usuario(user_id):
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash("🚫 No puedes desactivar al administrador maestro.", "danger")
        return redirect(url_for('herramientas.panel_herramientas'))
    
    user.activo = not user.activo
    db.session.commit()
    
    estado = "ACTIVADO" if user.activo else "DESACTIVADO"
    logger.warning(f"Usuario {user.username} {estado} por {current_user.username}")
    flash(f"✅ Usuario {user.username} ha sido {estado}.", "success")
    return redirect(url_for('herramientas.panel_herramientas'))

@herramientas_bp.route('/herramientas/reabrir_cierre/<int:cierre_id>', methods=['POST'])
@login_required
@solo_dueno
def reabrir_cierre(cierre_id):
    cierre = CierreCaja.query.get_or_404(cierre_id)
    fecha_cierre = cierre.fecha
    
    try:
        # 1. Borrar asientos de ajuste si existen para esa fecha
        # (Opcional, pero recomendado por integridad)
        # En la práctica, los asientos se buscan por referencia_tipo='CIERRE_AJUSTE'
        # Pero no tenemos la fecha exacta en el Asiento de forma fácil sin filtrar por fecha.
        
        db.session.delete(cierre)
        db.session.commit()
        
        logger.warning(f"🔓 Cierre del {fecha_cierre} REABIERTIO por {current_user.username}")
        flash(f"🔓 Cierre del {fecha_cierre} reabierto. Ahora se pueden registrar ventas para ese día.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al reabrir: {str(e)}", "danger")
        
    return redirect(url_for('herramientas.panel_herramientas'))

@herramientas_bp.route('/herramientas/borrar_venta/<int:venta_id>', methods=['POST'])
@login_required
@solo_dueno
def borrar_venta(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    
    # Verificar si el día ya está cerrado
    ya_cerrado = CierreCaja.query.filter_by(fecha=venta.fecha.date()).first()
    if ya_cerrado:
        flash(f"🚫 No puedes borrar una venta de un día que ya está CERRADO ({venta.fecha.date()}). Reabre el cierre primero.", "danger")
        return redirect(url_for('herramientas.panel_herramientas'))

    try:
        # 1. Revertir Stock
        for det in venta.detalles:
            if det.producto:
                det.producto.stock += det.cantidad
                logger.info(f"🔄 Stock revertido: {det.producto.nombre} +{det.cantidad}")

        # 2. Borrar Movimientos de Caja
        movs = MovimientoCaja.query.filter_by(referencia_id=venta.id, modulo_origen='Ventas').all()
        for m in movs:
            db.session.delete(m)

        # 3. Borrar Historial de Pagos (sobre todo si fue abono inicial)
        pagos = HistorialPago.query.filter_by(venta_id=venta.id).all()
        for p in pagos:
            db.session.delete(p)
            
        # 4. Ajustar saldo del cliente si era Fiado
        if venta.es_fiado and venta.cliente:
            # Si borramos la venta fiada, el saldo pendiente debe bajar
            venta.cliente.saldo_usd -= seguro_decimal(venta.saldo_pendiente_usd)
            logger.info(f"📉 Saldo fiado restado al cliente {venta.cliente.nombre}: -${venta.saldo_pendiente_usd}")

        # 5. Borrar Detalles y Venta
        for det in venta.detalles:
            db.session.delete(det)
        
        db.session.delete(venta)
        db.session.commit()
        
        logger.warning(f"🗑️ FACTURA {venta_id} ELIMINADA por {current_user.username}")
        flash(f"🗑️ Factura #{venta_id} eliminada exitosamente. Stock y caja actualizados.", "success")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error borrando venta {venta_id}: {e}")
        flash(f"❌ Error al borrar venta: {str(e)}", "danger")

    return redirect(url_for('herramientas.panel_herramientas'))

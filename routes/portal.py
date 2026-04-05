import os
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from models import (
    Cliente,
    Proveedor,
    Venta,
    HistorialPago,
    MovimientoProductor,
    PagoProductor,
    Producto,
    PagoReportado,
    Pedido,
    DetallePedido,
    User,
    Publicidad,
    QuejaSugerencia,
    db
)

portal_bp = Blueprint('portal', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@portal_bp.route('/mi_deuda')
@login_required
def mi_deuda():
    if current_user.role != 'cliente':
        flash('⛔ No tienes permiso para entrar al portal de clientes.', 'danger')
        return redirect(url_for('auth.login'))

    if not current_user.cliente_id or not current_user.cliente:
        flash('⚠️ Tu usuario no está vinculado a ningún cliente.', 'warning')
        return redirect(url_for('auth.login'))

    cliente = current_user.cliente

    ventas = Venta.query.filter_by(cliente_id=cliente.id).order_by(desc(Venta.fecha)).all()
    abonos = HistorialPago.query.filter_by(cliente_id=cliente.id).order_by(desc(HistorialPago.fecha)).all()
    productos = Producto.query.order_by(Producto.nombre.asc()).all()
    pagos_reportados = PagoReportado.query.filter_by(cliente_id=cliente.id).order_by(desc(PagoReportado.fecha_reporte)).all()
    publicidades = Publicidad.query.filter_by(activo=True).order_by(desc(Publicidad.fecha_creacion)).all()

    total_deuda_usd = float(cliente.saldo_usd or 0)
    total_deuda_bs = float(cliente.saldo_bs or 0)

    ventas_pendientes = []
    for v in ventas:
        saldo = float(v.saldo_pendiente_usd or 0)
        if saldo > 0:
            ventas_pendientes.append(v)

    return render_template(
        'mi_deuda.html',
        cliente=cliente,
        ventas_pendientes=ventas_pendientes,
        abonos=abonos,
        productos=productos,
        pagos_reportados=pagos_reportados,
        total_deuda_usd=total_deuda_usd,
        total_deuda_bs=total_deuda_bs,
        publicidades=publicidades
    )


@portal_bp.route('/reportar_pago', methods=['POST'])
@login_required
def reportar_pago():
    if current_user.role != 'cliente':
        flash('⛔ No tienes permiso para reportar pagos.', 'danger')
        return redirect(url_for('auth.login'))

    if not current_user.cliente_id or not current_user.cliente:
        flash('⚠️ Tu usuario no está vinculado a ningún cliente.', 'warning')
        return redirect(url_for('auth.login'))

    cliente = current_user.cliente

    monto_usd = request.form.get('monto_usd', 0) or 0
    monto_bs = request.form.get('monto_bs', 0) or 0
    
    try:
        monto_usd = float(monto_usd)
        monto_bs = float(monto_bs)
    except ValueError:
        monto_usd = 0
        monto_bs = 0

    if monto_usd <= 0 and monto_bs <= 0:
        flash('⚠️ Debes ingresar un monto mayor a cero (USD o Bs).', 'warning')
        return redirect(url_for('portal.mi_deuda'))

    metodo_pago = request.form.get('metodo_pago', '').strip()
    if not metodo_pago:
        flash('⚠️ Debes seleccionar un método de pago.', 'warning')
        return redirect(url_for('portal.mi_deuda'))

    referencia = request.form.get('referencia', '').strip()
    banco = request.form.get('banco', '').strip()
    observacion = request.form.get('observacion', '').strip()
    fecha_pago_str = request.form.get('fecha_pago', '').strip()

    fecha_pago = None
    if fecha_pago_str:
        try:
            fecha_pago = datetime.strptime(fecha_pago_str, '%Y-%m-%d').date()
        except ValueError:
            flash('⚠️ La fecha del pago no es válida.', 'warning')
            return redirect(url_for('portal.mi_deuda'))

    archivo = request.files.get('comprobante')
    nombre_archivo = None

    if archivo and archivo.filename:
        if not allowed_file(archivo.filename):
            flash('⚠️ Formato de imagen no permitido. Usa PNG, JPG, JPEG o WEBP.', 'warning')
            return redirect(url_for('portal.mi_deuda'))

        nombre_seguro = secure_filename(archivo.filename)
        nombre_archivo = f"pago_{cliente.id}_{int(datetime.now().timestamp())}_{nombre_seguro}"

        carpeta_destino = os.path.join(current_app.root_path, 'static', 'comprobantes')
        os.makedirs(carpeta_destino, exist_ok=True)

        ruta_archivo = os.path.join(carpeta_destino, nombre_archivo)
        archivo.save(ruta_archivo)

    pago = PagoReportado(
        cliente_id=cliente.id,
        user_id=current_user.id,
        fecha_pago=fecha_pago,
        monto_usd=monto_usd,
        monto_bs=monto_bs,
        metodo_pago=metodo_pago,
        referencia=referencia,
        banco=banco,
        observacion=observacion,
        imagen_comprobante=nombre_archivo,
        estado='pendiente'
    )

    from models import db
    db.session.add(pago)
    db.session.commit()

    flash('✅ Tu pago fue reportado correctamente y quedó pendiente por validación.', 'success')
    return redirect(url_for('portal.mi_deuda'))

@portal_bp.route('/mi_libreta')
@login_required
def mi_libreta():
    if current_user.role != 'productor':
        flash('⛔ No tienes permiso para entrar al portal de productores.', 'danger')
        return redirect(url_for('auth.login'))

    if not current_user.proveedor_id or not current_user.proveedor:
        flash('⚠️ Tu usuario no está vinculado a ningún productor.', 'warning')
        return redirect(url_for('auth.login'))

    proveedor = current_user.proveedor

    if not proveedor.es_productor:
        flash('⚠️ Este usuario está vinculado a un proveedor, pero no está marcado como productor.', 'warning')
        return redirect(url_for('auth.login'))

    movimientos = MovimientoProductor.query.filter_by(
        proveedor_id=proveedor.id
    ).order_by(desc(MovimientoProductor.fecha)).all()

    pagos = PagoProductor.query.filter_by(
        proveedor_id=proveedor.id
    ).order_by(desc(PagoProductor.fecha)).all()

    saldo_actual = float(proveedor.saldo_pendiente_usd or 0)
    total_debe = sum(float(m.debe or 0) for m in movimientos)
    total_haber = sum(float(m.haber or 0) for m in movimientos)
    total_kilos = sum(float(m.kilos or 0) for m in movimientos)

    productos = Producto.query.order_by(Producto.nombre.asc()).all()
    publicidades = Publicidad.query.filter_by(activo=True).order_by(desc(Publicidad.fecha_creacion)).all()

    return render_template(
        'mi_libreta.html',
        proveedor=proveedor,
        movimientos=movimientos,
        pagos=pagos,
        saldo_actual=saldo_actual,
        total_debe=total_debe,
        total_haber=total_haber,
        total_kilos=total_kilos,
        productos=productos,
        publicidades=publicidades
    )

# ============================================================
# 🚀 API: ENVIAR PEDIDO DESDE EL PORTAL
# ============================================================
@portal_bp.route('/api/crear_pedido', methods=['POST'])
@login_required
def crear_pedido():
    if current_user.role not in ['cliente', 'productor']:
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403

    data = request.get_json()
    items = data.get('items', [])

    if not items:
        return jsonify({'success': False, 'message': 'La lista está vacía'}), 400

    # Determinar si tiene un cliente_id válido
    cliente_id = current_user.cliente_id
    if not cliente_id and current_user.role == 'productor':
        # Si no tiene cliente_id pero es productor, buscamos o creamos un cliente dummy
        cliente_dummy = Cliente.query.filter_by(cedula=current_user.proveedor.rif).first()
        if not cliente_dummy:
            cliente_dummy = Cliente(
                nombre=f"PROD: {current_user.proveedor.nombre}",
                cedula=current_user.proveedor.rif,
                telefono=current_user.proveedor.telefono
            )
            db.session.add(cliente_dummy)
            db.session.flush()
        
        # Asignar el cliente dummy
        cliente_id = cliente_dummy.id
        
    if not cliente_id:
         return jsonify({'success': False, 'message': 'No tiene cuenta de cliente habilitada para pedir. Consulte al administrador.'}), 400

    nuevo_pedido = Pedido(
        cliente_id=cliente_id,
        observacion=data.get('observacion', '')
    )
    db.session.add(nuevo_pedido)
    db.session.flush()

    for item in items:
        db.session.add(DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=int(item['id']),
            cantidad=Decimal(str(item['cantidad']))
        ))

    db.session.commit()
    return jsonify({'success': True, 'message': '✅ ¡Pedido enviado! El cajero lo procesará pronto.'})

@portal_bp.route('/api/enviar_queja', methods=['POST'])
@login_required
def enviar_queja():
    tipo = request.form.get('tipo', 'Queja')
    mensaje = request.form.get('mensaje', '').strip()
    
    if not mensaje:
        flash('⚠️ El mensaje no puede estar vacío.', 'warning')
        return redirect(request.referrer or url_for('index'))
        
    nueva_queja = QuejaSugerencia(
        usuario_id=current_user.id,
        tipo=tipo,
        mensaje=mensaje
    )
    db.session.add(nueva_queja)
    db.session.commit()
    
    flash('✅ Tu mensaje ha sido enviado exitosamente. Gracias por ayudarnos a mejorar.', 'success')
    return redirect(request.referrer or url_for('index'))

@portal_bp.route('/mi_perfil', methods=['GET', 'POST'])
@login_required
def mi_perfil():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user and existing_user.id != current_user.id:
                flash('❌ El nombre de usuario ya está en uso. Por favor, elige otro.', 'danger')
                return redirect(url_for('portal.mi_perfil'))
            current_user.username = username
            
        if password:
            current_user.password = generate_password_hash(password)
            
        db.session.commit()
        flash('✅ Perfil actualizado correctamente.', 'success')
        return redirect(url_for('portal.mi_perfil'))
        
    return render_template('mi_perfil.html')
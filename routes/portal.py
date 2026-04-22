from datetime import datetime
import logging
import os
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from utils import seguro_decimal

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
    db,
    ahora_ve
)

portal_bp = Blueprint('portal', __name__)
logger = logging.getLogger('KALU.portal')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@portal_bp.route('/mi_deuda')
@login_required
def mi_deuda():
    if current_user.role != 'cliente':
        flash('⛔ No tienes permiso para entrar al portal de clientes.', 'danger')
        return redirect(url_for('auth.ingresar'))

    if not current_user.cliente_id or not current_user.cliente:
        flash('⚠️ Tu usuario no está vinculado a ningún cliente.', 'warning')
        return redirect(url_for('auth.ingresar'))

    cliente = current_user.cliente

    ventas = Venta.query.filter_by(cliente_id=cliente.id).order_by(desc(Venta.fecha)).all()
    abonos = HistorialPago.query.filter_by(cliente_id=cliente.id).order_by(desc(HistorialPago.fecha)).all()
    productos = Producto.query.order_by(Producto.nombre.asc()).all()
    pagos_reportados = PagoReportado.query.filter_by(cliente_id=cliente.id).order_by(desc(PagoReportado.fecha_reporte)).all()
    publicidades_obj = Publicidad.query.filter_by(activo=True).order_by(desc(Publicidad.fecha_creacion)).all()
    publicidades = [{'tipo': p.tipo, 'archivo_url': p.archivo_url, 'titulo': p.titulo, 'descripcion': p.descripcion} for p in publicidades_obj]

    total_deuda_usd = seguro_decimal(cliente.saldo_usd)
    total_deuda_bs = seguro_decimal(cliente.saldo_bs)

    ventas_pendientes = []
    for v in ventas:
        saldo = seguro_decimal(v.saldo_pendiente_usd)
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
    if current_user.role not in ['cliente', 'productor']:
        flash('⛔ No tienes permiso para reportar pagos.', 'danger')
        return redirect(url_for('auth.ingresar'))

    # Detectar el ente que reporta
    cliente_id = None
    proveedor_id = None
    redirect_target = 'portal.mi_deuda'

    if current_user.role == 'cliente':
        if not current_user.cliente_id:
            flash('⚠️ Tu usuario no está vinculado a ningún cliente.', 'warning')
            return redirect(url_for('auth.ingresar'))
        cliente_id = current_user.cliente_id
        redirect_target = 'portal.mi_deuda'
    else: # productor
        if not current_user.proveedor_id:
            flash('⚠️ Tu usuario no está vinculado a ningún productor.', 'warning')
            return redirect(url_for('auth.ingresar'))
        proveedor_id = current_user.proveedor_id
        redirect_target = 'portal.mi_libreta'

    monto_usd = request.form.get('monto_usd', 0) or 0
    monto_bs = request.form.get('monto_bs', 0) or 0
    
    try:
        monto_usd = seguro_decimal(monto_usd)
        monto_bs = seguro_decimal(monto_bs)
    except (ValueError, TypeError, InvalidOperation):
        monto_usd = Decimal('0')
        monto_bs = Decimal('0')

    if monto_usd <= 0 and monto_bs <= 0:
        flash('⚠️ Debes ingresar un monto mayor a cero (USD o Bs).', 'warning')
        return redirect(url_for(redirect_target))

    metodo_pago = request.form.get('metodo_pago', '').strip()
    if not metodo_pago:
        flash('⚠️ Debes seleccionar un método de pago.', 'warning')
        return redirect(url_for(redirect_target))

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
            return redirect(url_for(redirect_target))

    archivo = request.files.get('comprobante')
    nombre_archivo = None

    if archivo and archivo.filename:
        if not allowed_file(archivo.filename):
            flash('⚠️ Formato de imagen no permitido. Usa PNG, JPG, JPEG o WEBP.', 'warning')
            return redirect(url_for(redirect_target))

        target_id = cliente_id if cliente_id else proveedor_id
        nombre_seguro = secure_filename(archivo.filename)
        nombre_archivo = f"pago_{target_id}_{int(datetime.now().timestamp())}_{nombre_seguro}"

        carpeta_destino = os.path.join(current_app.root_path, 'static', 'comprobantes')
        os.makedirs(carpeta_destino, exist_ok=True)

        ruta_archivo = os.path.join(carpeta_destino, nombre_archivo)
        archivo.save(ruta_archivo)

    pago = PagoReportado(
        cliente_id=cliente_id,
        proveedor_id=proveedor_id,
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

    db.session.add(pago)
    db.session.commit()

    flash('✅ Tu pago fue reportado correctamente y quedó pendiente por validación.', 'success')
    return redirect(url_for(redirect_target))

@portal_bp.route('/mi_libreta')
@login_required
def mi_libreta():
    if current_user.role != 'productor':
        flash('⛔ No tienes permiso para entrar al portal de productores.', 'danger')
        return redirect(url_for('auth.ingresar'))

    if not current_user.proveedor_id or not current_user.proveedor:
        flash('⚠️ Tu usuario no está vinculado a ningún productor.', 'warning')
        return redirect(url_for('auth.ingresar'))

    proveedor = current_user.proveedor

    if not proveedor.es_productor:
        flash('⚠️ Este usuario está vinculado a un proveedor, pero no está marcado como productor.', 'warning')
        return redirect(url_for('auth.ingresar'))

    movimientos = MovimientoProductor.query.filter_by(
        proveedor_id=proveedor.id
    ).order_by(desc(MovimientoProductor.fecha)).all()

    pagos = PagoProductor.query.filter_by(
        proveedor_id=proveedor.id
    ).order_by(desc(PagoProductor.fecha)).all()

    # --- NUEVOS CÁLCULOS PARA TARJETAS SOLICITADAS ---
    ahora = ahora_ve()
    anio_actual = ahora.year
    semana_actual = ahora.isocalendar()[1]

    # 1. Queso de la semana
    total_kilos_semana = sum(seguro_decimal(m.kilos) for m in movimientos 
                             if m.anio == anio_actual and m.semana_del_anio == semana_actual)

    # 2. Queso del año (se reinicia cada año)
    total_kilos_anio = sum(seguro_decimal(m.kilos) for m in movimientos if m.anio == anio_actual)

    # 3. Puntos Ranking
    # Fórmula: (kilos/10) + (semanas_fiel * 10) + (compras_pos/5)
    semanas_fiel = len(set(m.semana_del_anio for m in movimientos if m.anio == anio_actual and m.tipo == 'ENTREGA_QUESO'))
    compras_pos = sum(seguro_decimal(m.monto_usd) for m in movimientos if m.anio == anio_actual and m.tipo == 'COMPRA_POS')
    puntos_ranking = int((total_kilos_anio / 10) + (Decimal(str(semanas_fiel)) * 10) + (compras_pos / 5))

    # 4. Queso Histórico (Total de siempre)
    total_kilos_historico = sum(seguro_decimal(m.kilos) for m in movimientos)

    saldo_actual = seguro_decimal(proveedor.saldo_pendiente_usd)
    total_debe = sum(seguro_decimal(m.debe) for m in movimientos)
    total_haber = sum(seguro_decimal(m.haber) for m in movimientos)

    productos = Producto.query.order_by(Producto.nombre.asc()).all()
    publicidades_obj = Publicidad.query.filter_by(activo=True).order_by(desc(Publicidad.fecha_creacion)).all()
    publicidades = [{'tipo': p.tipo, 'archivo_url': p.archivo_url, 'titulo': p.titulo, 'descripcion': p.descripcion} for p in publicidades_obj]
    pagos_reportados = PagoReportado.query.filter_by(proveedor_id=proveedor.id).order_by(desc(PagoReportado.fecha_reporte)).all()

    return render_template(
        'mi_libreta.html',
        proveedor=proveedor,
        movimientos=movimientos,
        pagos=pagos,
        saldo_actual=saldo_actual,
        total_debe=total_debe,
        total_haber=total_haber,
        total_kilos_semana=total_kilos_semana,
        total_kilos_anio=total_kilos_anio,
        total_kilos_historico=total_kilos_historico,
        puntos_ranking=puntos_ranking,
        productos=productos,
        publicidades=publicidades,
        pagos_reportados=pagos_reportados
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

@portal_bp.route('/api/notificaciones')
@login_required
def api_notificaciones():
    if current_user.role not in ['cliente', 'productor']:
        return jsonify([])
    
    # Buscar pedidos en estado 'recibido' o 'listo'
    cliente_id = current_user.cliente_id
    if not cliente_id and current_user.role == 'productor' and current_user.proveedor:
        cliente_dummy = Cliente.query.filter_by(cedula=current_user.proveedor.rif).first()
        if cliente_dummy:
            cliente_id = cliente_dummy.id

    if not cliente_id:
        return jsonify([])

    pedidos = Pedido.query.filter(
        Pedido.cliente_id == cliente_id,
        Pedido.estado.in_(['pendiente', 'recibido', 'listo'])
    ).all()
    
    pedidos_data = []
    for p in pedidos:
        pedidos_data.append({
            'id': p.id,
            'estado': p.estado,
            'fecha': p.fecha.strftime('%H:%M')
        })
    
    # Obtener stocks actuales para actualizar el catálogo dinámicamente
    productos = Producto.query.all()
    stocks = {p.id: float(p.stock or 0) for p in productos}
    
    return jsonify({
        'pedidos': pedidos_data,
        'stocks': stocks
    })

@portal_bp.route('/api/limpiar_pedido/<int:id>', methods=['POST'])
@login_required
def limpiar_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    # Solo puede limpiar sus propios pedidos
    cliente_id = current_user.cliente_id
    if not cliente_id and current_user.role == 'productor' and current_user.proveedor:
        cliente_dummy = Cliente.query.filter_by(cedula=current_user.proveedor.rif).first()
        if cliente_dummy:
            cliente_id = cliente_dummy.id
            
    if pedido.cliente_id != cliente_id:
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
        
    pedido.estado = 'finalizado'
    db.session.commit()
    return jsonify({'success': True})

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
        email = request.form.get('email')
        password = request.form.get('password')
        
        if username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user and existing_user.id != current_user.id:
                flash('❌ El nombre de usuario ya está en uso. Por favor, elige otro.', 'danger')
                return redirect(url_for('portal.mi_perfil'))
            current_user.username = username

        if email:
            existing_email = User.query.filter_by(email=email).first()
            if existing_email and existing_email.id != current_user.id:
                flash('❌ El correo electrónico ya está en uso por otra cuenta.', 'danger')
                return redirect(url_for('portal.mi_perfil'))
            current_user.email = email
            
        if password:
            current_user.password = generate_password_hash(password)
            
        db.session.commit()
        flash('✅ Perfil actualizado correctamente.', 'success')
        
    return render_template('mi_perfil.html')

@portal_bp.route('/eliminar_pago_reportado/<int:id>', methods=['POST'])
@login_required
def borrar_pago_propio(id):
    pago = PagoReportado.query.get_or_404(id)
    
    # Verificar propiedad
    if current_user.role == 'cliente':
        if pago.cliente_id != current_user.cliente_id:
            return jsonify({'success': False, 'message': 'No tienes permiso'}), 403
    elif current_user.role == 'productor':
        if pago.proveedor_id != current_user.proveedor_id:
            return jsonify({'success': False, 'message': 'No tienes permiso'}), 403
    else:
        return jsonify({'success': False, 'message': 'Rol no permitido'}), 403

    try:
        # Si tiene imagen, intentar borrarla del disco
        if pago.imagen_comprobante:
            file_path = os.path.join(current_app.root_path, 'static', 'comprobantes', pago.imagen_comprobante)
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass

        db.session.delete(pago)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Pago eliminado del historial'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

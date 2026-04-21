from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, session
from models import db, User, HistorialPago, PagoProductor, MovimientoProductor, MovimientoCaja, TasaBCV, Cliente, Proveedor
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from functools import wraps
from datetime import datetime, timedelta
import pytz
from decimal import Decimal
import logging
from utils import seguro_decimal
from routes.contabilidad import registrar_asiento

usuarios_bp = Blueprint('usuarios', __name__)
logger = logging.getLogger('KALU.usuarios')

# ============================================================
# 🔑 VERIFICAR PIN DE SUPERVISOR (API)
# ============================================================
@usuarios_bp.route('/api/verify_pin', methods=['POST'])
@login_required
def verify_pin():
    data = request.get_json()
    pin = data.get('pin') if data else None
    
    if not pin:
        return {"success": False, "message": "PIN no proporcionado"}, 400
    
    # Buscar usuario con ese PIN que sea admin o supervisor
    # Usamos filter para mayor seguridad
    supervisor = User.query.filter_by(pin=str(pin)).filter(User.role.in_(['admin', 'supervisor', 'dueno'])).first()
    
    if supervisor:
        logger.info(f"✅ PIN verificado correctamente por: {supervisor.username}")
        return {"success": True, "username": supervisor.username}
    else:
        logger.warning(f"❌ Intento de PIN fallido por usuario: {current_user.username}")
        return {"success": False, "message": "PIN incorrecto o nivel de acceso insuficiente"}, 401


# ============================================================
# 🔒 DECORADOR DE SEGURIDAD (Solo el Gran Jefe entra aquí)
# ============================================================
def solo_admin_maestro(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'dueno']:
            flash("🚫 Acceso denegado. Solo el Administrador o el Dueño pueden gestionar usuarios.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# 👥 LISTAR USUARIOS
# ============================================================
@usuarios_bp.route('/usuarios')
@login_required
@solo_admin_maestro
def lista_usuarios():
    todos = User.query.all()
    
    # 🔍 BUSCAR PAGOS QUE LLEGAN DE AFUERA
    pagos_clientes = HistorialPago.query.filter(HistorialPago.metodo_pago.like('%Pendiente%')).all()
    pagos_productores = PagoProductor.query.filter(PagoProductor.metodo.like('%Pendiente%')).all()

    # 📊 CÁLCULOS PARA EL RESUMEN SUPERIOR (Solicitado por el usuario)
    total_deuda_clientes = db.session.query(db.func.sum(db.func.coalesce(Cliente.saldo_usd, 0))).scalar() or 0
    total_haber_productores = db.session.query(db.func.sum(db.func.coalesce(Proveedor.saldo_pendiente_usd, 0))).scalar() or 0
    
    # Queso de la semana (Lunes a hoy)
    from datetime import datetime
    import pytz
    hoy = datetime.now(pytz.timezone('America/Caracas')).replace(tzinfo=None)
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    total_queso_semana = db.session.query(db.func.sum(db.func.coalesce(MovimientoProductor.kilos, 0)))\
        .filter(MovimientoProductor.fecha >= inicio_semana)\
        .filter(MovimientoProductor.tipo.in_(['recepcion', 'compra', 'ARRIME', 'Recepcion', 'RECEPCION']))\
        .scalar() or 0
    
    # 📊 CORDURA (CLIENTES Y PRODUCTORES PARA VINCULAR)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    produc_list = Proveedor.query.filter_by(es_productor=True).order_by(Proveedor.nombre).all()

    return render_template('usuarios/lista.html', 
                           usuarios=todos, 
                           pagos_clientes=pagos_clientes, 
                           pagos_productores=pagos_productores,
                           total_deuda_clientes=total_deuda_clientes,
                           total_haber_productores=total_haber_productores,
                           total_queso_semana=total_queso_semana,
                           clientes=clientes,
                           proveedores=produc_list)

# ============================================================
# 🏠 REDIRECCIÓN INTELIGENTE A "MI CUENTA"
# ============================================================
@usuarios_bp.route('/mi_cuenta')
@login_required
def mi_cuenta():
    if current_user.role == 'cliente':
        return redirect(url_for('portal.mi_deuda'))
    elif current_user.role == 'productor':
        return redirect(url_for('portal.mi_libreta'))
    elif current_user.role == 'admin' or current_user.role == 'supervisor':
        return redirect(url_for('pos.pos'))
    return redirect(url_for('index'))
# ============================================================
# ➕ CREAR NUEVO USUARIO (Cajero, Supervisor o Admin)
# ============================================================
@usuarios_bp.route('/usuarios/crear', methods=['POST'])
@login_required
@solo_admin_maestro
def crear_usuario():
    username = request.form.get('username')
    password = request.form.get('password')
    role     = request.form.get('role', 'cajero')
    email    = request.form.get('email', '').strip()
    pin      = request.form.get('pin', '').strip()
    cliente_id = request.form.get('cliente_id')
    proveedor_id = request.form.get('proveedor_id')

    if not username or not password:
        flash("⚠️ Usuario y contraseña son obligatorios.", "warning")
        return redirect(url_for('usuarios.lista_usuarios'))

    # Verificar si ya existe
    if User.query.filter_by(username=username).first():
        flash(f"❌ El usuario '{username}' ya existe.", "danger")
        return redirect(url_for('usuarios.lista_usuarios'))
        
    if email and User.query.filter_by(email=email).first():
        flash(f"❌ El correo '{email}' ya está en uso.", "danger")
        return redirect(url_for('usuarios.lista_usuarios'))

    nuevo = User(
        username = username,
        password = generate_password_hash(password, method='pbkdf2:sha256'),
        role     = role,
        email    = email if email else None,
        pin      = pin if pin else None,
        cliente_id = cliente_id if role == 'cliente' and cliente_id else None,
        proveedor_id = proveedor_id if role == 'productor' and proveedor_id else None
    )
    
    db.session.add(nuevo)
    db.session.commit()
    
    logger.info(f"Usuario creado: {username} con rol {role} por {current_user.username}")
    flash(f"✅ Usuario '{username}' creado exitosamente. {'(Vinculado a ' + email + ')' if email else ''}", "success")
    return redirect(url_for('usuarios.lista_usuarios'))

# ============================================================
# 🔑 CAMBIAR CONTRASEÑA (Por si al cajero se le olvida)
# ============================================================
@usuarios_bp.route('/usuarios/reset/<int:id>', methods=['POST'])
@login_required
@solo_admin_maestro
def reset_password(id):
    user = User.query.get_or_404(id)
    nueva_pass = request.form.get('nueva_password')
    
    if user.username == 'admin' and current_user.username != 'admin':
        flash("🚫 No puedes resetear al Admin Maestro.", "danger")
        return redirect(url_for('usuarios.lista_usuarios'))

    user.password = generate_password_hash(nueva_pass, method='pbkdf2:sha256')
    db.session.commit()
    
    logger.info(f"Contraseña reseteada para usuario: {user.username} por {current_user.username}")
    flash(f"🔑 Contraseña de '{user.username}' actualizada.", "success")
    return redirect(url_for('usuarios.lista_usuarios'))

# ============================================================
# 📧 ACTUALIZAR PERFIL (Email y Rol)
# ============================================================
@usuarios_bp.route('/usuarios/actualizar/<int:id>', methods=['POST'])
@login_required
@solo_admin_maestro
def actualizar_usuario(id):
    user = User.query.get_or_404(id)
    email = request.form.get('email', '').strip()
    role = request.form.get('role', user.role)
    pin = request.form.get('pin', '').strip()
    cliente_id = request.form.get('cliente_id')
    proveedor_id = request.form.get('proveedor_id')

    if user.username == 'admin' and current_user.username != 'admin':
        flash("🚫 No puedes modificar al Admin Maestro.", "danger")
        return redirect(url_for('usuarios.lista_usuarios'))

    # Verificar disponibilidad de email
    if email:
        exist_email = User.query.filter(User.email == email, User.id != id).first()
        if exist_email:
            flash(f"❌ El correo '{email}' ya lo usa otro usuario.", "danger")
            return redirect(url_for('usuarios.lista_usuarios'))

    user.email = email if email else None
    user.role = role
    user.pin = pin if pin else None
    user.cliente_id = cliente_id if role == 'cliente' and cliente_id else None
    user.proveedor_id = proveedor_id if role == 'productor' and proveedor_id else None
    db.session.commit()
    
    logger.info(f"Usuario actualizado: {user.username} (Rol: {role}) por {current_user.username}")
    flash(f"✅ Perfil de '{user.username}' actualizado.", "success")
    return redirect(url_for('usuarios.lista_usuarios'))

# ============================================================
# 🗑️ ELIMINAR USUARIO
# ============================================================
@usuarios_bp.route('/usuarios/eliminar/<int:id>')
@login_required
@solo_admin_maestro
def eliminar_usuario(id):
    user = User.query.get_or_404(id)
    
    if user.username == 'admin':
        flash("🚫 ¡Mano, no te puedes eliminar a ti mismo!", "danger")
        return redirect(url_for('usuarios.lista_usuarios'))

    db.session.delete(user)
    db.session.commit()
    
    logger.warning(f"Usuario eliminado: {user.username} por {current_user.username}")
    flash(f"🗑️ Usuario '{user.username}' eliminado.", "info")
    return redirect(url_for('usuarios.lista_usuarios'))

# ============================================================
# ✅ APROBAR / ❌ RECHAZAR PAGOS (GESTIÓN ADMIN)
# ============================================================

@usuarios_bp.route('/usuarios/aprobar_pago/<tipo>/<int:id>')
@login_required
@solo_admin_maestro
def aprobar_pago(tipo, id):
    try:
        tasa_obj = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
        tasa = seguro_decimal(tasa_obj.valor) if tasa_obj and tasa_obj.valor else Decimal('1.00')

        if tipo == 'cliente':
            pago = HistorialPago.query.get_or_404(id)
            pago.metodo_pago = pago.metodo_pago.replace(" - Pendiente Verificacion", "")
            
            # 📓 CONTABILIDAD: Caja vs Cuentas por Cobrar
            registrar_asiento(
                descripcion=f"ABONO CLIENTE VERIFICADO: {pago.cliente.nombre}",
                tasa=tasa,
                referencia_tipo='ABONO_CLIENTE',
                referencia_id=pago.id,
                movimientos=[
                    {'cuenta_codigo': '1.1.01.03', 'debe_usd': pago.monto_usd, 'debe_bs': pago.monto_usd * tasa},
                    {'cuenta_codigo': '1.1.02.01', 'haber_usd': pago.monto_usd, 'haber_bs': pago.monto_usd * tasa},
                ]
            )
            # 💰 CAJA: Banco (Ingreso)
            nuevo_mov = MovimientoCaja(
                tipo_caja='Banco', tipo_movimiento='INGRESO', categoria='Abono Cliente',
                monto=pago.monto_usd, tasa_dia=tasa, descripcion=f"Pago Móvil verificado: {pago.cliente.nombre}",
                modulo_origen='Usuarios', user_id=current_user.id
            )
            db.session.add(nuevo_mov)

        else: # productor
            pago = PagoProductor.query.get_or_404(id)
            pago.metodo = pago.metodo.replace(" - Pendiente Verificacion", "")
            
            # 📓 CONTABILIDAD: Cuentas por Pagar vs Caja
            registrar_asiento(
                descripcion=f"PAGO PRODUCTOR VERIFICADO: {pago.proveedor.nombre}",
                tasa=tasa,
                referencia_tipo='PAGO_PRODUCTOR',
                referencia_id=pago.id,
                movimientos=[
                    {'cuenta_codigo': '2.1.01.01', 'debe_usd': pago.monto_usd, 'debe_bs': pago.monto_usd * tasa},
                    {'cuenta_codigo': '1.1.01.03', 'haber_usd': pago.monto_usd, 'haber_bs': pago.monto_usd * tasa},
                ]
            )
            # 💰 CAJA: Banco (Egreso - pues sale dinero para pagar al productor)
            # NOTA: En este caso el productor SUBIÓ un pago? 
            # Si el productor reporta que le pagamos, significa que YA salió el dinero.
            nuevo_mov = MovimientoCaja(
                tipo_caja='Banco', tipo_movimiento='EGRESO', categoria='Pago Productor',
                monto=pago.monto_usd, tasa_dia=tasa, descripcion=f"Pago verificado a productor: {pago.proveedor.nombre}",
                modulo_origen='Usuarios', user_id=current_user.id
            )
            db.session.add(nuevo_mov)

        db.session.commit()
        logger.info(f"Pago aprobado: {tipo} ID {id} por {current_user.username}")
        flash("✅ Pago verificado y registrado en contabilidad.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al aprobar: {str(e)}", "danger")

    return redirect(url_for('usuarios.lista_usuarios'))

@usuarios_bp.route('/usuarios/rechazar_pago/<tipo>/<int:id>')
@login_required
@solo_admin_maestro
def rechazar_pago(tipo, id):
    try:
        if tipo == 'cliente':
            pago = HistorialPago.query.get_or_404(id)
            # RESTAURAR SALDO (porque se restó al subir)
            cliente = pago.cliente
            cliente.saldo_usd = seguro_decimal(cliente.saldo_usd) + seguro_decimal(pago.monto_usd)
            db.session.delete(pago)
        else:
            pago = PagoProductor.query.get_or_404(id)
            # RESTAURAR SALDO
            proveedor = pago.proveedor
            proveedor.saldo_pendiente_usd = seguro_decimal(proveedor.saldo_pendiente_usd) + seguro_decimal(pago.monto_usd)
            db.session.delete(pago)

        db.session.commit()
        logger.warning(f"Pago rechazado: {tipo} ID {id} por {current_user.username}")
        flash("🗑️ Pago rechazado y saldo restaurado.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al rechazar: {str(e)}", "danger")

    return redirect(url_for('usuarios.lista_usuarios'))

def crear_acceso_sistema(objeto, tipo):
    """
    objeto: puede ser un Cliente o un Proveedor
    tipo: 'cliente' o 'productor'
    """
    # Usuario: Cédula o RIF (Limpiamos y normalizamos)
    raw_id = objeto.cedula if tipo == 'cliente' else objeto.rif
    if not raw_id:
        return None, None

    username = "".join(filter(str.isalnum, raw_id)).upper()
    
    # Verificar si el usuario ya existe para evitar errores de duplicado
    existente = User.query.filter_by(username=username).first()
    if existente:
        # Vincular si no estaba vinculado
        if tipo == 'cliente' and not existente.cliente_id:
            existente.cliente_id = objeto.id
        elif tipo == 'productor' and not existente.proveedor_id:
            existente.proveedor_id = objeto.id
        db.session.commit()
        return username, "Ya Existía (Vinculado)"

    # Clave: últimos 4 dígitos
    # Intentamos extraer solo números para la clave por si el RIF tiene guiones o letras
    solo_numeros = "".join(filter(str.isdigit, username))
    if len(solo_numeros) >= 4:
        password_final = solo_numeros[-4:]
    else:
        # Si no hay suficientes números, usamos los últimos 4 caracteres del username original
        password_final = username[-4:] if len(username) >= 4 else "1234"
    
    nuevo_usuario = User(
        username=username,
        password=generate_password_hash(password_final, method='pbkdf2:sha256'),
        role=tipo,
        cliente_id=objeto.id if tipo == 'cliente' else None,
        proveedor_id=objeto.id if tipo == 'productor' else None
    )
    db.session.add(nuevo_usuario)
    db.session.commit()
    logger.info(f"Usuario auto-creado: {username} para {tipo} ID {objeto.id}")
    return username, password_final

@usuarios_bp.route('/usuarios/generar_acceso/<int:proveedor_id>')
@login_required
@solo_admin_maestro
def generar_acceso_productor(proveedor_id):
    prov = Proveedor.query.get_or_404(proveedor_id)
    
    # Verificar si ya tiene usuario
    if prov.usuario:
        flash(f"⚠️ El productor {prov.nombre} ya tiene un usuario asignado: @{prov.usuario.username}", "warning")
        return redirect(request.referrer or url_for('productores.libreta'))

    try:
        user, clave = crear_acceso_sistema(prov, 'productor')
        if user:
            flash(f"✅ Acceso creado para {prov.nombre}. Usuario: {user} | Clave: {clave}", "success")
        else:
            flash("❌ Error: El productor no tiene RIF registrado.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al crear acceso: {str(e)}", "danger")
    
    return redirect(request.referrer or url_for('productores.libreta'))

@usuarios_bp.route('/usuarios/generar_acceso_cliente/<int:cliente_id>')
@login_required
@solo_admin_maestro
def generar_acceso_cliente(cliente_id):
    cli = Cliente.query.get_or_404(cliente_id)
    
    # Verificar si ya tiene usuario
    if cli.usuario:
        flash(f"⚠️ El cliente {cli.nombre} ya tiene un usuario asignado: @{cli.usuario.username}", "warning")
        return redirect(request.referrer or url_for('clientes.lista_clientes'))

    try:
        user, clave = crear_acceso_sistema(cli, 'cliente')
        if user:
            flash(f"✅ Acceso creado para {cli.nombre}. Usuario: {user} | Clave: {clave}", "success")
        else:
            flash("❌ Error: El cliente no tiene Cédula registrada.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al crear acceso: {str(e)}", "danger")
    
    return redirect(request.referrer or url_for('clientes.lista_clientes'))

# ============================================================
# 💸 SUBIR PAGO MÓVIL (Cliente o Productor)
# ============================================================
@usuarios_bp.route('/subir_pago', methods=['POST'])
@login_required
def subir_pago():
    monto = request.form.get('monto')

    if not monto:
        flash("⚠️ Debes ingresar un monto.", "warning")
        return redirect(url_for('usuarios.mi_cuenta'))

    try:
        monto = seguro_decimal(monto)

        # 🔵 SI ES CLIENTE (FIADO)
        if current_user.cliente:
            cliente = current_user.cliente

            # Registrar el pago en historial
            pago = HistorialPago(
                cliente_id=cliente.id,
                monto_usd=monto,
                metodo_pago="Pago Movil - Pendiente Verificacion"
            )
            db.session.add(pago)

            # Bajar la deuda
            cliente.saldo_usd = seguro_decimal(cliente.saldo_usd) - monto
            db.session.commit()

            logger.info(f"Cliente {cliente.nombre} subió pago: ${monto}")
            flash(f"✅ Pago de ${monto:.2f} enviado. Pendiente de verificación.", "success")

        # 🟢 SI ES PRODUCTOR (QUESERO)
        elif current_user.proveedor:
            proveedor = current_user.proveedor

            # Registrar el pago
            pago = PagoProductor(
                proveedor_id=proveedor.id,
                monto_usd=monto,
                metodo="Pago Movil - Pendiente Verificacion",
                descripcion="Pago subido por el productor desde su cuenta"
            )
            db.session.add(pago)

            # Bajar la deuda del productor
            proveedor.saldo_pendiente_usd = seguro_decimal(proveedor.saldo_pendiente_usd) - monto
            db.session.commit()

            logger.info(f"Productor {proveedor.nombre} subió pago: ${monto}")
            flash(f"✅ Pago de ${monto:.2f} registrado. Pendiente de verificación.", "success")

        else:
            flash("❌ No tienes un perfil asignado.", "danger")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al procesar el pago: {str(e)}", "danger")

    return redirect(url_for('usuarios.mi_cuenta'))
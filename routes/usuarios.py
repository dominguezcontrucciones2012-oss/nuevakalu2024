from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from models import db, User, HistorialPago, PagoProductor, MovimientoProductor
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from functools import wraps


usuarios_bp = Blueprint('usuarios', __name__)

# ============================================================
# 🔒 DECORADOR DE SEGURIDAD (Solo el Gran Jefe entra aquí)
# ============================================================
def solo_admin_maestro(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("🚫 Acceso denegado. Solo el Administrador Maestro puede gestionar usuarios.", "danger")
            return redirect(url_for('index')) # O a tu ruta principal
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
    
    return render_template('usuarios/lista.html', 
                           usuarios=todos, 
                           pagos_clientes=pagos_clientes, 
                           pagos_productores=pagos_productores)
# ============================================================
# ➕ CREAR NUEVO USUARIO (Cajero, Supervisor o Admin)
# ============================================================
@usuarios_bp.route('/usuarios/crear', methods=['POST'])
@login_required
@solo_admin_maestro
def crear_usuario():
    username = request.form.get('username').strip().lower()
    password = request.form.get('password')
    role     = request.form.get('role')

    if not username or not password:
        flash("⚠️ Usuario y contraseña son obligatorios.", "warning")
        return redirect(url_for('usuarios.lista_usuarios'))

    # Verificar si ya existe
    existe = User.query.filter_by(username=username).first()
    if existe:
        flash(f"❌ El usuario '{username}' ya existe.", "danger")
        return redirect(url_for('usuarios.lista_usuarios'))

    nuevo = User(
        username = username,
        password = generate_password_hash(password, method='pbkdf2:sha256'),
        role     = role
    )
    
    db.session.add(nuevo)
    db.session.commit()
    
    flash(f"✅ Usuario '{username}' creado como {role.upper()} exitosamente.", "success")
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
    
    flash(f"🔑 Contraseña de '{user.username}' actualizada.", "success")
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
    
    flash(f"🗑️ Usuario '{user.username}' eliminado.", "info")
    return redirect(url_for('usuarios.lista_usuarios'))

def crear_acceso_sistema(objeto, tipo):
    """
    objeto: puede ser un Cliente o un Proveedor
    tipo: 'cliente' o 'productor'
    """
    # Usuario: Cédula o RIF
    username = objeto.cedula if tipo == 'cliente' else objeto.rif
    # Clave: últimos 4 de la Cédula/RIF
    password = username[-4:] if len(username) >= 4 else "1234"
    
    nuevo_usuario = User(
        username=username,
        password=generate_password_hash(password),
        role=tipo,
        cliente_id=objeto.id if tipo == 'cliente' else None,
        proveedor_id=objeto.id if tipo == 'productor' else None
    )
    db.session.add(nuevo_usuario)
    db.session.commit()
    return username, password

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
        monto = float(monto)

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
            cliente.saldo_usd = float(cliente.saldo_usd) - monto
            db.session.commit()

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
            proveedor.saldo_pendiente_usd = float(proveedor.saldo_pendiente_usd) - monto
            db.session.commit()

            flash(f"✅ Pago de ${monto:.2f} registrado. Pendiente de verificación.", "success")

        else:
            flash("❌ No tienes un perfil asignado.", "danger")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al procesar el pago: {str(e)}", "danger")

    return redirect(url_for('usuarios.mi_cuenta'))
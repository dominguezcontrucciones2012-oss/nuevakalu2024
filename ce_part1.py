import os
import pandas as pd
from decimal import Decimal
from datetime import datetime
from utils import seguro_decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from functools import wraps
from flask import abort
from models import (db, Cliente, Producto, Proveedor, Venta, DetalleVenta,
                    Compra, CompraDetalle, CuentaPorPagar, HistorialPago, TasaBCV,
                    MovimientoCaja, AuditoriaInventario)
from routes.contabilidad import registrar_asiento

cargar_bp = Blueprint('cargar', __name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'importar_aqui')
PLANTILLAS_FOLDER = os.path.join(os.getcwd(), 'static', 'plantillas')

# ============================================================
# 🔒 DECORADOR DE SEGURIDAD
# ============================================================
def solo_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("⚠️ Debes iniciar sesión primero.", "warning")
            return redirect(url_for('auth.ingresar'))
        if current_user.role not in ['admin', 'supervisor']:
            flash("🚫 No tienes permiso para acceder a esta sección.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xls', 'xlsx'}

def guardar_archivo(file):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filename = secure_filename(file.filename)
    ruta = os.path.join(UPLOAD_FOLDER, filename)
    file.save(ruta)
    return ruta

# ============================================================
#   PANEL PRINCIPAL DE CARGA 🔒
# ============================================================
@cargar_bp.route('/cargar')
@login_required
@solo_admin
def panel_cargar():
    return render_template('cargar_excel.html')

# ============================================================
#   1. CLIENTES 🔒
# ============================================================
@cargar_bp.route('/cargar/clientes', methods=['POST'])
@login_required
@solo_admin
def cargar_clientes():
    file = request.files.get('archivo')
    if not file or not allowed_file(file.filename):
        flash('Archivo inválido. Usa .xlsx', 'danger')
        return redirect(url_for('cargar.panel_cargar'))

    ruta = guardar_archivo(file)
    try:
        df = pd.read_excel(ruta)
        df.columns = [c.strip().lower() for c in df.columns]

        creados = actualizados = errores = 0
        for _, row in df.iterrows():
            try:
                nombre = str(row.get('nombre', '')).strip()
                cedula = str(row.get('cedula', '')).strip()
                if not nombre or not cedula or cedula == 'nan':
                    continue

                cliente = Cliente.query.filter_by(cedula=cedula).first()
                if cliente:
                    cliente.nombre    = nombre
                    cliente.telefono  = str(row.get('telefono', '') or '').strip()
                    cliente.direccion = str(row.get('direccion', '') or '').strip()
                    actualizados += 1
                else:
                    fecha_nac = None
                    fn_raw = row.get('fecha_nacimiento')
                    if pd.notna(fn_raw):
                        try:
                            fecha_nac = pd.to_datetime(fn_raw).date()
                        except:
                            pass

                    cliente = Cliente(
                        nombre           = nombre,
                        cedula           = cedula,
                        telefono         = str(row.get('telefono', '') or '').strip(),
                        direccion        = str(row.get('direccion', '') or '').strip(),
                        fecha_nacimiento = fecha_nac,
                        saldo_usd        = seguro_decimal(row.get('saldo_usd')),
                        saldo_bs         = seguro_decimal(row.get('saldo_bs')),
                        puntos           = int(row.get('puntos', 0) or 0),
                    )
                    db.session.add(cliente)
                    creados += 1
            except Exception:
                errores += 1

        db.session.commit()
        flash(f'✅ Clientes: {creados} creados, {actualizados} actualizados, {errores} errores.', 'success')
    except Exception as e:
        flash(f'❌ Error procesando archivo: {str(e)}', 'danger')

    return redirect(url_for('cargar.panel_cargar'))

# ============================================================
#   2. PROVEEDORES 🔒
# ============================================================
@cargar_bp.route('/cargar/proveedores', methods=['POST'])
@login_required
@solo_admin
def cargar_proveedores():
    file = request.files.get('archivo')
    if not file or not allowed_file(file.filename):
        flash('Archivo inválido. Usa .xlsx', 'danger')
        return redirect(url_for('cargar.panel_cargar'))

    ruta = guardar_archivo(file)
    try:
        df = pd.read_excel(ruta)
        df.columns = [c.strip().lower() for c in df.columns]

        creados = actualizados = errores = 0
        for _, row in df.iterrows():
            try:
                rif    = str(row.get('rif', '')).strip()
                nombre = str(row.get('nombre', '')).strip()
                if not rif or not nombre or rif == 'nan':
                    continue

                prov = Proveedor.query.filter_by(rif=rif).first()
                if prov:
                    prov.nombre            = nombre
                    prov.telefono          = str(row.get('telefono', '') or '').strip()
                    prov.direccion         = str(row.get('direccion', '') or '').strip()
                    prov.vendedor_nombre   = str(row.get('vendedor_nombre', '') or '').strip()
                    prov.vendedor_telefono = str(row.get('vendedor_telefono', '') or '').strip()
                    actualizados += 1
                else:
                    prov = Proveedor(
                        rif                  = rif,
                        nombre               = nombre,
                        telefono             = str(row.get('telefono', '') or '').strip(),
                        direccion            = str(row.get('direccion', '') or '').strip(),
                        vendedor_nombre      = str(row.get('vendedor_nombre', '') or '').strip(),
                        vendedor_telefono    = str(row.get('vendedor_telefono', '') or '').strip(),
                        saldo_pendiente_usd  = seguro_decimal(row.get('saldo_pendiente_usd')),
                    )
                    db.session.add(prov)
                    creados += 1
            except Exception:
                errores += 1

        db.session.commit()
        flash(f'✅ Proveedores: {creados} creados, {actualizados} actualizados, {errores} errores.', 'success')
    except Exception as e:
        flash(f'❌ Error procesando archivo: {str(e)}', 'danger')

    return redirect(url_for('cargar.panel_cargar'))

# ============================================================
#   3. INVENTARIO (PRODUCTOS) 🔒
# ============================================================
@cargar_bp.route('/cargar/inventario', methods=['POST'])
@login_required
@solo_admin
def cargar_inventario():
    file = request.files.get('archivo')
    if not file or not allowed_file(file.filename):
        flash('Archivo inválido. Usa .xlsx', 'danger')
        return redirect(url_for('cargar.panel_cargar'))

    ruta = guardar_archivo(file)
    try:
        df = pd.read_excel(ruta)
        df.columns = [c.strip().lower() for c in df.columns]

        creados = actualizados = errores = 0
        for _, row in df.iterrows():
            try:
                codigo = str(row.get('codigo', '')).strip()
                nombre = str(row.get('nombre', '')).strip()
                if not codigo or not nombre or codigo == 'nan':
                    continue

                prod = Producto.query.filter_by(codigo=codigo).first()
                if prod:
                    prod.nombre             = nombre
                    prod.categoria          = str(row.get('categoria', '') or '').strip()
                    prod.costo_usd          = seguro_decimal(row.get('costo_usd'))
                    prod.precio_normal_usd  = seguro_decimal(row.get('precio_normal_usd'))
                    prod.precio_oferta_usd  = seguro_decimal(row.get('precio_oferta_usd'))
                    antes_stock = prod.stock
                    prod.stock              = seguro_decimal(row.get('stock'))
                    prod.stock_minimo       = int(row.get('stock_minimo', 5) or 5)
                    actualizados += 1

                    # 📜 AUDITORIA
                    db.session.add(AuditoriaInventario(
                        usuario_id=current_user.id,
                        usuario_nombre=current_user.username,
                        producto_id=prod.id,
                        producto_nombre=prod.nombre,
                        accion='CARGA_EXCEL_STOCK_UPDATE',
                        cantidad_antes=antes_stock,
                        cantidad_despues=prod.stock,
                        fecha=datetime.now()
                    ))
                else:
                    prod = Producto(
                        codigo            = codigo,
                        nombre            = nombre,
                        categoria         = str(row.get('categoria', '') or '').strip(),
                        costo_usd         = seguro_decimal(row.get('costo_usd')),
                        precio_normal_usd = seguro_decimal(row.get('precio_normal_usd')),
                        precio_oferta_usd = seguro_decimal(row.get('precio_oferta_usd')),
                        stock             = seguro_decimal(row.get('stock')),
                        stock_minimo      = int(row.get('stock_minimo', 5) or 5),
                    )
                    db.session.add(prod)
                    db.session.flush()

                    # 📜 AUDITORIA
                    db.session.add(AuditoriaInventario(
                        usuario_id=current_user.id,
                        usuario_nombre=current_user.username,
                        producto_id=prod.id,
                        producto_nombre=prod.nombre,
                        accion='CARGA_EXCEL_NUEVO_PRODUCTO',
                        cantidad_antes=0,
                        cantidad_despues=prod.stock,
                        fecha=datetime.now()
                    ))
                    creados += 1
            except Exception:
                errores += 1

        db.session.commit()
        flash(f'✅ Inventario: {creados} creados, {actualizados} actualizados, {errores} errores.', 'success')
    except Exception as e:
        flash(f'❌ Error procesando archivo: {str(e)}', 'danger')

    return redirect(url_for('cargar.panel_cargar'))

# ============================================================
#   4. COMPRAS HISTÓRICAS 🔒
# ============================================================
@cargar_bp.route('/cargar/compras', methods=['POST'])
@login_required
@solo_admin
def cargar_compras():
    file = request.files.get('archivo')
    if not file or not allowed_file(file.filename):
        flash('Archivo inválido. Usa .xlsx', 'danger')
        return redirect(url_for('cargar.panel_cargar'))

    ruta = guardar_archivo(file)
    try:
        df = pd.read_excel(ruta)
        df.columns = [c.strip().lower() for c in df.columns]

        creados = errores = 0
        for _, row in df.iterrows():
            try:
                rif_prov = str(row.get('rif_proveedor', '')).strip()
                nro_fac  = str(row.get('numero_factura', '')).strip()
                if not rif_prov or rif_prov == 'nan':
                    continue

                prov = Proveedor.query.filter_by(rif=rif_prov).first()
                if not prov:
                    errores += 1
                    continue

                if nro_fac and Compra.query.filter_by(numero_factura=nro_fac).first():
                    continue

                fecha = datetime.utcnow()
                if pd.notna(row.get('fecha')):
                    try:
                        fecha = pd.to_datetime(row['fecha'])
                    except:
                        pass

                compra = Compra(
                    proveedor_id   = prov.id,
                    numero_factura = nro_fac,
                    total_usd      = seguro_decimal(row.get('total_usd')),
                    estado         = str(row.get('estado', 'Pendiente') or 'Pendiente').strip(),
                    metodo_pago    = str(row.get('metodo_pago', 'Credito') or 'Credito').strip(),
                    fecha          = fecha,
                )
                db.session.add(compra)
                db.session.flush()

                cod_prod = str(row.get('codigo_producto', '')).strip()
                if cod_prod and cod_prod != 'nan':
                    prod = Producto.query.filter_by(codigo=cod_prod).first()
                    if prod:
                        cantidad = Decimal(str(row.get('cantidad', 1) or 1))
                        costo    = Decimal(str(row.get('costo_unitario', 0) or 0))
                        detalle  = CompraDetalle(
                            compra_id      = compra.id,
                            producto_id    = prod.id,
                            cantidad       = cantidad,
                            costo_unitario = costo,
                        )
                        db.session.add(detalle)
                        antes_compra = prod.stock
                        prod.stock += cantidad

                        # 📜 AUDITORIA
                        db.session.add(AuditoriaInventario(
                            usuario_id=current_user.id,
                            usuario_nombre=current_user.username,
                            producto_id=prod.id,
                            producto_nombre=prod.nombre,
                            accion='CARGA_EXCEL_COMPRA_HISTORICA',
                            cantidad_antes=antes_compra,
                            cantidad_despues=prod.stock,
                            fecha=datetime.now()
                        ))

                creados += 1
            except Exception:
                errores += 1

        db.session.commit()
        flash(f'✅ Compras: {creados} creadas, {errores} errores.', 'success')
    except Exception as e:
        flash(f'❌ Error procesando archivo: {str(e)}', 'danger')

    return redirect(url_for('cargar.panel_cargar'))

# ============================================================
#   5. VENTAS HISTÓRICAS 🔒
# ============================================================
@cargar_bp.route('/cargar/ventas', methods=['POST'])
@login_required
@solo_admin
def cargar_ventas():
    file = request.files.get('archivo')
    if not file or not allowed_file(file.filename):
        flash('Archivo inválido. Usa .xlsx', 'danger')
        return redirect(url_for('cargar.panel_cargar'))

    ruta = gu

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from functools import wraps
from models import db, Producto
from decimal import Decimal
from datetime import datetime
from utils import seguro_decimal
import logging

inventario_bp = Blueprint('inventario', __name__)
logger = logging.getLogger('KALU.inventario')

CATEGORIAS = [
    "VÍVERES",
    "REPUESTOS DE MOTO",
    "CARNICERÍA",
    "PRODUCTORES / AGRÍCOLA",
    "FERRETERÍA",
    "GENÉRICOS"
]

# ============================================================
# 🔒 DECORADOR DE SEGURIDAD
# ============================================================
def solo_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("⚠️ Debes iniciar sesión primero.", "warning")
            return redirect(url_for('auth.ingresar'))
        if current_user.role not in ['admin', 'supervisor', 'dueno']:
            flash("🚫 No tienes permiso para acceder al inventario.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# 📋 AUDITORÍA
# ============================================================
def registrar_auditoria(accion, producto, cantidad_antes=None, cantidad_despues=None):
    from models import AuditoriaInventario
    log = AuditoriaInventario(
        usuario_id=current_user.id,
        usuario_nombre=current_user.username,
        producto_id=producto.id,
        producto_nombre=producto.nombre,
        accion=accion,
        cantidad_antes=cantidad_antes,
        cantidad_despues=cantidad_despues,
        fecha=datetime.utcnow()
    )
    db.session.add(log)

# ============================================================
# 📦 VER INVENTARIO
# ============================================================
@inventario_bp.route('/inventario')
@login_required
@solo_admin
def lista_inventario():
    prods = Producto.query.order_by(Producto.categoria, Producto.nombre).all()
    return render_template('inventario.html', productos=prods, categorias=CATEGORIAS)

# ============================================================
# ➕ AGREGAR PRODUCTO
# ============================================================
@inventario_bp.route('/agregar_producto', methods=['POST'])
@login_required
@solo_admin
def agregar_producto():
    try:
        codigo = request.form.get('codigo', '').strip()
        nombre = request.form.get('nombre', '').strip().upper()

        existe_codigo = Producto.query.filter_by(codigo=codigo).first()
        if existe_codigo:
            flash(f"⚠️ El código [{codigo}] ya lo tiene: {existe_codigo.nombre}", "danger")
            return redirect(url_for('inventario.lista_inventario'))

        existe_nombre = Producto.query.filter_by(nombre=nombre).first()
        if existe_nombre:
            flash(f"⚠️ Ya existe un producto llamado [{nombre}] con código: {existe_nombre.codigo}", "danger")
            return redirect(url_for('inventario.lista_inventario'))

        nuevo = Producto(
            codigo=codigo,
            nombre=nombre,
            categoria=request.form.get('categoria'),
            costo_usd=seguro_decimal(request.form.get('costo_usd', '0')),
            precio_normal_usd=seguro_decimal(request.form.get('precio_normal_usd', '0')),
            precio_oferta_usd=seguro_decimal(request.form.get('precio_oferta_usd', '0')),
            stock=seguro_decimal(request.form.get('stock', '0')),
            stock_minimo=seguro_decimal(request.form.get('stock_minimo', '5'))
        )

        if nuevo.stock < 0:
            flash("❌ El stock no puede ser negativo.", "danger")
            return redirect(url_for('inventario.lista_inventario'))

        if nuevo.precio_normal_usd < 0 or nuevo.costo_usd < 0:
            flash("❌ Los precios no pueden ser negativos.", "danger")
            return redirect(url_for('inventario.lista_inventario'))

        db.session.add(nuevo)
        db.session.flush()
        registrar_auditoria('AGREGAR PRODUCTO', nuevo, 0, nuevo.stock)
        db.session.commit()
        logger.info(f"PRODUCTO AGREGADO: {nuevo.nombre} (ID: {nuevo.id}) | Stock Inicial: {nuevo.stock} | Por: {current_user.username}")
        flash(f"✅ Producto '{nuevo.nombre}' agregado por {current_user.username}", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")

    return redirect(url_for('inventario.lista_inventario'))

# ============================================================
# ✏️ EDITAR PRODUCTO
# ============================================================
@inventario_bp.route('/editar_producto/<int:id>', methods=['GET', 'POST'])
@login_required
@solo_admin
def editar_producto(id):
    prod = Producto.query.get_or_404(id)

    if request.method == 'POST':
        stock_antes = prod.stock
        prod.codigo = request.form.get('codigo')
        prod.nombre = request.form.get('nombre')
        prod.categoria = request.form.get('categoria')
        prod.costo_usd = seguro_decimal(request.form.get('costo_usd', '0'))
        prod.precio_normal_usd = seguro_decimal(request.form.get('precio_normal_usd', '0'))
        prod.precio_oferta_usd = seguro_decimal(request.form.get('precio_oferta_usd', '0'))
        prod.stock = seguro_decimal(request.form.get('stock', '0'))
        prod.stock_minimo = seguro_decimal(request.form.get('stock_minimo', '5'))

        if prod.stock < 0:
            flash("❌ El stock no puede ser negativo.", "danger")
            return redirect(url_for('inventario.lista_inventario'))

        registrar_auditoria('EDITAR PRODUCTO', prod, stock_antes, prod.stock)
        db.session.commit()
        logger.info(f"PRODUCTO EDITADO: {prod.nombre} (ID: {prod.id}) | Stock: {stock_antes} -> {prod.stock} | Por: {current_user.username}")
        flash(f"✅ Producto '{prod.nombre}' actualizado por {current_user.username}", "success")
        return redirect(url_for('inventario.lista_inventario') + f'#prod-{id}')

    return render_template('editar_producto.html', p=prod, categorias=CATEGORIAS)

# ============================================================
# 🗑️ ELIMINAR PRODUCTO
# ============================================================
@inventario_bp.route('/eliminar_producto/<int:id>')
@login_required
@solo_admin
def eliminar_producto(id):
    try:
        prod = Producto.query.get_or_404(id)
        registrar_auditoria('ELIMINAR PRODUCTO', prod, prod.stock, 0)
        db.session.delete(prod)
        db.session.commit()
        logger.warning(f"PRODUCTO ELIMINADO: {prod.nombre} (ID: {prod.id}) | Stock Final: {prod.stock} | Por: {current_user.username}")
        flash(f"✅ Producto '{prod.nombre}' eliminado por {current_user.username}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al eliminar: {str(e)}", "danger")
    return redirect(url_for('inventario.lista_inventario'))

# ============================================================
# 📊 VER AUDITORÍA
# ============================================================
@inventario_bp.route('/auditoria_inventario')
@login_required
@solo_admin
def ver_auditoria():
    from models import AuditoriaInventario
    logs = AuditoriaInventario.query.order_by(
        AuditoriaInventario.fecha.desc()
    ).limit(200).all()
    return render_template('auditoria_inventario.html', logs=logs)

# ============================================================
# 💰 REPORTE DE INVERSIÓN
# ============================================================
@inventario_bp.route('/reporte_inventario')
@login_required
@solo_admin
def reporte_inventario():
    from models import TasaBCV
    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = tasa_obj.valor if tasa_obj else Decimal('1.00')

    productos = Producto.query.order_by(Producto.categoria).all()

    data = []
    for p in productos:
        costo     = p.costo_usd or Decimal('0.00')
        precio    = p.precio_normal_usd or Decimal('0.00')
        stock     = p.stock or Decimal('0.000')
        invertido = costo * stock
        valor_venta = precio * stock
        ganancia    = valor_venta - invertido

        data.append({
            'id':           p.id,
            'codigo':       p.codigo,
            'nombre':       p.nombre,
            'categoria':    p.categoria,
            'stock':        stock,
            'stock_minimo': p.stock_minimo,
            'costo_usd':    costo,
            'precio_usd':   precio,
            'invertido_usd':  invertido,
            'valor_venta_usd': valor_venta,
            'ganancia_usd':   ganancia,
            'invertido_bs':   invertido * tasa,
            'valor_venta_bs': valor_venta * tasa,
            'bajo_minimo':  stock <= (p.stock_minimo or Decimal('0.000'))
        })

    totales = {
        'total_invertido_usd':  sum(d['invertido_usd']  for d in data),
        'total_venta_usd':      sum(d['valor_venta_usd'] for d in data),
        'total_ganancia_usd':   sum(d['ganancia_usd']   for d in data),
        'total_invertido_bs':   sum(d['invertido_bs']   for d in data),
        'total_venta_bs':       sum(d['valor_venta_bs'] for d in data),
        'total_productos':      len(data),
        'bajo_minimo':          sum(1 for d in data if d['bajo_minimo'])
    }

    categorias_resumen = {}
    for d in data:
        cat = d['categoria'] or 'SIN CATEGORÍA'
        if cat not in categorias_resumen:
            categorias_resumen[cat] = {
                'invertido_usd': 0, 'valor_venta_usd': 0,
                'ganancia_usd': 0, 'cantidad_productos': 0
            }
        categorias_resumen[cat]['invertido_usd']   += d['invertido_usd']
        categorias_resumen[cat]['valor_venta_usd'] += d['valor_venta_usd']
        categorias_resumen[cat]['ganancia_usd']    += d['ganancia_usd']
        categorias_resumen[cat]['cantidad_productos'] += 1

    return render_template('reporte_inventario.html',
                           data=data,
                           totales=totales,
                           categorias_resumen=categorias_resumen,
                           tasa=tasa,  # Mantener como Decimal
                           categorias=CATEGORIAS,
                           categoria_filtro='TODAS',
                           fecha=datetime.now())

# ============================================================
# 🖨️ IMPRIMIR INVENTARIO
# ============================================================
@inventario_bp.route('/imprimir_inventario')
@login_required
@solo_admin
def imprimir_inventario():
    from models import TasaBCV
    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = tasa_obj.valor if tasa_obj else Decimal('1.00')

    categoria_filtro = request.args.get('categoria', 'TODAS')
    productos = Producto.query.order_by(Producto.categoria, Producto.nombre).all()

    if categoria_filtro != 'TODAS':
        productos = [p for p in productos if p.categoria == categoria_filtro]

    data = []
    for p in productos:
        costo   = p.costo_usd or Decimal('0.00')
        precio  = p.precio_normal_usd or Decimal('0.00')
        stock   = p.stock or Decimal('0.000')
        invertido   = costo * stock
        valor_venta = precio * stock
        ganancia    = valor_venta - invertido
        
        data.append({
            'codigo':       p.codigo,
            'nombre':       p.nombre,
            'categoria':    p.categoria,
            'stock':        stock,
            'costo_usd':    costo,
            'precio_usd':   precio,
            'invertido_usd': invertido,
            'valor_venta_usd': valor_venta,
            'ganancia_usd':   ganancia,
            'bajo_minimo':  stock <= (p.stock_minimo or Decimal('0.000'))
        })

    totales = {
        'total_invertido_usd': sum(d['invertido_usd']    for d in data),
        'total_venta_usd':     sum(d['valor_venta_usd']  for d in data),
        'total_productos':     len(data)
    }

    return render_template('imprimir_inventario.html',
                           data=data,
                           totales=totales,
                           tasa=tasa,
                           categoria_filtro=categoria_filtro,
                           categorias=CATEGORIAS,
                           fecha=datetime.now())
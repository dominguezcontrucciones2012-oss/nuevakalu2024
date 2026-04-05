from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user  # 👈 NUEVO
from functools import wraps                            # 👈 NUEVO
from models import db, CuentaContable, Asiento, DetalleAsiento, TasaBCV
from datetime import datetime
from decimal import Decimal

contabilidad_bp = Blueprint('contabilidad', __name__)

# ============================================================
# 🔒 DECORADOR DE SEGURIDAD
# ============================================================
def solo_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("⚠️ Debes iniciar sesión primero.", "warning")
            return redirect(url_for('auth.login'))
        if current_user.role not in ['admin', 'supervisor']:
            flash("🚫 No tienes permiso para acceder a contabilidad.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def sembrar_cuentas():
    cuentas_base = [
        ('1',           'ACTIVO',                       'ACTIVO'),
        ('1.1',         'ACTIVO CORRIENTE',              'ACTIVO'),
        ('1.1.01',      'CAJA Y BANCOS',                 'ACTIVO'),
        ('1.1.01.01',   'CAJA USD',                      'ACTIVO'),
        ('1.1.01.02',   'CAJA BS EFECTIVO',              'ACTIVO'),
        ('1.1.01.03',   'PAGO MÓVIL / TRANSFERENCIA',    'ACTIVO'),
        ('1.1.01.04',   'BIOPAGO BDV',                   'ACTIVO'),
        ('1.1.01.05',   'TARJETA DE DÉBITO',              'ACTIVO'),
        ('1.1.02',      'CUENTAS POR COBRAR',            'ACTIVO'),
        ('1.1.02.01',   'CLIENTES (FIADO)',               'ACTIVO'),
        ('1.1.02.02',   'PRODUCTORES (FIADO)',            'ACTIVO'),
        ('1.1.03',      'INVENTARIO',                    'ACTIVO'),
        ('1.1.03.01',   'MERCANCÍA EN EXISTENCIA',       'ACTIVO'),
        ('2',           'PASIVO',                        'PASIVO'),
        ('2.1',         'PASIVO CORRIENTE',              'PASIVO'),
        ('2.1.01',      'CUENTAS POR PAGAR',             'PASIVO'),
        ('2.1.01.01',   'PROVEEDORES',                   'PASIVO'),
        ('3',           'PATRIMONIO',                    'PATRIMONIO'),
        ('3.1',         'CAPITAL',                       'PATRIMONIO'),
        ('3.1.01',      'CAPITAL SOCIAL',                'PATRIMONIO'),
        ('4',           'INGRESOS',                      'INGRESO'),
        ('4.1',         'INGRESOS OPERACIONALES',        'INGRESO'),
        ('4.1.01',      'VENTAS CONTADO',                'INGRESO'),
        ('4.1.02',      'VENTAS FIADO',                  'INGRESO'),
        ('4.1.03',      'ABONOS RECIBIDOS',              'INGRESO'),
        ('5',           'GASTOS',                        'GASTO'),
        ('5.1',         'GASTOS OPERACIONALES',          'GASTO'),
        ('5.1.01',      'COSTO DE VENTAS',               'GASTO'),
        ('5.1.02',      'COMPRAS DE MERCANCÍA',          'GASTO'),
        ('5.1.03',      'GASTOS GENERALES',              'GASTO'),
    ]
    for codigo, nombre, tipo in cuentas_base:
        if not CuentaContable.query.filter_by(codigo=codigo).first():
            db.session.add(CuentaContable(codigo=codigo, nombre=nombre, tipo=tipo))
    db.session.commit()


def registrar_asiento(descripcion, tasa, referencia_tipo, referencia_id, movimientos, commit=True):
    try:
        asiento = Asiento(
            fecha=datetime.now().date(),
            descripcion=descripcion,
            tasa_referencia=Decimal(str(tasa)),
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id
        )
        db.session.add(asiento)
        db.session.flush()

        for mov in movimientos:
            cuenta = CuentaContable.query.filter_by(codigo=mov['cuenta_codigo']).first()
            if not cuenta:
                continue
            detalle = DetalleAsiento(
                asiento_id=asiento.id,
                cuenta_id=cuenta.id,
                debe_usd=Decimal(str(mov.get('debe_usd', 0))),
                haber_usd=Decimal(str(mov.get('haber_usd', 0))),
                debe_bs=Decimal(str(mov.get('debe_bs', 0))),
                haber_bs=Decimal(str(mov.get('haber_bs', 0))),
            )
            db.session.add(detalle)

        if commit:
            db.session.commit()
        else:
            db.session.flush()
            
        return asiento.id

    except Exception as e:
        if commit:
            db.session.rollback()
        print(f"❌ Error registrando asiento: {e}")
        raise e



# ============================================================
# 📊 DASHBOARD CONTABILIDAD 🔒
# ============================================================
@contabilidad_bp.route('/contabilidad')
@login_required
@solo_admin
def index():
    sembrar_cuentas()
    total_ventas = db.session.query(
        db.func.sum(DetalleAsiento.haber_usd)
    ).join(CuentaContable).filter(
        CuentaContable.codigo.in_(['4.1.01', '4.1.02'])
    ).scalar() or Decimal('0.00')

    total_compras = db.session.query(
        db.func.sum(DetalleAsiento.debe_usd)
    ).join(CuentaContable).filter(
        CuentaContable.codigo == '5.1.02'
    ).scalar() or Decimal('0.00')

    total_fiado = db.session.query(
        db.func.sum(DetalleAsiento.debe_usd)
    ).join(CuentaContable).filter(
        CuentaContable.codigo == '1.1.02.01'
    ).scalar() or Decimal('0.00')

    return render_template('contabilidad/index.html',
        total_ventas=total_ventas,
        total_compras=total_compras,
        total_fiado=total_fiado
    )


# ============================================================
# 📋 PLAN DE CUENTAS 🔒
# ============================================================
@contabilidad_bp.route('/contabilidad/plan-cuentas')
@login_required
@solo_admin
def plan_cuentas():
    sembrar_cuentas()
    cuentas = CuentaContable.query.order_by(CuentaContable.codigo).all()
    return render_template('contabilidad/plan_cuentas.html', cuentas=cuentas)


# ============================================================
# 📖 LIBRO DIARIO 🔒
# ============================================================
@contabilidad_bp.route('/contabilidad/libro-diario')
@login_required
@solo_admin
def libro_diario():
    asientos = Asiento.query.order_by(Asiento.fecha.desc()).all()
    return render_template('contabilidad/libro_diario.html', asientos=asientos)


# ============================================================
# ⚖️ BALANCE GENERAL 🔒
# ============================================================
@contabilidad_bp.route('/contabilidad/balance')
@login_required
@solo_admin
def balance():
    sembrar_cuentas()
    cuentas = CuentaContable.query.order_by(CuentaContable.codigo).all()
    resumen = []
    for cuenta in cuentas:
        total_debe_usd  = sum(d.debe_usd  for d in cuenta.movimientos) or Decimal('0.00')
        total_haber_usd = sum(d.haber_usd for d in cuenta.movimientos) or Decimal('0.00')

        # ✅ CORRECCIÓN: cada tipo de cuenta tiene su propia fórmula
        if cuenta.tipo in ['ACTIVO', 'GASTO']:
            saldo = total_debe_usd - total_haber_usd
        else:  # PASIVO, PATRIMONIO, INGRESO
            saldo = total_haber_usd - total_debe_usd

        if saldo != 0:
            resumen.append({
                'codigo': cuenta.codigo,
                'nombre': cuenta.nombre,
                'tipo':   cuenta.tipo,
                'debe':   total_debe_usd,
                'haber':  total_haber_usd,
                'saldo':  saldo
            })
    return render_template('contabilidad/balance.html', resumen=resumen)
# ============================================================
# 🔍 VER ASIENTO INDIVIDUAL 🔒
# ============================================================
@contabilidad_bp.route('/contabilidad/asiento/<int:id>')
@login_required
@solo_admin
def ver_asiento(id):
    asiento = Asiento.query.get_or_404(id)
    return render_template('contabilidad/ver_asiento.html', asiento=asiento)


# ============================================================
# 💸 REGISTRAR GASTO OPERATIVO 🔒
# ============================================================
@contabilidad_bp.route('/contabilidad/registrar_gasto_operativo', methods=['POST'])
@login_required
@solo_admin
def registrar_gasto_operativo():
    descripcion   = request.form.get('descripcion', '').strip()
    monto_usd     = Decimal(str(request.form.get('monto_usd', 0)))
    cuenta_origen = request.form.get('cuenta_origen')

    if not descripcion or monto_usd <= 0:
        flash('⚠️ Descripción y monto válido son obligatorios.', 'warning')
        return redirect(url_for('contabilidad.balance'))

    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')

    registrar_asiento(
        descripcion=f"GASTO: {descripcion}",
        tasa=float(tasa),
        referencia_tipo='GASTO',
        referencia_id=0,
        movimientos=[
            {'cuenta_codigo': '5.1.03',      'debe_usd': monto_usd, 'haber_usd': 0,
             'debe_bs': monto_usd * tasa,     'haber_bs': 0},
            {'cuenta_codigo': cuenta_origen,  'debe_usd': 0, 'haber_usd': monto_usd,
             'debe_bs': 0, 'haber_bs': monto_usd * tasa},
        ]
    )

    flash(f'✅ Gasto "{descripcion}" de ${monto_usd:.2f} registrado.', 'success')
    return redirect(url_for('contabilidad.balance'))


# ============================================================
# 🔌 API ASIENTOS — Libre (solo lectura para reportes internos)
# ============================================================
@contabilidad_bp.route('/contabilidad/api/asientos')
def api_asientos():
    tipo  = request.args.get('tipo')
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    query = Asiento.query
    if tipo:
        query = query.filter_by(referencia_tipo=tipo)
    if desde:
        query = query.filter(Asiento.fecha >= desde)
    if hasta:
        query = query.filter(Asiento.fecha <= hasta)
    asientos = query.order_by(Asiento.fecha.desc()).all()
    return jsonify([{
        'id':           a.id,
        'fecha':        str(a.fecha),
        'descripcion':  a.descripcion,
        'tipo':         a.referencia_tipo,
        'referencia_id': a.referencia_id
    } for a in asientos])

# ============================================================
# 🔄 DEVOLUCIÓN DE PRODUCTO 🔒
# ============================================================
@contabilidad_bp.route('/contabilidad/devolucion', methods=['POST'])
@login_required
@solo_admin
def registrar_devolucion():
    venta_id        = request.form.get('venta_id')
    producto_id     = request.form.get('producto_id')
    cantidad        = Decimal(request.form.get('cantidad', 0))
    monto_reembolso = Decimal(request.form.get('monto_reembolso', 0))
    motivo          = request.form.get('motivo', 'Devolución de mercancía')

    if cantidad <= 0 or monto_reembolso < 0:
        flash('⚠️ Cantidad o monto no válidos.', 'warning')
        return redirect(url_for('contabilidad.balance'))

    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')

    registrar_asiento(
        descripcion=f"DEVOLUCIÓN: {motivo} (Venta #{venta_id})",
        tasa=float(tasa),
        referencia_tipo='DEVOLUCION',
        referencia_id=venta_id,
        movimientos=[
            {'cuenta_codigo': '4.1.01', 'debe_usd': monto_reembolso, 'haber_usd': 0,
             'debe_bs': monto_reembolso * tasa, 'haber_bs': 0},
            {'cuenta_codigo': '1.1.01.02', 'debe_usd': 0, 'haber_usd': monto_reembolso,
             'debe_bs': 0, 'haber_bs': monto_reembolso * tasa},
        ]
    )

    # ✅ DEVOLVER EL STOCK AL INVENTARIO
    from models import Producto
    producto = Producto.query.get(producto_id)
    if producto and cantidad > 0:
        producto.stock += cantidad
        db.session.commit()

    flash(f'✅ Devolución de ${monto_reembolso:.2f} procesada y stock actualizado.', 'success')
    return redirect(url_for('contabilidad.balance'))
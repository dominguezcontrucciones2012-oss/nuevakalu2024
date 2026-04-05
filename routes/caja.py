from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, MovimientoCaja, TasaBCV, Venta
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import func

caja_bp = Blueprint('caja', __name__, url_prefix='/caja')

# ============================================================
# HELPER: OBTENER SALDO DE UNA CAJA
# ============================================================
def get_saldo_caja(tipo_caja):
    ingresos = db.session.query(
        func.sum(MovimientoCaja.monto)
    ).filter(
        MovimientoCaja.tipo_caja == tipo_caja,
        MovimientoCaja.tipo_movimiento == 'INGRESO'
    ).scalar() or Decimal('0.00')

    egresos = db.session.query(
        func.sum(MovimientoCaja.monto)
    ).filter(
        MovimientoCaja.tipo_caja == tipo_caja,
        MovimientoCaja.tipo_movimiento == 'EGRESO'
    ).scalar() or Decimal('0.00')

    return Decimal(str(ingresos)) - Decimal(str(egresos))


# ============================================================
# HELPER: SALDO BANCO DESGLOSADO POR MÉTODO
# ============================================================
def get_saldo_banco_desglosado():
    metodos = ['Pago Móvil', 'Biopago', 'Tarjeta Débito']
    resultado = {}
    for metodo in metodos:
        ingresos = db.session.query(
            func.sum(MovimientoCaja.monto)
        ).filter(
            MovimientoCaja.tipo_caja == 'Banco',
            MovimientoCaja.tipo_movimiento == 'INGRESO',
            MovimientoCaja.descripcion.ilike(f'%{metodo}%')
        ).scalar() or Decimal('0.00')

        egresos = db.session.query(
            func.sum(MovimientoCaja.monto)
        ).filter(
            MovimientoCaja.tipo_caja == 'Banco',
            MovimientoCaja.tipo_movimiento == 'EGRESO',
            MovimientoCaja.descripcion.ilike(f'%{metodo}%')
        ).scalar() or Decimal('0.00')

        resultado[metodo] = Decimal(str(ingresos)) - Decimal(str(egresos))
    return resultado


# ============================================================
# TABLERO PRINCIPAL DE CAJA (LO QUE VE LA JEFA)
# ============================================================
@caja_bp.route('/')
@caja_bp.route('/saldo')
@login_required
def saldo_caja():
    tasa_obj = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
    tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.00')

    saldo_usd = get_saldo_caja('Caja USD')
    saldo_bs  = get_saldo_caja('Caja Bs')
    saldo_banco = get_saldo_caja('Banco')
    banco_desglosado = get_saldo_banco_desglosado()

    # Total disponible en USD (para pagar facturas)
    total_usd = saldo_usd + (saldo_bs / tasa) + (saldo_banco / tasa)

    # Últimos 30 movimientos
    movimientos = MovimientoCaja.query.order_by(
        MovimientoCaja.fecha.desc()
    ).limit(30).all()

    return render_template('caja/saldo.html',
        saldo_usd        = saldo_usd,
        saldo_bs         = saldo_bs,
        saldo_banco      = saldo_banco,
        banco_desglosado = banco_desglosado,
        total_usd        = total_usd,
        tasa             = tasa,
        movimientos      = movimientos
    )


# ============================================================
# REGISTRAR GASTO / EGRESO MANUAL
# ============================================================
@caja_bp.route('/registrar_gasto', methods=['GET', 'POST'])
@login_required
def registrar_gasto():
    if current_user.role == 'cajero':
        flash('⛔ No tienes permiso para registrar gastos.', 'danger')
        return redirect(url_for('caja.saldo_caja'))
    if request.method == 'POST':
        categoria = request.form.get('categoria')
        monto     = Decimal(request.form.get('monto', '0').replace(',', '.'))
        tipo_caja = request.form.get('tipo_caja')
        concepto  = request.form.get('concepto', '')

        # Verificar que hay saldo suficiente
        saldo_actual = get_saldo_caja(tipo_caja)
        if monto > saldo_actual:
            flash(f'⚠️ Saldo insuficiente en {tipo_caja}. Disponible: {saldo_actual:.2f}', 'warning')
            return redirect(url_for('caja.registrar_gasto'))

        hoy = datetime.now().date()
        tasa = TasaBCV.query.filter_by(fecha=hoy).first()
        tasa_valor = Decimal(str(tasa.valor)) if tasa else Decimal('1.00')

        nuevo_egreso = MovimientoCaja(
            fecha           = datetime.now(),
            tipo_movimiento = 'EGRESO',
            tipo_caja       = tipo_caja,
            categoria       = categoria,
            monto           = monto,
            tasa_dia        = tasa_valor,
            descripcion     = concepto,
            modulo_origen   = 'Gasto Manual',
            user_id         = current_user.id
        )

        db.session.add(nuevo_egreso)
        db.session.commit()
        flash(f'✅ Egreso de {monto:.2f} registrado en {tipo_caja}.', 'success')
        return redirect(url_for('caja.saldo_caja'))

    # Saldos actuales para mostrar en el formulario
    saldos = {
        'Caja USD': get_saldo_caja('Caja USD'),
        'Caja Bs':  get_saldo_caja('Caja Bs'),
        'Banco':    get_saldo_caja('Banco'),
    }

    movimientos = MovimientoCaja.query.order_by(
        MovimientoCaja.fecha.desc()
    ).limit(20).all()

    return render_template('caja/registrar_gasto.html',
        saldos      = saldos,
        movimientos = movimientos
    )


# ============================================================
# REGISTRAR INGRESO MANUAL (Depósito, Fondo de Caja, etc.)
# ============================================================
@caja_bp.route('/registrar_ingreso', methods=['POST'])
@login_required
def registrar_ingreso():
    if current_user.role == 'cajero':
        flash('⛔ No tienes permiso para registrar ingresos.', 'danger')
        return redirect(url_for('caja.saldo_caja'))
    tipo_caja = request.form.get('tipo_caja')
    monto     = Decimal(request.form.get('monto', '0').replace(',', '.'))
    concepto  = request.form.get('concepto', 'Ingreso Manual')

    hoy = datetime.now().date()
    tasa = TasaBCV.query.filter_by(fecha=hoy).first()
    tasa_valor = Decimal(str(tasa.valor)) if tasa else Decimal('1.00')

    nuevo_ingreso = MovimientoCaja(
        fecha           = datetime.now(),
        tipo_movimiento = 'INGRESO',
        tipo_caja       = tipo_caja,
        categoria       = 'Ingreso Manual',
        monto           = monto,
        tasa_dia        = tasa_valor,
        descripcion     = concepto,
        modulo_origen   = 'Manual',
        user_id         = current_user.id
    )

    db.session.add(nuevo_ingreso)
    db.session.commit()
    flash(f'✅ Ingreso de {monto:.2f} registrado en {tipo_caja}.', 'success')
    return redirect(url_for('caja.saldo_caja'))


# ============================================================
# API: SALDO EN TIEMPO REAL (para el dashboard)
# ============================================================
@caja_bp.route('/api/saldos')
@login_required
def api_saldos():
    tasa_obj = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
    tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.00')

    saldo_usd   = get_saldo_caja('Caja USD')
    saldo_bs    = get_saldo_caja('Caja Bs')
    saldo_banco = get_saldo_caja('Banco')
    total_usd   = saldo_usd + (saldo_bs / tasa) + (saldo_banco / tasa)

    return jsonify({
        'caja_usd':   float(saldo_usd),
        'caja_bs':    float(saldo_bs),
        'banco':      float(saldo_banco),
        'total_usd':  float(total_usd),
        'tasa':       float(tasa)
    })
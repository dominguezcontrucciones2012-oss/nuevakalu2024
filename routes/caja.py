from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from routes.decorators import staff_required
from models import db, MovimientoCaja, TasaBCV, Venta, Proveedor, MovimientoProductor
import logging
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import func
from utils import seguro_decimal

caja_bp = Blueprint('caja', __name__, url_prefix='/caja')
logger = logging.getLogger('KALU.caja')

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

    return ingresos - egresos


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

        resultado[metodo] = ingresos - egresos
    return resultado


# ============================================================
# TABLERO PRINCIPAL DE CAJA (LO QUE VE LA JEFA)
# ============================================================
@caja_bp.route('/')
@caja_bp.route('/saldo')
@login_required
@staff_required
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
@staff_required
def registrar_gasto():
    if current_user.role == 'cajero':
        flash('⛔ No tienes permiso para registrar gastos.', 'danger')
        return redirect(url_for('caja.saldo_caja'))
    if request.method == 'POST':
        categoria = request.form.get('categoria')
        monto     = seguro_decimal(request.form.get('monto', '0'))
        tipo_caja = request.form.get('tipo_caja')
        concepto  = request.form.get('concepto', '')
        obrero_id = request.form.get('obrero_id')
        moneda_input = request.form.get('moneda_input', 'USD')
        
        # Nuevo: Monto que realmente se entrega en efectivo/banco (Opcional para Nómina)
        monto_pago_efectivo = request.form.get('monto_pago_efectivo')
        
        # Obtener tasa para conversiones
        hoy = datetime.now().date()
        from models import TasaBCV
        tasa = TasaBCV.query.filter_by(fecha=hoy).order_by(TasaBCV.id.desc()).first()
        if not tasa:
             tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
        tasa_valor = tasa.valor if tasa else Decimal('40.00')

        # NORMALIZACIÓN DE MONTOS
        if moneda_input == 'USD':
            monto_en_usd = monto
            monto_en_bs  = monto * tasa_valor
        else:
            monto_en_bs  = monto
            monto_en_usd = (monto / tasa_valor).quantize(Decimal('0.01'))

        # Definir cuánto se resta de la caja física (según el origen)
        monto_para_caja = monto_en_usd if tipo_caja == 'Caja USD' else monto_en_bs

        # 👷 LÓGICA ESPECIAL PARA PAGO DE OBREROS (Siempre en USD para la libreta)
        if categoria == 'Nomina' and obrero_id:
            obrero = Proveedor.query.get(obrero_id)
            if obrero:
                # 1. Registrar lo que ganó el obrero (Haber en su libreta - SIEMPRE USD)
                saldo_antes = obrero.saldo_pendiente_usd or Decimal('0.00')
                nuevo_saldo = saldo_antes + monto_en_usd # El sueldo ganado se procesa en USD
                
                # 2. Calcular cuánto se le paga "neto" (Dinero físico que sale de caja)
                payout_neto_usd = Decimal('0.00')
                if monto_pago_efectivo is not None and str(monto_pago_efectivo).strip() != '':
                    payout_solicitado = seguro_decimal(monto_pago_efectivo)
                    # Si el usuario ingresó un monto, lo convertimos a USD para la libreta
                    # Nota: El monto_pago_efectivo viene en la moneda del gasto (moneda_input)
                    if moneda_input == 'USD':
                        payout_neto_usd = payout_solicitado
                    else:
                        payout_neto_usd = (payout_solicitado / tasa_valor).quantize(Decimal('0.01'))
                    
                    # No podemos pagar más de lo que tiene acumulado a favor
                    payout_neto_usd = min(max(Decimal('0.00'), nuevo_saldo), payout_neto_usd)
                
                # RECALCULAR monto_para_caja: Es lo que REALMENTE sale de la caja física hoy
                if moneda_input == 'USD':
                    monto_para_caja = payout_neto_usd
                else:
                    monto_para_caja = (payout_neto_usd * tasa_valor).quantize(Decimal('0.01'))

                # 3. Registrar movimientos en la libreta digital (SIEMPRE USD)
                # Entrada de sueldo bruto
                db.session.add(MovimientoProductor(
                    proveedor_id = obrero.id,
                    tipo = 'NOMINA',
                    descripcion = f"Sueldo Bruto: {concepto} ({moneda_input} {monto})",
                    haber = monto_en_usd,
                    debe = 0,
                    saldo_momento = nuevo_saldo,
                    fecha = datetime.now()
                ))
                
                # Descuento por pago neto (si aplica)
                if payout_neto_usd > 0:
                    desc_pago = f"Pago Neto en {tipo_caja}"
                    if payout_neto_usd < monto_en_usd:
                        deuda_cobrada = monto_en_usd - payout_neto_usd
                        desc_pago += f" (Cobro Deuda: ${deuda_cobrada:.2f})"
                    
                    db.session.add(MovimientoProductor(
                        proveedor_id = obrero.id,
                        tipo = 'PAGO',
                        descripcion = desc_pago,
                        haber = 0,
                        debe = payout_neto_usd,
                        saldo_momento = nuevo_saldo - payout_neto_usd,
                        fecha = datetime.now()
                    ))
                
                # Actualizar el saldo del obrero
                obrero.saldo_pendiente_usd = nuevo_saldo - payout_neto_usd

                # 4. Sincronización con CXP (FIFO) si se está pagando algo
                if payout_neto_usd > 0:
                    from models import CuentaPorPagar, AbonoCuentaPorPagar
                    monto_a_aplicar = payout_neto_usd
                    referencia_nomina = f"Pago Nómina: {concepto}"
                    
                    # Buscar facturas de crédito pendientes de este obrero/productor
                    facturas_pendientes = CuentaPorPagar.query.filter_by(
                        proveedor_id=obrero.id, 
                        estatus='Pendiente'
                    ).order_by(CuentaPorPagar.fecha.asc()).all()

                    for factura in facturas_pendientes:
                        if monto_a_aplicar <= 0: break
                        
                        abono = min(monto_a_aplicar, factura.saldo_pendiente_usd)
                        factura.saldo_pendiente_usd -= abono
                        monto_a_aplicar -= abono
                        
                        if factura.saldo_pendiente_usd <= 0:
                            factura.estatus = 'Pagado'
                        else:
                            factura.estatus = 'Parcial'
                            
                        db.session.add(AbonoCuentaPorPagar(
                            cuenta_id=factura.id,
                            monto_usd=abono,
                            metodo_pago='NOMINA',
                            descripcion=f"Saldado desde Nomina: {concepto}"
                        ))

        # Verificar saldo físico
        saldo_actual = get_saldo_caja(tipo_caja)
        if monto_para_caja > saldo_actual:
            flash(f'⚠️ Saldo insuficiente en {tipo_caja}. Disponible: {saldo_actual.quantize(Decimal("0.01"))}, Necesario: {monto_para_caja.quantize(Decimal("0.01"))}', 'warning')
            return redirect(url_for('caja.registrar_gasto'))

        # Registrar el gasto en caja física
        if monto_para_caja > 0:
            desc_egreso = concepto
            if categoria == 'Nomina' and obrero_id:
                desc_egreso = f"Nómina {obrero.nombre}: Pagado {payout_neto_usd:.2f}$ (Sueldo {monto_en_usd:.2f}$)"

            nuevo_egreso = MovimientoCaja(
                fecha           = datetime.now(),
                tipo_movimiento = 'EGRESO',
                tipo_caja       = tipo_caja,
                categoria       = categoria,
                monto           = monto_para_caja,
                tasa_dia        = tasa_valor,
                descripcion     = desc_egreso,
                modulo_origen   = 'Gasto Manual',
                user_id         = current_user.id
            )
            db.session.add(nuevo_egreso)
        
        db.session.commit()
        logger.info(f"EGRESO MANUAL: {monto_para_caja:.2f} {tipo_caja} | Por: {current_user.username}")
        flash(f'✅ Movimiento procesado. Salida: {monto_para_caja:.2f} {tipo_caja}.', 'success')
        return redirect(url_for('caja.saldo_caja'))

    # Saldos actuales para mostrar en el formulario
    saldos = {
        'Caja USD': get_saldo_caja('Caja USD'),
        'Caja Bs':  get_saldo_caja('Caja Bs'),
        'Banco':    get_saldo_caja('Banco'),
    }

    # Lista de obreros para el combo (Productores u Obreros marcados)
    from sqlalchemy import or_
    obreros = Proveedor.query.filter(or_(Proveedor.es_productor==True, Proveedor.es_obrero==True)).order_by(Proveedor.nombre).all()

    movimientos = MovimientoCaja.query.order_by(
        MovimientoCaja.fecha.desc()
    ).limit(20).all()

    return render_template('caja/registrar_gasto.html',
        saldos      = saldos,
        movimientos = movimientos,
        obreros     = obreros
    )


# ============================================================
# REGISTRAR INGRESO MANUAL (Depósito, Fondo de Caja, etc.)
# ============================================================
@caja_bp.route('/registrar_ingreso', methods=['POST'])
@login_required
@staff_required
def registrar_ingreso():
    if current_user.role == 'cajero':
        flash('⛔ No tienes permiso para registrar ingresos.', 'danger')
        return redirect(url_for('caja.saldo_caja'))
    tipo_caja = request.form.get('tipo_caja')
    monto     = seguro_decimal(request.form.get('monto', '0'))
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
    logger.info(f"INGRESO MANUAL: {monto:.2f} {tipo_caja} | Por: {current_user.username} | Concepto: {concepto}")
    flash(f'✅ Ingreso de {monto:.2f} registrado en {tipo_caja}.', 'success')
    return redirect(url_for('caja.saldo_caja'))


# ============================================================
# API: SALDO EN TIEMPO REAL (para el dashboard)
# ============================================================
@caja_bp.route('/api/saldos')
@login_required
@staff_required
def api_saldos():
    tasa_obj = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
    tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.00')

    saldo_usd   = get_saldo_caja('Caja USD')
    saldo_bs    = get_saldo_caja('Caja Bs')
    saldo_banco = get_saldo_caja('Banco')
    total_usd   = saldo_usd + (saldo_bs / tasa) + (saldo_banco / tasa)

    return jsonify({
        'caja_usd':   str(saldo_usd.quantize(Decimal('0.01'))),
        'caja_bs':    str(saldo_bs.quantize(Decimal('0.01'))),
        'banco':      str(saldo_banco.quantize(Decimal('0.01'))),
        'total_usd':  str(total_usd.quantize(Decimal('0.01'))),
        'tasa':       str(tasa.quantize(Decimal('0.01')))
    })
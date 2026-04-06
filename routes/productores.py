from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Proveedor, MovimientoProductor, Producto, CierreCaja, PagoProductor, MovimientoCaja
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from datetime import datetime
from decimal import Decimal

productores_bp = Blueprint('productores', __name__)

@productores_bp.route('/libreta_productores')
def libreta():
    productores = Proveedor.query.filter_by(es_productor=True).all()
    anio_actual = datetime.utcnow().year

    for p in productores:
        total = db.session.query(func.sum(MovimientoProductor.kilos)).filter(
            MovimientoProductor.proveedor_id == p.id,
            MovimientoProductor.tipo == 'ENTREGA_QUESO',
            MovimientoProductor.anio == anio_actual
        ).scalar()
        p.total_kilos = total or 0

    raw_ranking = db.session.query(
        Proveedor.nombre,
        func.sum(MovimientoProductor.kilos).label('total_kilos'),
        func.count(func.distinct(MovimientoProductor.semana_del_anio)).label('semanas_fiel'),
        func.sum(MovimientoProductor.monto_usd).filter(
            MovimientoProductor.tipo == 'COMPRA_POS'
        ).label('total_compras')
    ).join(MovimientoProductor).filter(
        MovimientoProductor.anio == anio_actual
    ).group_by(Proveedor.id).order_by(desc('total_kilos')).all()

    ranking = []
    for r in raw_ranking:
        kilos = float(r.total_kilos or 0)
        semanas = int(r.semanas_fiel or 0)
        compras = float(r.total_compras or 0)
        puntos = int((kilos / 10) + (semanas * 10) + (compras / 5))
        ranking.append({
            'nombre': r.nombre,
            'total_kilos': kilos,
            'semanas_fiel': semanas,
            'puntos_totales': puntos
        })

    from models import TasaBCV
    tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    valor_tasa = float(tasa.valor) if tasa else 40.0

    return render_template(
        'libreta_productores.html',
        productores=productores,
        ranking=ranking,
        anio_actual=anio_actual,
        tasa_bcv=valor_tasa
    )

@productores_bp.route('/registrar_entrega', methods=['POST'])
def registrar_entrega():
    from models import CuentaContable, Asiento, DetalleAsiento, TasaBCV

    p_id = request.form.get('proveedor_id')
    kilos = Decimal(request.form.get('kilos', '0') or '0')
    precio = Decimal(request.form.get('precio', '0') or '0')
    metodo = request.form.get('metodo_pago')

    _monto_raw = (request.form.get('monto_pagado') or '0').strip()
    if not _monto_raw: _monto_raw = '0'
    monto_pagado = Decimal(_monto_raw) if metodo != 'CREDITO' else Decimal('0')

    total_queso = kilos * precio
    productor = Proveedor.query.get(p_id)
    tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    valor_tasa = tasa.valor if tasa else Decimal('1.00')

    # 🔒 1. CANDADO DE ACERO
    if metodo == 'CAJA_CHICA':
        if monto_pagado <= 0:
            flash("⚠️ Si pagas con CAJA CHICA debes indicar el monto a pagar.", "danger")
            return redirect(url_for('productores.libreta'))

        cierre = CierreCaja.query.order_by(CierreCaja.id.desc()).first()
        monto_en_caja = Decimal(str(cierre.monto_usd)) if cierre else Decimal('0')

        if not cierre or monto_en_caja < monto_pagado:
            flash(f"🚫 SIN EFECTIVO: En caja solo hay ${monto_en_caja:.2f}. Usa 'BANCO' o registra a 'CRÉDITO'.", "danger")
            return redirect(url_for('productores.libreta'))

        cierre.monto_usd = float(monto_en_caja - monto_pagado)
        db.session.add(cierre)

    # 📦 2. INVENTARIO
    queso = Producto.query.filter(Producto.nombre.ilike('%QUESO%')).first()
    if queso:
        queso.stock += int(kilos)

    # 📝 3. ASIENTO CONTABLE
    try:
        nuevo_asiento = Asiento(
            descripcion=f"COMPRA QUESO: {kilos}kg de {productor.nombre} | Pago: {metodo}",
            tasa_referencia=valor_tasa,
            referencia_tipo="COMPRA_QUESO",
            referencia_id=productor.id
        )
        db.session.add(nuevo_asiento)
        db.session.flush()

        cta_inv = CuentaContable.query.filter_by(codigo="1.1.03.01").first()
        if cta_inv:
            db.session.add(DetalleAsiento(
                asiento_id=nuevo_asiento.id,
                cuenta_id=cta_inv.id,
                debe_usd=total_queso,
                debe_bs=total_queso * valor_tasa
            ))

        if metodo != 'CREDITO' and monto_pagado > 0:
            cod_pago = "1.1.01.01" if metodo == 'CAJA_CHICA' else "1.1.01.03"
            cta_pago = CuentaContable.query.filter_by(codigo=cod_pago).first()
            if cta_pago:
                db.session.add(DetalleAsiento(
                    asiento_id=nuevo_asiento.id,
                    cuenta_id=cta_pago.id,
                    haber_usd=monto_pagado,
                    haber_bs=monto_pagado * valor_tasa
                ))

        deuda_a_cobrar = Decimal('0.00')
        sobrante_queso = total_queso - monto_pagado
        saldo_anterior = productor.saldo_pendiente_usd

        if sobrante_queso > 0 and saldo_anterior < 0:
            deuda_a_cobrar = min(sobrante_queso, abs(saldo_anterior))
            cta_deuda_prod = CuentaContable.query.filter_by(codigo="1.1.02.02").first()
            if cta_deuda_prod and deuda_a_cobrar > 0:
                db.session.add(DetalleAsiento(
                    asiento_id=nuevo_asiento.id,
                    cuenta_id=cta_deuda_prod.id,
                    haber_usd=deuda_a_cobrar,
                    haber_bs=deuda_a_cobrar * valor_tasa
                ))

        restante_final = total_queso - monto_pagado - deuda_a_cobrar
        if restante_final > 0:
            cta_cxp = CuentaContable.query.filter_by(codigo="2.1.01.01").first()
            if cta_cxp:
                db.session.add(DetalleAsiento(
                    asiento_id=nuevo_asiento.id,
                    cuenta_id=cta_cxp.id,
                    haber_usd=restante_final,
                    haber_bs=restante_final * valor_tasa
                ))

    except Exception as e:
        print(f"❌ Error en asiento contable de entrega: {e}")
        db.session.rollback()

    # 📖 4. LIBRETA DIGITAL
    falta_por_pagar = total_queso - monto_pagado
    db.session.add(MovimientoProductor(
        proveedor_id=p_id,
        tipo='ENTREGA_QUESO',
        descripcion=f"Recibido {kilos}kg. Pago {metodo}: ${monto_pagado}",
        kilos=kilos,
        haber=total_queso,
        debe=monto_pagado,
        saldo_momento=productor.saldo_pendiente_usd + falta_por_pagar,
        anio=datetime.utcnow().year,
        semana_del_anio=datetime.utcnow().isocalendar()[1]
    ))
    productor.saldo_pendiente_usd += falta_por_pagar

    # ✅ MOVIMIENTO CAJA (Efectivo o Banco)
    if monto_pagado > 0:
        tipo_caja_mov = 'Caja USD' if metodo == 'CAJA_CHICA' else ('Banco' if metodo == 'BANCO' else None)
        if tipo_caja_mov:
            monto_caja = monto_pagado if tipo_caja_mov == 'Caja USD' else (monto_pagado * valor_tasa)
            db.session.add(MovimientoCaja(
                fecha=datetime.now(),
                tipo_caja=tipo_caja_mov,
                tipo_movimiento='EGRESO',
                categoria='Compra Queso',
                monto=monto_caja,
                tasa_dia=valor_tasa,
                descripcion=f'Pago queso {kilos}kg a {productor.nombre} ({metodo})',
                modulo_origen='PRODUCTOR',
                referencia_id=int(p_id)
            ))

    db.session.commit()
    flash(f"✅ Compra procesada con éxito vía {metodo}.", "success")
    return redirect(url_for('productores.libreta'))


@productores_bp.route('/registrar_pago_productor', methods=['POST'])
def registrar_pago_productor():
    from models import CuentaContable, Asiento, DetalleAsiento, TasaBCV
    from sqlalchemy import func

    p_id = request.form.get('proveedor_id')
    monto = Decimal(request.form.get('monto', '0'))
    metodo = request.form.get('metodo')
    beneficiario = request.form.get('beneficiario', 'Mismo Productor')
    referencia = request.form.get('referencia', 'S/N')

    # 🛑 RESTRICCIÓN 1: Monto mínimo
    if monto <= 0:
        flash("⚠️ El monto a pagar debe ser mayor a cero.", "danger")
        return redirect(url_for('productores.libreta'))

    productor = Proveedor.query.get(p_id)
    tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    valor_tasa = tasa.valor if tasa else Decimal('1.00')

    # 🧮 CONVERSIÓN DE MONEDA (El input 'monto' siempre viene en USD como indica el label)
    monto_usd = monto
    monto_bs  = monto * valor_tasa

    # 🛑 RESTRICCIÓN 2: Alerta si pagan muy poco en Bs
    if metodo in ['EFECTIVO_BS', 'PAGO_MOVIL', 'TRANSFERENCIA'] and monto < 10:
        flash(f"⚠️ ALERTA: ¿Seguro que vas a pagar solo {monto} Bolívares? Verifique la moneda.", "warning")
        return redirect(url_for('productores.libreta'))

    # 🛑 RESTRICCIÓN 3: Límite de pago único
    if monto_usd > 1000:
        flash(f"⛔ BLOQUEO: Un pago de ${monto_usd:.2f} supera el límite permitido. El sistema abortó.", "danger")
        return redirect(url_for('productores.libreta'))

    # 🛑 RESTRICCIÓN 4: No pagar más de lo que se debe
    saldo_actual = productor.saldo_pendiente_usd
    if monto_usd > (abs(saldo_actual) + 50):
        flash(f"⛔ ERROR CONTABLE: Estás pagando ${monto_usd:.2f} pero {productor.nombre} solo tiene ${abs(saldo_actual):.2f} pendiente. Operación cancelada.", "danger")
        return redirect(url_for('productores.libreta'))

    # 🔒 CANDADO DE CAJA (calcula saldo real desde MovimientoCaja)
    if metodo == 'EFECTIVO':
        ingresos_usd = db.session.query(func.sum(MovimientoCaja.monto)).filter(
            MovimientoCaja.tipo_caja == 'Caja USD',
            MovimientoCaja.tipo_movimiento == 'INGRESO'
        ).scalar() or Decimal('0')

        egresos_usd = db.session.query(func.sum(MovimientoCaja.monto)).filter(
            MovimientoCaja.tipo_caja == 'Caja USD',
            MovimientoCaja.tipo_movimiento == 'EGRESO'
        ).scalar() or Decimal('0')

        saldo_real_usd = Decimal(str(ingresos_usd)) - Decimal(str(egresos_usd))

        if saldo_real_usd < monto_usd:
            flash(f"🚫 Fondos insuficientes en Caja USD. Solo hay ${saldo_real_usd:.2f}.", "danger")
            return redirect(url_for('productores.libreta'))

    elif metodo == 'EFECTIVO_BS':
        ingresos_bs = db.session.query(func.sum(MovimientoCaja.monto)).filter(
            MovimientoCaja.tipo_caja == 'Caja Bs',
            MovimientoCaja.tipo_movimiento == 'INGRESO'
        ).scalar() or Decimal('0')

        egresos_bs = db.session.query(func.sum(MovimientoCaja.monto)).filter(
            MovimientoCaja.tipo_caja == 'Caja Bs',
            MovimientoCaja.tipo_movimiento == 'EGRESO'
        ).scalar() or Decimal('0')

        saldo_real_bs = Decimal(str(ingresos_bs)) - Decimal(str(egresos_bs))

        if saldo_real_bs < monto_bs:
            flash(f"🚫 Fondos insuficientes en Caja Bs. Solo hay Bs {saldo_real_bs:.2f}.", "danger")
            return redirect(url_for('productores.libreta'))

    # 🏦 DEFINIR CAJA DEL MOVIMIENTO
    if metodo == 'EFECTIVO':
        tipo_caja_mov = 'Caja USD'
        monto_mov = monto_usd
    elif metodo == 'EFECTIVO_BS':
        tipo_caja_mov = 'Caja Bs'
        monto_mov = monto_bs
    elif metodo in ['PAGO_MOVIL', 'TRANSFERENCIA']:
        tipo_caja_mov = 'Banco'
        monto_mov = monto_bs
    else:
        tipo_caja_mov = None
        monto_mov = Decimal('0')

    # 📖 LIBRETA SIEMPRE EN USD
    productor.saldo_pendiente_usd -= monto_usd

    # 📝 ASIENTO CONTABLE
    codigo_cta = "1.1.01.01" # Caja USD por defecto
    if metodo == 'EFECTIVO_BS':
        codigo_cta = "1.1.01.02" # Caja Bs (Añadido para mayor precisión)
    elif metodo in ['PAGO_MOVIL', 'TRANSFERENCIA']:
        codigo_cta = "1.1.01.03" # Banco
        
    cuenta_origen = CuentaContable.query.filter_by(codigo=codigo_cta).first()
    cuenta_pasivo = CuentaContable.query.filter_by(codigo="2.1.01").first()

    if not cuenta_origen or not cuenta_pasivo:
        flash("❌ Error: Cuentas contables no configuradas.", "danger")
        return redirect(url_for('productores.libreta'))

    nuevo_asiento = Asiento(
        descripcion=f"PAGO A PRODUCTOR: {productor.nombre} - {metodo} ({referencia})",
        tasa_referencia=valor_tasa,
        referencia_tipo="PAGO_PRODUCTOR",
        referencia_id=productor.id
    )
    db.session.add(nuevo_asiento)
    db.session.flush()

    db.session.add_all([
        DetalleAsiento(asiento_id=nuevo_asiento.id, cuenta_id=cuenta_pasivo.id, debe_usd=monto_usd, debe_bs=monto_bs),
        DetalleAsiento(asiento_id=nuevo_asiento.id, cuenta_id=cuenta_origen.id, haber_usd=monto_usd, haber_bs=monto_bs),
        MovimientoProductor(
            proveedor_id=p_id,
            tipo='PAGO' if productor.saldo_pendiente_usd >= 0 else 'ADELANTO',
            descripcion=f"Pago {metodo} a {beneficiario}. Ref: {referencia} - Bs {monto_bs:.2f} / ${monto_usd:.2f}",
            debe=monto_usd,
            saldo_momento=productor.saldo_pendiente_usd,
            anio=datetime.utcnow().year,
            semana_del_anio=datetime.utcnow().isocalendar()[1]
        )
    ])

    # ✅ MOVIMIENTO DE CAJA
    if tipo_caja_mov:
        db.session.add(MovimientoCaja(
            fecha=datetime.now(),
            tipo_caja=tipo_caja_mov,
            tipo_movimiento='EGRESO',
            categoria='Pago Productor',
            monto=monto_mov,
            tasa_dia=valor_tasa,
            descripcion=f'Pago a {productor.nombre} - {metodo} - Ref: {referencia}',
            modulo_origen='PRODUCTOR',
            referencia_id=int(p_id)
        ))

    db.session.commit()
    flash(f"✅ Pago de ${monto_usd:.2f} registrado y caja actualizada.", "success")
    return redirect(url_for('productores.libreta'))
@productores_bp.route('/abonar_efectivo_productor', methods=['POST'])
def abonar_efectivo_productor():
    from models import CuentaContable, Asiento, DetalleAsiento, TasaBCV

    p_id = request.form.get('proveedor_id')
    monto_input = Decimal(request.form.get('monto', '0') or '0')
    metodo = request.form.get('metodo', 'EFECTIVO_USD')

    # 🛑 RESTRICCIÓN 1: Monto mínimo
    if monto_input <= 0:
        flash("⚠️ El monto debe ser mayor a cero.", "danger")
        return redirect(url_for('productores.libreta'))

    productor = Proveedor.query.get(p_id)
    tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    valor_tasa = tasa.valor if tasa else Decimal('1.00')

    # 🛑 RESTRICCIÓN 2: Alerta de moneda
    if metodo in ['EFECTIVO_BS', 'PAGO_MOVIL'] and monto_input < 10:
        flash(f"⚠️ Error de Moneda: ¿Seguro que el abono es de solo {monto_input} Bolívares? Verifique.", "warning")
        return redirect(url_for('productores.libreta'))

    # 🧮 CONVERSIÓN (El input siempre viene en USD)
    monto_usd = monto_input
    monto_bs  = monto_input * valor_tasa

    # 🛑 RESTRICCIÓN 3: Límite de abono único
    if monto_usd > 500:
        flash(f"⛔ BLOQUEO: Un abono de ${monto_usd:.2f} es inusual. El sistema abortó para proteger la contabilidad.", "danger")
        return redirect(url_for('productores.libreta'))

    # 🛑 RESTRICCIÓN 4: Saldo final no puede dispararse
    saldo_final_proyectado = productor.saldo_pendiente_usd + monto_usd
    if saldo_final_proyectado > 1000:
        flash(f"⛔ ERROR CONTABLE: Este abono dejaría un saldo a favor excesivo (${saldo_final_proyectado:.2f}). Operación cancelada.", "danger")
        return redirect(url_for('productores.libreta'))

    # 💰 ACTUALIZAR CAJA
    cierre = CierreCaja.query.order_by(CierreCaja.id.desc()).first()
    if cierre:
        if metodo == 'EFECTIVO_USD':
            cierre.monto_usd = float(Decimal(str(cierre.monto_usd)) + monto_usd)
        elif metodo == 'EFECTIVO_BS':
            cierre.monto_bs = float(Decimal(str(cierre.monto_bs or 0)) + monto_bs)
        db.session.add(cierre)

    # ⚖️ ACTUALIZAR LIBRETA
    productor.saldo_pendiente_usd += monto_usd

    # 📖 MOVIMIENTO EN LIBRETA
    db.session.add(MovimientoProductor(
        proveedor_id=p_id,
        tipo='ABONO_POS',
        descripcion=f"Abono POS ({metodo.replace('_', ' ')}): Bs {monto_bs:.2f} / ${monto_usd:.2f}",
        debe=monto_usd,
        saldo_momento=productor.saldo_pendiente_usd,
        anio=datetime.utcnow().year,
        semana_del_anio=datetime.utcnow().isocalendar()[1]
    ))

    # ✅ MOVIMIENTO CAJA
    tipo_caja_mov = 'Caja USD' if metodo == 'EFECTIVO_USD' else ('Caja Bs' if metodo == 'EFECTIVO_BS' else 'Banco')
    monto_caja_final = monto_usd if tipo_caja_mov == 'Caja USD' else monto_bs

    db.session.add(MovimientoCaja(
        fecha=datetime.now(),
        tipo_caja=tipo_caja_mov,
        tipo_movimiento='INGRESO',
        categoria='Abono Productor',
        monto=monto_caja_final,
        tasa_dia=valor_tasa,
        descripcion=f'Abono de {productor.nombre} - {metodo}',
        modulo_origen='PRODUCTOR',
        referencia_id=int(p_id)
    ))
    # 📝 ASIENTO CONTABLE
    try:
        cod_cuenta = '1.1.01.01' if metodo == 'EFECTIVO_USD' else ('1.1.01.02' if metodo == 'EFECTIVO_BS' else '1.1.01.03')
        cta_caja = CuentaContable.query.filter_by(codigo=cod_cuenta).first()
        cta_deuda = CuentaContable.query.filter_by(codigo='1.1.02.02').first()

        if cta_caja and cta_deuda:
            nuevo_asiento = Asiento(
                descripcion=f"ABONO POS: {productor.nombre} - ${monto_usd:.2f}",
                tasa_referencia=valor_tasa,
                referencia_tipo="ABONO_PRODUCTOR",
                referencia_id=productor.id
            )
            db.session.add(nuevo_asiento)
            db.session.flush()

            db.session.add_all([
                DetalleAsiento(asiento_id=nuevo_asiento.id, cuenta_id=cta_caja.id, debe_usd=monto_usd, debe_bs=monto_bs),
                DetalleAsiento(asiento_id=nuevo_asiento.id, cuenta_id=cta_deuda.id, haber_usd=monto_usd, haber_bs=monto_bs)
            ])
    except Exception as e:
        print(f"⚠️ Asiento contable falló: {e}")

    db.session.commit()
    flash(f"✅ Abono de ${monto_usd:.2f} registrado correctamente.", "success")
    return redirect(url_for('productores.libreta'))

@productores_bp.route('/mi-ficha')
@login_required
def mi_ficha():
    # Solo productores pueden entrar aquí
    if current_user.role != 'productor':
        return redirect(url_for('pos.pos'))
    
    # Busca el proveedor vinculado a este usuario
    proveedor = current_user.proveedor
    
    if not proveedor:
        flash("No tienes un perfil de productor asignado.", "warning")
        return redirect(url_for('auth.login'))
    
    # Trae sus movimientos (queso, pagos, deudas)
    movimientos = MovimientoProductor.query.filter_by(
        proveedor_id=proveedor.id
    ).order_by(MovimientoProductor.fecha.desc()).limit(20).all()
    
    return render_template('ficha_productor.html', 
                           proveedor=proveedor,
                           movimientos=movimientos)
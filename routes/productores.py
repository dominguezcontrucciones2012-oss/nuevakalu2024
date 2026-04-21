from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Proveedor, MovimientoProductor, Producto, CierreCaja, PagoProductor, MovimientoCaja, AuditoriaInventario, CuentaPorPagar, AbonoCuentaPorPagar, ahora_ve
from flask_login import login_required, current_user
from routes.decorators import staff_required
from sqlalchemy import func, desc
from datetime import datetime
from utils import seguro_decimal
from decimal import Decimal
import logging

logger = logging.getLogger('KALU.productores')
productores_bp = Blueprint('productores', __name__)

@productores_bp.route('/libreta_productores')
@login_required
@staff_required
def libreta():
    from sqlalchemy import or_
    productores = Proveedor.query.filter(or_(Proveedor.es_productor==True, Proveedor.es_obrero==True)).order_by(Proveedor.nombre).all()
    anio_actual = datetime.utcnow().year
    semana_actual = datetime.utcnow().isocalendar()[1]

    for p in productores:
        total_anio = db.session.query(func.sum(MovimientoProductor.kilos)).filter(
            MovimientoProductor.proveedor_id == p.id,
            MovimientoProductor.tipo == 'ENTREGA_QUESO',
            MovimientoProductor.anio == anio_actual
        ).scalar() or Decimal('0')
        p.total_kilos = total_anio

        # Kilos traídos por este productor en la SEMANA ACTUAL
        kilos_semana = db.session.query(func.sum(MovimientoProductor.kilos)).filter(
            MovimientoProductor.proveedor_id == p.id,
            MovimientoProductor.tipo == 'ENTREGA_QUESO',
            MovimientoProductor.anio == anio_actual,
            MovimientoProductor.semana_del_anio == semana_actual
        ).scalar() or Decimal('0')
        p.kilos_semana = kilos_semana

    # Kilos de la semana actual para el dashboard
    total_kilos_semana = db.session.query(func.sum(MovimientoProductor.kilos)).filter(
        MovimientoProductor.tipo == 'ENTREGA_QUESO',
        MovimientoProductor.anio == anio_actual,
        MovimientoProductor.semana_del_anio == semana_actual
    ).scalar() or Decimal('0')

    # Lógica del Ranking (para que no se pierda)
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
        kilos = r.total_kilos or Decimal('0')
        semanas = int(r.semanas_fiel or 0)
        compras = r.total_compras or Decimal('0')
        puntos = int((kilos / 10) + (Decimal(str(semanas)) * 10) + (compras / 5))
        ranking.append({
            'nombre': r.nombre,
            'total_kilos': kilos.quantize(Decimal('0.01')),
            'semanas_fiel': semanas,
            'puntos_totales': puntos
        })

    total_deuda = sum(p.saldo_pendiente_usd for p in productores if p.saldo_pendiente_usd > 0)
    total_haber = sum(abs(p.saldo_pendiente_usd) for p in productores if p.saldo_pendiente_usd < 0)

    from models import TasaBCV
    tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    valor_tasa = Decimal(str(tasa.valor)) if tasa else Decimal('40.0')

    return render_template(
        'libreta_productores.html',
        productores=productores,
        ranking=ranking,
        anio_actual=anio_actual,
        semana_actual=semana_actual,
        tasa_bcv=valor_tasa,
        total_kilos_semana=total_kilos_semana,
        total_deuda=total_deuda,
        total_haber=total_haber
    )

@productores_bp.route('/registrar_entrega', methods=['POST'])
@login_required
@staff_required
def registrar_entrega():
    from models import CuentaContable, Asiento, DetalleAsiento, TasaBCV

    p_id = request.form.get('proveedor_id')
    kilos = seguro_decimal(request.form.get('kilos'))
    precio = seguro_decimal(request.form.get('precio'))
    metodo = request.form.get('metodo_pago')

    monto_pagado = seguro_decimal(request.form.get('monto_pagado')) if metodo != 'CREDITO' else Decimal('0.00')

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
        monto_en_caja = cierre.monto_usd if cierre else Decimal('0')

        if not cierre or monto_en_caja < monto_pagado:
            flash(f"🚫 SIN EFECTIVO: En caja solo hay ${monto_en_caja:.2f}. Usa 'BANCO' o registra a 'CRÉDITO'.", "danger")
            return redirect(url_for('productores.libreta'))

        cierre.monto_usd = monto_en_caja - monto_pagado
        db.session.add(cierre)

    # 📦 2. INVENTARIO
    queso = Producto.query.filter(Producto.nombre.ilike('%QUESO%')).first()
    if queso:
        antes = Decimal(str(queso.stock))
        queso.stock = antes + kilos
        
        # 📜 AUDITORIA
        db.session.add(AuditoriaInventario(
            usuario_id=current_user.id,
            usuario_nombre=current_user.username,
            producto_id=queso.id,
            producto_nombre=queso.nombre,
            accion='RECEPCION_QUESO',
            cantidad_antes=antes,
            cantidad_despues=queso.stock,
            fecha=datetime.now()
        ))

    # 📝 3. ASIENTO CONTABLE
    try:
        nuevo_asiento = Asiento(
            descripcion=f"COMPRA QUESO: {kilos}kg de {productor.nombre} | Pago: {metodo}",
            tasa_referencia=valor_tasa,
            referencia_tipo="COMPRA_QUESO",
            referencia_id=productor.id,
            user_id=current_user.id
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
        logger.error(f"Error en asiento contable de entrega: {e}")
        db.session.rollback()

    # 📖 4. LIBRETA DIGITAL
    falta_por_pagar = total_queso - monto_pagado
    
    # Sincronización con Cuentas por Pagar (CXP)
    if falta_por_pagar > 0:
        from models import Compra, CuentaPorPagar
        # Creamos una "Compra" fantasma para que aparezca en CXP
        nueva_compra = Compra(
            proveedor_id=p_id,
            numero_factura=f"ENTREGA-{datetime.now().strftime('%Y%m%d%H%M')}",
            fecha=datetime.now(),
            total_usd=total_queso,
            metodo_pago='Credito',
            estado='Pendiente'
        )
        db.session.add(nueva_compra)
        db.session.flush()

        # Creamos la factura pendiente en CXP
        nueva_cxp = CuentaPorPagar(
            proveedor_id=p_id,
            compra_id=nueva_compra.id,
            numero_factura=nueva_compra.numero_factura,
            fecha=datetime.now(),
            monto_total_usd=total_queso,
            monto_abonado_usd=monto_pagado,
            saldo_pendiente_usd=falta_por_pagar,
            estatus='Pendiente' if monto_pagado == 0 else 'Parcial'
        )
        db.session.add(nueva_cxp)

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
                referencia_id=int(p_id),
                user_id=current_user.id
            ))

    db.session.commit()
    logger.info(f"Recepción de queso: {kilos}kg de {productor.nombre} por {current_user.username}")
    flash(f"✅ Compra procesada con éxito vía {metodo}.", "success")
    return redirect(url_for('productores.libreta'))


@productores_bp.route('/registrar_pago_productor', methods=['POST'])
@login_required
@staff_required
def registrar_pago_productor():
    from models import CuentaContable, Asiento, DetalleAsiento, TasaBCV
    from flask import jsonify
    from sqlalchemy import func

    try:
        p_id = int(request.form.get('proveedor_id'))
        monto = seguro_decimal(request.form.get('monto', '0'))
        metodo = request.form.get('metodo')
        beneficiario = request.form.get('beneficiario', 'Mismo Productor')
        referencia = request.form.get('referencia', 'S/N')

        # 🛑 RESTRICCIÓN 1: Monto mínimo
        if monto <= 0:
            return jsonify({'status': 'error', 'message': "⚠️ El monto a pagar debe ser mayor a cero."})

        productor = Proveedor.query.get(p_id)
        if not productor:
             return jsonify({'status': 'error', 'message': "❌ Productor no encontrado."})

        tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
        valor_tasa = tasa.valor if tasa else Decimal('1.00')

        # 🧮 CONVERSIÓN DE MONEDA
        moneda_entregada = request.form.get('moneda_entregada', 'USD')
        
        if moneda_entregada == 'Bs':
            monto_bs = monto
            monto_usd = monto / valor_tasa
        else:
            monto_usd = monto
            monto_bs  = monto * valor_tasa

        # 🛑 RESTRICCIÓN 2: Alerta si pagan muy poco en Bs
        if metodo in ['EFECTIVO_BS', 'PAGO_MOVIL', 'TRANSFERENCIA'] and monto_bs < 10:
             return jsonify({'status': 'error', 'message': f"⚠️ ALERTA: ¿Seguro que vas a pagar solo {monto_bs:.2f} Bolívares? Verifique la moneda."})

        # 🛑 RESTRICCIÓN 3: Límite de pago único
        if monto_usd > 1000:
            return jsonify({'status': 'error', 'message': f"⛔ BLOQUEO: Un pago de ${monto_usd:.2f} supera el límite permitido."})

        # 🛑 RESTRICCIÓN 4: No pagar más de lo que se debe
        saldo_actual = productor.saldo_pendiente_usd
        if monto_usd > (abs(saldo_actual) + 50):
            return jsonify({'status': 'error', 'message': f"⛔ ERROR CONTABLE: Estás pagando ${monto_usd:.2f} pero {productor.nombre} solo tiene ${abs(saldo_actual):.2f} pendiente."})

        # 🔒 CANDADO DE CAJA
        if metodo == 'EFECTIVO':
            ingresos_usd = db.session.query(func.sum(MovimientoCaja.monto)).filter(
                MovimientoCaja.tipo_caja == 'Caja USD',
                MovimientoCaja.tipo_movimiento == 'INGRESO'
            ).scalar() or Decimal('0')

            egresos_usd = db.session.query(func.sum(MovimientoCaja.monto)).filter(
                MovimientoCaja.tipo_caja == 'Caja USD',
                MovimientoCaja.tipo_movimiento == 'EGRESO'
            ).scalar() or Decimal('0')

            saldo_real_usd = ingresos_usd - egresos_usd
            if saldo_real_usd < monto_usd:
                return jsonify({'status': 'error', 'message': f"🚫 Fondos insuficientes en Caja USD. Solo hay ${saldo_real_usd:.2f}."})

        elif metodo == 'EFECTIVO_BS':
            ingresos_bs = db.session.query(func.sum(MovimientoCaja.monto)).filter(
                MovimientoCaja.tipo_caja == 'Caja Bs',
                MovimientoCaja.tipo_movimiento == 'INGRESO'
            ).scalar() or Decimal('0')

            egresos_bs = db.session.query(func.sum(MovimientoCaja.monto)).filter(
                MovimientoCaja.tipo_caja == 'Caja Bs',
                MovimientoCaja.tipo_movimiento == 'EGRESO'
            ).scalar() or Decimal('0')

            saldo_real_bs = ingresos_bs - egresos_bs
            if saldo_real_bs < monto_bs:
                return jsonify({'status': 'error', 'message': f"🚫 Fondos insuficientes en Caja Bs. Solo hay Bs {saldo_real_bs:.2f}."})

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

        # 🎯 VINCULAR CON CUENTAS POR PAGAR (Sincronización automática)
        # Buscamos facturas pendientes del proveedor para saldarlas con este pago
        cuentas_pendientes = CuentaPorPagar.query.filter(
            CuentaPorPagar.proveedor_id == p_id,
            CuentaPorPagar.estatus.in_(['Pendiente', 'Parcial'])
        ).order_by(CuentaPorPagar.fecha.asc()).all()

        monto_a_distribuir = monto_usd
        for cxp in cuentas_pendientes:
            if monto_a_distribuir <= 0:
                break
            
            # Calculamos cuánto de este pago se aplica a esta factura
            pago_aplicado = min(monto_a_distribuir, cxp.saldo_pendiente_usd)
            
            cxp.monto_abonado_usd += pago_aplicado
            cxp.saldo_pendiente_usd -= pago_aplicado
            monto_a_distribuir -= pago_aplicado
            
            # Actualizar estatus de la factura
            if cxp.saldo_pendiente_usd <= 0:
                cxp.saldo_pendiente_usd = 0
                cxp.estatus = 'Pagado'
            else:
                cxp.estatus = 'Parcial'
            
            # Registrar el abono interno en la factura para el historial de CXP
            db.session.add(AbonoCuentaPorPagar(
                cuenta_id=cxp.id,
                monto_usd=pago_aplicado,
                metodo_pago=metodo,
                descripcion=f"Saldado desde Libreta Digital | Ref: {referencia}"
            ))

        # 📝 ASIENTO CONTABLE
        codigo_cta = "1.1.01.01" # Caja USD por defecto
        if metodo == 'EFECTIVO_BS':
            codigo_cta = "1.1.01.02" 
        elif metodo in ['PAGO_MOVIL', 'TRANSFERENCIA']:
            codigo_cta = "1.1.01.03" # Banco
            
        cuenta_origen = CuentaContable.query.filter_by(codigo=codigo_cta).first()
        cuenta_pasivo = CuentaContable.query.filter_by(codigo="2.1.01").first()

        if not cuenta_origen or not cuenta_pasivo:
            return jsonify({'status': 'error', 'message': "❌ Error: Cuentas contables no configuradas (1.1.01.xx o 2.1.01)."})

        nuevo_asiento = Asiento(
            descripcion=f"PAGO A PRODUCTOR: {productor.nombre} - {metodo} ({referencia})",
            tasa_referencia=valor_tasa,
            referencia_tipo="PAGO_PRODUCTOR",
            referencia_id=productor.id,
            user_id=current_user.id
        )
        db.session.add(nuevo_asiento)
        db.session.flush()

        # 📖 ACTUALIZAR SALDO
        productor.saldo_pendiente_usd -= monto_usd

        db.session.add_all([
            DetalleAsiento(asiento_id=nuevo_asiento.id, cuenta_id=cuenta_pasivo.id, debe_usd=monto_usd, debe_bs=monto_bs),
            DetalleAsiento(asiento_id=nuevo_asiento.id, cuenta_id=cuenta_origen.id, haber_usd=monto_usd, haber_bs=monto_bs),
            MovimientoProductor(
                proveedor_id=p_id,
                tipo='PAGO',
                descripcion=f"Pago {metodo} a {beneficiario}. Ref: {referencia}",
                debe=monto_usd,
                saldo_momento=productor.saldo_pendiente_usd,
                anio=datetime.now().year,
                semana_del_anio=datetime.now().isocalendar()[1],
                fecha=datetime.now()
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
                referencia_id=int(p_id),
                user_id=current_user.id
            ))

        db.session.commit()
        logger.info(f"Pago a productor {productor.nombre}: ${monto_usd} ({metodo}) por {current_user.username}")
        return jsonify({
            'status': 'success', 
            'message': f"✅ Pago de ${monto_usd:.2f} registrado con éxito."
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error fatal registrando pago a productor: {e}")
        return jsonify({'status': 'error', 'message': f"❌ Error interno: {str(e)}"})

@productores_bp.route('/abonar_efectivo_productor', methods=['POST'])
@login_required
@staff_required
def abonar_efectivo_productor():
    from models import CuentaContable, Asiento, DetalleAsiento, TasaBCV
    from flask import jsonify

    try:
        p_id = request.form.get('proveedor_id')
        monto_input = seguro_decimal(request.form.get('monto', '0'))
        metodo = request.form.get('metodo', 'EFECTIVO_USD')
        referencia = request.form.get('referencia', 'S/N')

        # 🛑 RESTRICCIÓN 1: Monto mínimo
        if monto_input <= 0:
            return jsonify({'status': 'error', 'message': "⚠️ El monto debe ser mayor a cero."})

        productor = Proveedor.query.get(p_id)
        if not productor:
            return jsonify({'status': 'error', 'message': "❌ Productor no encontrado."})

        tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
        valor_tasa = tasa.valor if tasa else Decimal('1.00')

        # 🧮 CONVERSIÓN
        moneda_entregada = request.form.get('moneda_entregada', 'USD')
        
        if moneda_entregada == 'Bs':
            monto_bs = monto_input
            monto_usd = monto_input / valor_tasa
        else:
            monto_usd = monto_input
            monto_bs  = monto_input * valor_tasa

        # 🛑 RESTRICCIÓN 2: Alerta de moneda
        if metodo in ['EFECTIVO_BS', 'PAGO_MOVIL'] and monto_bs < 10:
            return jsonify({'status': 'error', 'message': f"⚠️ Error de Moneda: ¿Seguro que el abono es de solo {monto_bs:.2f} Bolívares?"})

        # 🛑 RESTRICCIÓN 3: Límite de abono único
        if monto_usd > 500:
            return jsonify({'status': 'error', 'message': f"⛔ BLOQUEO: Un abono de ${monto_usd:.2f} es inusual e inválido."})

        # 🛑 RESTRICCIÓN 4: Saldo final no puede dispararse
        saldo_final_proyectado = productor.saldo_pendiente_usd + monto_usd
        if saldo_final_proyectado > 1000:
            return jsonify({'status': 'error', 'message': f"⛔ ERROR CONTABLE: Este abono dejaría un saldo a favor excesivo (${saldo_final_proyectado:.2f})."})

        # 💰 ACTUALIZAR CAJA
        cierre = CierreCaja.query.order_by(CierreCaja.id.desc()).first()
        if cierre:
            if metodo == 'EFECTIVO_USD':
                cierre.monto_usd = (Decimal(str(cierre.monto_usd or 0)) + monto_usd)
            elif metodo == 'EFECTIVO_BS':
                cierre.monto_bs = (Decimal(str(cierre.monto_bs or 0)) + monto_bs)
            db.session.add(cierre)

        # ⚖️ ACTUALIZAR LIBRETA (Abono a favor del productor, disminuye su deuda o aumenta su crédito)
        productor.saldo_pendiente_usd += monto_usd

        # 📖 MOVIMIENTO EN LIBRETA
        db.session.add(MovimientoProductor(
            proveedor_id=p_id,
            tipo='ABONO',
            descripcion=f"[DEBUG CALU MANUAL] Abono de Dinero ({metodo.replace('_', ' ')}): {referencia if referencia else ''}",
            haber=monto_usd,
            monto_usd=monto_usd,
            debe=0,
            saldo_momento=productor.saldo_pendiente_usd,
            anio=ahora_ve().year,
            semana_del_anio=ahora_ve().isocalendar()[1],
            fecha=ahora_ve()
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
            referencia_id=int(p_id),
            user_id=current_user.id
        ))

        # 📝 ASIENTO CONTABLE
        cod_cuenta = '1.1.01.01' if metodo == 'EFECTIVO_USD' else ('1.1.01.02' if metodo == 'EFECTIVO_BS' else '1.1.01.03')
        cta_caja = CuentaContable.query.filter_by(codigo=cod_cuenta).first()
        cta_deuda = CuentaContable.query.filter_by(codigo='1.1.02.02').first()

        if cta_caja and cta_deuda:
            nuevo_asiento = Asiento(
                descripcion=f"ABONO POS: {productor.nombre} - ${monto_usd:.2f}",
                tasa_referencia=valor_tasa,
                referencia_tipo="ABONO_PRODUCTOR",
                referencia_id=productor.id,
                user_id=current_user.id
            )
            db.session.add(nuevo_asiento)
            db.session.flush()

            db.session.add_all([
                DetalleAsiento(asiento_id=nuevo_asiento.id, cuenta_id=cta_caja.id, debe_usd=monto_usd, debe_bs=monto_bs),
                DetalleAsiento(asiento_id=nuevo_asiento.id, cuenta_id=cta_deuda.id, haber_usd=monto_usd, haber_bs=monto_bs)
            ])

        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': f"✅ Abono de ${monto_usd:.2f} registrado correctamente."
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error registrando abono de productor: {e}")
        return jsonify({'status': 'error', 'message': f"❌ Error interno: {str(e)}"})


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
        return redirect(url_for('auth.ingresar'))
    
    # Trae sus movimientos (queso, pagos, deudas)
    movimientos = MovimientoProductor.query.filter_by(
        proveedor_id=proveedor.id
    ).order_by(MovimientoProductor.fecha.desc()).limit(20).all()
    
    return render_template('ficha_productor.html', 
                           proveedor=proveedor,
                           movimientos=movimientos)

@productores_bp.route('/eliminar_movimiento/<int:mov_id>', methods=['POST'])
@login_required
@staff_required
def eliminar_movimiento(mov_id):
    if current_user.role not in ['admin', 'dueno']:
        flash("⛔ No tienes permiso para esta acción.", "danger")
        return redirect(url_for('productores.libreta'))
    
    mov = MovimientoProductor.query.get_or_404(mov_id)
    productor = mov.proveedor

    try:
        # Revertir saldo
        # Si fue haber (sumó saldo), ahora lo restamos
        # Si fue debe (restó saldo), ahora lo sumamos
        productor.saldo_pendiente_usd = (productor.saldo_pendiente_usd or Decimal('0')) - (mov.haber or 0) + (mov.debe or 0)
        
        # Neutralizar en caja si era un ingreso de dinero
        if mov.tipo in ['ABONO', 'ABONO_EFECTIVO']:
             db.session.add(MovimientoCaja(
                fecha=ahora_ve(), tipo_caja='Banco', tipo_movimiento='EGRESO',
                categoria='Anulación Abono', monto=mov.haber if mov.haber > 0 else mov.debe,
                descripcion=f"ANULACIÓN de Abono #{mov.id} - {productor.nombre}",
                user_id=current_user.id
            ))

        db.session.delete(mov)
        db.session.commit()
        flash("✅ Movimiento eliminado y saldo reversado con éxito.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al eliminar: {str(e)}", "danger")
    
    return redirect(url_for('productores.libreta'))
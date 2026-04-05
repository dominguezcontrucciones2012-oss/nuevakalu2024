from flask import Blueprint, render_template, redirect, url_for, flash, jsonify,request
from flask_login import login_required, current_user
from models import db, Venta, TasaBCV, CierreCaja, Asiento, MovimientoCaja, Compra, CompraDetalle, HistorialPago
from datetime import datetime
from decimal import Decimal
from sqlalchemy import func
import json

cierre_bp = Blueprint('cierre', __name__)

def _get_ventas_hoy(hoy_date):
    return Venta.query.filter(func.date(Venta.fecha) == hoy_date).all()

def _calcular_resumen(ventas, hoy_date=None):
    r = {
        'efectivo_usd': 0.0, 'efectivo_bs': 0.0, 'pago_movil': 0.0,
        'debito': 0.0, 'biopago': 0.0, 'cobro_queso': 0.0,
        'fiado_nuevo': 0.0, 'total_general': 0.0, 'conteo': len(ventas),
        'pagos_productores_usd': 0.0,
        'pagos_productores_bs': 0.0,
        'total_compras_usd': 0.0,
    }
    for v in ventas:
        r['total_general']  += float(v.total_usd or 0)
        r['efectivo_usd']   += float(v.pago_efectivo_usd or 0)
        r['efectivo_bs']    += float(v.pago_efectivo_bs or 0)
        r['pago_movil']     += float(v.pago_movil_bs or 0)
        r['debito']         += float(v.pago_transferencia_bs or 0)
        r['biopago']        += float(v.biopago_bdv or 0)
        if v.es_fiado:
            r['fiado_nuevo'] += float(v.saldo_pendiente_usd or 0)

    if hoy_date:
        # ✅ NUEVO: Abonos de deudas viejas cobradas HOY
        from models import HistorialPago
        abonos_hoy = HistorialPago.query.filter(func.date(HistorialPago.fecha) == hoy_date).all()
        for abono in abonos_hoy:
            metodo = abono.metodo_pago
            if metodo == 'ABONO INICIAL':
                continue  # NO sumar abonos iniciales de ventas de hoy (ya están sumados como efectivo en la Venta)
            
            monto_usd = float(abono.monto_usd or 0)
            monto_bs  = float(abono.monto_bs or 0)
            if metodo == 'EFECTIVO_USD':
                r['efectivo_usd']  += monto_usd
            elif metodo == 'EFECTIVO_BS':
                r['efectivo_bs']   += monto_bs
            elif metodo == 'PAGO_MOVIL':
                r['pago_movil']    += monto_bs
            elif metodo == 'DEBITO':
                r['debito']        += monto_bs
            elif metodo == 'BIOPAGO':
                r['biopago']       += monto_bs
            r['total_general'] += monto_usd

        # 🛡️ Productores (intacto)
        movs_productores = MovimientoCaja.query.filter(
            func.date(MovimientoCaja.fecha) == hoy_date,
            MovimientoCaja.tipo_movimiento == 'SALIDA',
            MovimientoCaja.categoria == 'Pago Productor'
        ).all()
        r['pagos_productores_usd'] = sum(
            float(m.monto or 0) for m in movs_productores if m.tipo_caja == 'CAJA_USD'
        )
        r['pagos_productores_bs'] = sum(
            float(m.monto or 0) for m in movs_productores if m.tipo_caja in ['CAJA_BS', 'BANCO']
        )

        # 🛡️ Compras (intacto)
        compras_hoy = Compra.query.filter(func.date(Compra.fecha) == hoy_date).all()
        r['total_compras_usd'] = sum(float(c.total_usd or 0) for c in compras_hoy)

    r['fiado'] = r['fiado_nuevo']
    r['transferencia'] = r['debito']
    return r


@cierre_bp.route('/reporte_cierre')
@login_required
def vista_cierre():
    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = float(tasa_obj.valor) if tasa_obj else 1.0
    hoy_date = datetime.now().date()
    ventas_hoy = _get_ventas_hoy(hoy_date)
    r = _calcular_resumen(ventas_hoy, hoy_date)
    ya_cerrado = CierreCaja.query.filter_by(fecha=hoy_date).first()

    # ✅ Movimientos del día para la tabla
    movs_hoy = MovimientoCaja.query.filter(
        func.date(MovimientoCaja.fecha) == hoy_date
    ).order_by(MovimientoCaja.fecha.desc()).all()

    # ✅ Historial reciente para la tabla de abajo
    cierres_historial = CierreCaja.query.order_by(CierreCaja.fecha.desc()).limit(10).all()

    return render_template('cierre_diario.html',
        r=r,
        ventas_hoy=ventas_hoy,
        fecha=hoy_date,
        tasa=tasa,
        ya_cerrado=ya_cerrado,
        movs_hoy=movs_hoy,
        cierres_historial=cierres_historial,
    )

@cierre_bp.route('/ejecutar_cierre', methods=['POST'])
@login_required
def ejecutar_cierre():
    if current_user.role not in ['admin', 'supervisor', 'cajero']:
        flash('⛔ No tienes permiso para ejecutar el cierre. Llama a un supervisor.', 'danger')
        return redirect(url_for('cierre.vista_cierre'))
    hoy_date = datetime.now().date()
    ya_cerrado = CierreCaja.query.filter_by(fecha=hoy_date).first()
    if ya_cerrado:
        flash('⚠️ Ya existe un cierre guardado para hoy.', 'warning')
        return redirect(url_for('cierre.vista_cierre'))

    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = float(tasa_obj.valor) if tasa_obj else 1.0

    ventas_hoy = _get_ventas_hoy(hoy_date)
    r = _calcular_resumen(ventas_hoy, hoy_date)

    # ---------------------------------------------------------
    # ✅ PARCHE: Sumar abonos de deudas al JSON de ventas para el historial
    # ---------------------------------------------------------
    from models import HistorialPago
    abonos_hoy = HistorialPago.query.filter(func.date(HistorialPago.fecha) == hoy_date).all()
    
    # Preparar JSON de ventas
    lista_ventas = []
    for v in ventas_hoy:
        lista_ventas.append({
            'id': v.id,
            'hora': v.fecha.strftime('%I:%M %p'),
            'cliente': v.nombre_cliente_final,
            'total_usd': float(v.total_usd or 0),
            'efectivo_usd': float(v.pago_efectivo_usd or 0),
            'efectivo_bs': float(v.pago_efectivo_bs or 0),
            'pago_movil': float(v.pago_movil_bs or 0),
            'debito': float(v.pago_transferencia_bs or 0),
            'biopago': float(v.biopago_bdv or 0),
            'fiado': v.es_fiado,
            'saldo_pendiente': float(v.saldo_pendiente_usd or 0),
            'productos': [{'nombre': d.producto.nombre, 'cantidad': float(d.cantidad), 'precio': float(d.precio_unitario_usd)} for d in v.detalles]
        })

    # ✅ Agregar los abonos a la lista de ventas para que salgan en el "Ver Cierre"
    for a in abonos_hoy:
        if a.metodo_pago == 'ABONO INICIAL':
            continue  # Omitir abonos iniciales de fiados para no duplicar en el resumen

        lista_ventas.append({
            'id': f"ABONO-{a.id}",
            'hora': a.fecha.strftime('%I:%M %p'),
            'cliente': f"ABONO: {a.cliente.nombre if a.cliente else 'S/N'}",
            'total_usd': float(a.monto_usd or 0),
            'efectivo_usd': float(a.monto_usd if a.metodo_pago == 'EFECTIVO_USD' else 0),
            'efectivo_bs': float(a.monto_bs if a.metodo_pago == 'EFECTIVO_BS' else 0),
            'pago_movil': float(a.monto_bs if a.metodo_pago == 'PAGO_MOVIL' else 0),
            'debito': float(a.monto_bs if a.metodo_pago == 'DEBITO' else 0),
            'biopago': float(a.monto_bs if a.metodo_pago == 'BIOPAGO' else 0),
            'fiado': False,
            'saldo_pendiente': 0,
            'productos': [{'nombre': 'ABONO DE DEUDA', 'cantidad': 1, 'precio': float(a.monto_usd or 0)}]
        })

    # Compras del día (Tu lógica intacta)
    compras_hoy = Compra.query.filter(func.date(Compra.fecha) == hoy_date).all()
    total_compras = sum(float(c.total_usd or 0) for c in compras_hoy)
    lista_compras = []
    for c in compras_hoy:
        lista_compras.append({
            'id': c.id,
            'proveedor': c.proveedor.nombre if c.proveedor else 'Desconocido',
            'total_usd': float(c.total_usd or 0),
            'productos': [{'nombre': d.producto.nombre, 'cantidad': float(d.cantidad), 'costo': float(d.costo_unitario)} for d in c.detalles]
        })

    # 1. Guardar en CierreCaja (r ya trae los abonos sumados por _calcular_resumen)
    nuevo_cierre = CierreCaja(
        fecha=hoy_date,
        monto_bs=r['efectivo_bs'],
        monto_usd=r['efectivo_usd'],
        pago_movil=r['pago_movil'],
        transferencia=r['debito'],
        biopago=r['biopago'],
        tasa_cierre=tasa,
        total_ventas_usd=r['total_general'],
        total_compras_usd=total_compras,
        fiado_dia_usd=r['fiado_nuevo'],
        detalle_ventas=json.dumps(lista_ventas),
        detalle_compras=json.dumps(lista_compras)
    )
    db.session.add(nuevo_cierre)

    # --- PARCHE DE SEGURIDAD: NO DUPLICAR MOVIMIENTOS ---
    # Comentamos esta sección porque las ventas y abonos ya registran sus propios 
    # movimientos en tiempo real. Crear un resumen aquí infla los saldos de caja.
    """
    entradas = [
        ('Caja USD', 'INGRESO', 'Ventas Efectivo USD', r['efectivo_usd']),
        ('Caja Bs',  'INGRESO', 'Ventas Efectivo Bs',  r['efectivo_bs']),
        ('Banco',    'INGRESO', 'Ventas Pago Móvil',   r['pago_movil']),
        ('Banco',    'INGRESO', 'Ventas Débito',        r['debito']),
        ('Banco',    'INGRESO', 'Ventas Biopago BDV',   r['biopago']),
    ]
    for tipo_caja, tipo_mov, categoria, monto in entradas:
        if monto and float(monto) > 0:
            db.session.add(MovimientoCaja(
                tipo_caja=tipo_caja,
                tipo_movimiento=tipo_mov,
                categoria=categoria,
                monto=Decimal(str(monto)),
                tasa_dia=Decimal(str(tasa)),
                descripcion=f'Cierre de caja {hoy_date}',
                modulo_origen='CIERRE',
                user_id=current_user.id
            ))
    """

    db.session.commit()
    flash('✅ Cierre del día guardado y contabilidad actualizada.', 'success')
    return redirect(url_for('cierre.vista_cierre'))

@cierre_bp.route('/ver_cierre/<int:cierre_id>')
@login_required
def ver_cierre(cierre_id):
    cierre = CierreCaja.query.get_or_404(cierre_id)
    ventas  = json.loads(cierre.detalle_ventas  or '[]')
    compras = json.loads(cierre.detalle_compras or '[]')
    return render_template('ver_cierre.html', cierre=cierre, ventas=ventas, compras=compras)

@cierre_bp.route('/historial_cierres')
@login_required
def historial_cierres():
    if current_user.role not in ['admin', 'supervisor']:
        flash('⛔ No tienes permiso para ver el historial de cierres.', 'danger')
        return redirect(url_for('cierre.vista_cierre'))
    cierres = CierreCaja.query.order_by(CierreCaja.fecha.desc()).all()
    return render_template('historial_cierres.html', cierres=cierres)

@cierre_bp.route('/ejecutar_cierre_retroactivo', methods=['POST'])
@login_required
def ejecutar_cierre_retroactivo():
    if current_user.role not in ['admin', 'supervisor']:
        flash('⛔ No tienes permiso.', 'danger')
        return redirect(url_for('cierre.vista_cierre'))

    fecha_str = request.form.get('fecha_retroactiva')
    if not fecha_str:
        flash('⚠️ Debe indicar una fecha.', 'warning')
        return redirect(url_for('cierre.vista_cierre'))

    try:
        fecha_cierre = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        flash('⚠️ Fecha inválida.', 'warning')
        return redirect(url_for('cierre.vista_cierre'))

    ya_cerrado = CierreCaja.query.filter_by(fecha=fecha_cierre).first()
    if ya_cerrado:
        flash(f'⚠️ Ya existe un cierre para {fecha_cierre}.', 'warning')
        return redirect(url_for('cierre.vista_cierre'))

    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = float(tasa_obj.valor) if tasa_obj else 1.0

    ventas_dia = Venta.query.filter(func.date(Venta.fecha) == fecha_cierre).all()
    r = _calcular_resumen(ventas_dia, fecha_cierre)

    abonos_dia = HistorialPago.query.filter(func.date(HistorialPago.fecha) == fecha_cierre).all()

    lista_ventas = []
    for v in ventas_dia:
        lista_ventas.append({
            'id': v.id,
            'hora': v.fecha.strftime('%I:%M %p'),
            'cliente': v.nombre_cliente_final,
            'total_usd': float(v.total_usd or 0),
            'efectivo_usd': float(v.pago_efectivo_usd or 0),
            'efectivo_bs': float(v.pago_efectivo_bs or 0),
            'pago_movil': float(v.pago_movil_bs or 0),
            'debito': float(v.pago_transferencia_bs or 0),
            'biopago': float(v.biopago_bdv or 0),
            'fiado': v.es_fiado,
            'saldo_pendiente': float(v.saldo_pendiente_usd or 0),
            'productos': [{'nombre': d.producto.nombre, 'cantidad': float(d.cantidad), 'precio': float(d.precio_unitario_usd)} for d in v.detalles]
        })

    for a in abonos_dia:
        if a.metodo_pago == 'ABONO INICIAL':
            continue

        lista_ventas.append({
            'id': f"ABONO-{a.id}",
            'hora': a.fecha.strftime('%I:%M %p'),
            'cliente': f"ABONO: {a.cliente.nombre if a.cliente else 'S/N'}",
            'total_usd': float(a.monto_usd or 0),
            'efectivo_usd': float(a.monto_usd if a.metodo_pago == 'EFECTIVO_USD' else 0),
            'efectivo_bs': float(a.monto_bs if a.metodo_pago == 'EFECTIVO_BS' else 0),
            'pago_movil': float(a.monto_bs if a.metodo_pago == 'PAGO_MOVIL' else 0),
            'debito': float(a.monto_bs if a.metodo_pago == 'DEBITO' else 0),
            'biopago': float(a.monto_bs if a.metodo_pago == 'BIOPAGO' else 0),
            'fiado': False, 'saldo_pendiente': 0,
            'productos': [{'nombre': 'ABONO DE DEUDA', 'cantidad': 1, 'precio': float(a.monto_usd or 0)}]
        })

    compras_dia = Compra.query.filter(func.date(Compra.fecha) == fecha_cierre).all()
    total_compras = sum(float(c.total_usd or 0) for c in compras_dia)
    lista_compras = []
    for c in compras_dia:
        lista_compras.append({
            'id': c.id,
            'proveedor': c.proveedor.nombre if c.proveedor else 'Desconocido',
            'total_usd': float(c.total_usd or 0),
            'productos': [{'nombre': d.producto.nombre, 'cantidad': float(d.cantidad), 'costo': float(d.costo_unitario)} for d in c.detalles]
        })

    nuevo_cierre = CierreCaja(
        fecha=fecha_cierre,
        monto_bs=r['efectivo_bs'],
        monto_usd=r['efectivo_usd'],
        pago_movil=r['pago_movil'],
        transferencia=r['debito'],
        biopago=r['biopago'],
        tasa_cierre=tasa,
        total_ventas_usd=r['total_general'],
        total_compras_usd=total_compras,
        fiado_dia_usd=r['fiado_nuevo'],
        detalle_ventas=json.dumps(lista_ventas),
        detalle_compras=json.dumps(lista_compras)
    )
    db.session.add(nuevo_cierre)

    # --- PARCHE DE SEGURIDAD RETROACTIVO ---
    """
    entradas = [
        ('Caja USD', 'INGRESO', 'Ventas Efectivo USD', r['efectivo_usd']),
        ('Caja Bs',  'INGRESO', 'Ventas Efectivo Bs',  r['efectivo_bs']),
        ('Banco',    'INGRESO', 'Ventas Pago Móvil',   r['pago_movil']),
        ('Banco',    'INGRESO', 'Ventas Débito',        r['debito']),
        ('Banco',    'INGRESO', 'Ventas Biopago BDV',   r['biopago']),
    ]
    for tipo_caja, tipo_mov, categoria, monto in entradas:
        if monto and float(monto) > 0:
            db.session.add(MovimientoCaja(
                tipo_caja=tipo_caja, tipo_movimiento=tipo_mov,
                categoria=categoria, monto=Decimal(str(monto)),
                tasa_dia=Decimal(str(tasa)),
                descripcion=f'Cierre retroactivo {fecha_cierre}',
                modulo_origen='CIERRE', user_id=current_user.id
            ))
    """

    db.session.commit()
    flash(f'✅ Cierre retroactivo del {fecha_cierre} guardado correctamente.', 'success')
    return redirect(url_for('cierre.vista_cierre'))
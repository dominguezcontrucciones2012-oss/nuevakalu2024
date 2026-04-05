from flask import Blueprint, render_template, redirect, url_for, flash
from models import db, Venta, TasaBCV, CierreCaja, Asiento
from datetime import datetime
from decimal import Decimal
from sqlalchemy import func

cierre_bp = Blueprint('cierre', __name__)

def _get_ventas_hoy(hoy_date):
    fecha_str = hoy_date.strftime('%Y-%m-%d')
    return Venta.query.filter(func.date(Venta.fecha) == fecha_str).all()

def _calcular_resumen(ventas, hoy_date=None):
    r = {
        'efectivo_usd': 0.0, 'efectivo_bs': 0.0, 'pago_movil': 0.0,
        'debito': 0.0, 'biopago': 0.0,
        'cobro_queso': 0.0, 'abonos_productores': 0.0,
        'fiado_nuevo': 0.0, 'total_general': 0.0, 'conteo': len(ventas),
        'fiado_productores': 0.0
    }

    # 1. VENTAS DEL DÍA (Fuente única de verdad)
    for v in ventas:
        r['total_general'] += float(v.total_usd or 0)
        r['efectivo_usd']  += float(v.pago_efectivo_usd or 0)
        r['efectivo_bs']   += float(v.pago_efectivo_bs or 0)
        r['pago_movil']    += float(v.pago_movil_bs or 0)
        r['debito']        += float(v.pago_transferencia_bs or 0)  # Tarjeta Débito
        r['biopago']       += float(v.biopago_bdv or 0)
        if v.es_fiado:
            r['fiado_nuevo'] += float(v.saldo_pendiente_usd or 0)

    # 2. COBRO DE QUESO (Solo rastreamos desde asientos contables, cuenta 1.1.02.02)
    if hoy_date:
        asientos_hoy = Asiento.query.filter(func.date(Asiento.fecha) == hoy_date).all()
        for asiento in asientos_hoy:
            for d in asiento.detalles:
                if d.cuenta.codigo == '1.1.02.02':
                    if d.haber_usd > 0:
                        r['cobro_queso'] += float(d.haber_usd)

    r['fiado']       = r['fiado_nuevo']
    r['fiado_total'] = r['fiado_nuevo'] + r['fiado_productores']
    r['transferencia'] = r['debito']  # Alias por si el template lo usa
    return r


@cierre_bp.route('/reporte_cierre')
def vista_cierre():
    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa     = float(tasa_obj.valor) if tasa_obj else 1.0
    hoy_date = datetime.now().date()

    ventas_hoy = _get_ventas_hoy(hoy_date)
    r          = _calcular_resumen(ventas_hoy, hoy_date)

    ya_cerrado        = CierreCaja.query.filter_by(fecha=hoy_date).first()
    cierres_historial = CierreCaja.query.order_by(CierreCaja.fecha.desc()).limit(10).all()

    return render_template('cierre_diario.html',
                           r=r,
                           ventas_hoy=ventas_hoy,
                           fecha=hoy_date,
                           tasa=tasa,
                           ya_cerrado=ya_cerrado,
                           cierres_historial=cierres_historial)


@cierre_bp.route('/cierre/ejecutar', methods=['POST'])
def ejecutar_cierre():
    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa     = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')
    hoy_date = datetime.now().date()

    ventas_hoy = _get_ventas_hoy(hoy_date)
    r          = _calcular_resumen(ventas_hoy, hoy_date)

    nuevo_cierre = CierreCaja(
        fecha=hoy_date,
        monto_usd=Decimal(str(r['efectivo_usd'])),
        monto_bs=Decimal(str(r['efectivo_bs'])),
        pago_movil=Decimal(str(r['pago_movil'])),
        transferencia=Decimal(str(r['debito'])),
        biopago=Decimal(str(r['biopago'])),
        tasa_cierre=tasa
    )

    db.session.add(nuevo_cierre)
    db.session.commit()

    flash('✅ Caja cerrada y asientos contables generados', 'success')
    return redirect(url_for('cierre.vista_cierre'))
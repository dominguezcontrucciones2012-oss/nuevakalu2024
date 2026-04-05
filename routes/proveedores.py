from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from decimal import Decimal
from datetime import datetime
from models import db, Proveedor, CuentaPorPagar, AbonoCuentaPorPagar, MovimientoCaja, TasaBCV

proveedores_bp = Blueprint('proveedores', __name__)

# ========== LISTA DE PROVEEDORES ==========
@proveedores_bp.route('/proveedores')
def lista_proveedores():
    todos = Proveedor.query.all()
    return render_template('proveedores.html', proveedores=todos)

# ========== GUARDAR PROVEEDOR ==========
@proveedores_bp.route('/guardar_proveedor', methods=['POST'])
def guardar_proveedor():
    try:
        nombre = request.form.get('nombre')
        rif = request.form.get('rif')
        
        if not nombre or not rif:
            flash("Nombre y RIF son obligatorios", "danger")
            return redirect(url_for('proveedores.lista_proveedores'))
            
        nuevo = Proveedor(
            nombre=nombre,
            rif=rif,
            telefono=request.form.get('telefono'),
            direccion=request.form.get('direccion'),
            vendedor_nombre=request.form.get('vendedor_nombre'),
            vendedor_telefono=request.form.get('vendedor_telefono'),
            es_productor=True if request.form.get('es_productor') else False
        )
        db.session.add(nuevo)
        db.session.commit()
        flash("✅ Proveedor guardado con éxito", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al guardar: {str(e)}", "danger")
    return redirect(url_for('proveedores.lista_proveedores'))

# ========== EDITAR PROVEEDOR ==========
@proveedores_bp.route('/editar_proveedor/<int:id>', methods=['POST'])
def editar_proveedor(id):
    try:
        prov = Proveedor.query.get_or_404(id)
        prov.rif               = request.form.get('rif')
        prov.nombre            = request.form.get('nombre')
        prov.telefono          = request.form.get('telefono')
        prov.direccion         = request.form.get('direccion')
        prov.vendedor_nombre   = request.form.get('vendedor_nombre')
        prov.vendedor_telefono = request.form.get('vendedor_telefono')
        prov.es_productor      = True if request.form.get('es_productor') else False
        db.session.commit()
        flash("✅ Proveedor actualizado con éxito", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al editar: {str(e)}", "danger")
    return redirect(url_for('proveedores.lista_proveedores'))

# ========== ELIMINAR PROVEEDOR ==========
@proveedores_bp.route('/eliminar_proveedor/<int:id>', methods=['POST'])
def eliminar_proveedor(id):
    try:
        prov = Proveedor.query.get_or_404(id)
        db.session.delete(prov)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# ========== CUENTAS POR PAGAR (A QUIÉN LE DEBES) ==========
@proveedores_bp.route('/cuentas_por_pagar')
def lista_cuentas_por_pagar():
    cuentas = CuentaPorPagar.query.filter(
        CuentaPorPagar.saldo_pendiente_usd > 0
    ).order_by(CuentaPorPagar.fecha.desc()).all()
    total = sum(c.saldo_pendiente_usd for c in cuentas) if cuentas else 0
    return render_template('cuentas_por_pagar.html', cuentas=cuentas, total=total)

# ========== REGISTRAR PAGO A PROVEEDOR (CONECTADO A CAJA) ==========
@proveedores_bp.route('/pagar_factura/<int:id>', methods=['POST'])
def pagar_factura(id):
    try:
        cuenta = CuentaPorPagar.query.get_or_404(id)
        monto_pago_usd = Decimal(str(request.form.get('monto_usd', '0')))
        metodo         = request.form.get('metodo_pago', 'EFECTIVO_USD')
        referencia     = request.form.get('referencia', '')

        if monto_pago_usd <= 0:
            flash("⚠️ El monto debe ser mayor a 0", "danger")
            return redirect(url_for('proveedores.lista_cuentas_por_pagar'))

        if monto_pago_usd > cuenta.saldo_pendiente_usd:
            flash("⚠️ El monto no puede ser mayor al saldo pendiente", "danger")
            return redirect(url_for('proveedores.lista_cuentas_por_pagar'))

        # 1. Registrar el abono en la cuenta del proveedor
        nuevo_abono = AbonoCuentaPorPagar(
            cuenta_id  = cuenta.id,
            fecha      = datetime.now(),
            monto_usd  = monto_pago_usd,
            metodo_pago= metodo,
            referencia = referencia,
            descripcion= f"Pago a {cuenta.proveedor.nombre} | Factura {cuenta.numero_factura}"
        )
        db.session.add(nuevo_abono)

        # 2. Actualizar saldos de la factura
        cuenta.monto_abonado_usd   = (cuenta.monto_abonado_usd or Decimal('0.00')) + monto_pago_usd
        cuenta.saldo_pendiente_usd = (cuenta.saldo_pendiente_usd or Decimal('0.00')) - monto_pago_usd

        if cuenta.saldo_pendiente_usd <= 0:
            cuenta.saldo_pendiente_usd = Decimal('0.00')
            cuenta.estatus = 'Pagada'

        # 3. DESCONTAR DE MOVIMIENTOCAJA AUTOMÁTICAMENTE
        tasa_obj = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
        tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.00')

        # Mapeo de métodos a cajas
        if metodo == 'EFECTIVO_USD':
            tipo_caja = 'Caja USD'
            monto_caja = monto_pago_usd
        elif metodo == 'EFECTIVO_BS':
            tipo_caja = 'Caja Bs'
            monto_caja = monto_pago_usd * tasa
        else: # PAGO_MOVIL, BIOPAGO, TARJETA
            tipo_caja = 'Banco'
            monto_caja = monto_pago_usd * tasa

        # Registrar el egreso en la caja
        nuevo_egreso = MovimientoCaja(
            fecha           = datetime.now(),
            tipo_movimiento = 'EGRESO',
            tipo_caja       = tipo_caja,
            categoria       = 'Pago Proveedor',
            monto           = monto_caja,
            tasa_dia        = tasa,
            descripcion     = f"Pago Factura #{cuenta.numero_factura} - {cuenta.proveedor.nombre} ({metodo})",
            modulo_origen   = 'Proveedores',
            referencia_id   = cuenta.id
        )
        db.session.add(nuevo_egreso)

        # UN SOLO COMMIT PARA TODO
        db.session.commit()
        flash(f"✅ Pago de ${monto_pago_usd} registrado y descontado de {tipo_caja}", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error crítico al procesar pago: {str(e)}", "danger")
        
    return redirect(url_for('proveedores.lista_cuentas_por_pagar'))

# ========== HISTORIAL DE PAGOS A PROVEEDORES ==========
@proveedores_bp.route('/historial_pagos_proveedores')
def historial_pagos_proveedores():
    pagos = AbonoCuentaPorPagar.query.order_by(
        AbonoCuentaPorPagar.fecha.desc()
    ).all()
    return render_template('historial_pagos_proveedores.html', pagos=pagos)
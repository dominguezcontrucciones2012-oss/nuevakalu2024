from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from models import db, Producto, Cliente, Venta, DetalleVenta, TasaBCV, HistorialPago, Proveedor, MovimientoProductor, MovimientoCaja, Pedido, DetallePedido, PagoReportado
from flask_login import login_required, current_user
from routes.decorators import staff_required
from decimal import Decimal
from datetime import datetime
from routes.contabilidad import registrar_asiento
from models import CierreCaja, AuditoriaInventario

pos_bp = Blueprint('pos', __name__)

# 🔒 CANDADO ANTI-DUPLICADO - Set global para tokens usados
_tokens_usados = set()  # ← AQUÍ, como variable global del módulo

from flask_login import login_required

@pos_bp.route('/pos')
@login_required
@staff_required
def pos():
    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    if tasa_obj:
        tasa_valor = tasa_obj.valor
        fecha_sistema = tasa_obj.fecha if hasattr(tasa_obj, 'fecha') else datetime.now().strftime('%Y-%m-%d')
    else:
        tasa_valor = Decimal('1.0')
        fecha_sistema = datetime.now().strftime('%Y-%m-%d')

    productos = Producto.query.all()
    clientes = Cliente.query.all()
    productores = Proveedor.query.filter_by(es_productor=True).order_by(Proveedor.nombre).all()
    return render_template('pos.html', productos=productos, clientes=clientes,
                           productores=productores, tasa=tasa_valor, fecha=fecha_sistema)

@pos_bp.route('/buscar_producto/<codigo>')
def buscar_producto(codigo):
    prod = Producto.query.filter(
        (Producto.codigo == codigo) |
        (Producto.nombre.ilike(f'%{codigo}%'))
    ).first()
    if prod:
        return jsonify({
            'success': True,
            'id': prod.id,
            'codigo': prod.codigo,
            'nombre': prod.nombre,
            'precio': float(prod.precio_normal_usd),
            'precio_normal': float(prod.precio_normal_usd),
            'precio_oferta': float(prod.precio_oferta_usd),
            'stock': prod.stock
        })
    return jsonify({'success': False, 'message': 'Producto no encontrado'})


# ==========================================================
#   BUSCAR CLIENTE O PRODUCTOR (busca en ambas tablas)
# ==========================================================
@pos_bp.route('/buscar_cliente/<cedula>')
def buscar_cliente(cedula):
    cedula = cedula.strip().upper()

    cliente = Cliente.query.filter(
        (Cliente.cedula == cedula) |
        (Cliente.nombre.ilike(f'%{cedula}%'))
    ).first()

    if cliente:
        return jsonify({
            'encontrado': True,
            'tipo': 'cliente',
            'id': cliente.id,
            'nombre': cliente.nombre,
            'cedula': cliente.cedula,
            'telefono': cliente.telefono or 'N/A',
            'saldo_usd': float(cliente.saldo_usd or 0),
            'puntos': cliente.puntos or 0
        })

    productor = Proveedor.query.filter(
        Proveedor.es_productor == True
    ).filter(
        (Proveedor.rif == cedula) |
        (Proveedor.nombre.ilike(f'%{cedula}%'))
    ).first()

    if productor:
        return jsonify({
            'encontrado': True,
            'tipo': 'productor',
            'id': productor.id,
            'nombre': productor.nombre,
            'cedula': productor.rif,
            'saldo_usd': float(productor.saldo_pendiente_usd or 0),
            'puntos': 0
        })

    return jsonify({'encontrado': False})

@pos_bp.route('/procesar_venta', methods=['POST'])
@login_required
@staff_required
def procesar_venta():
    data = request.get_json()

    # 🔒 CANDADO ANTI-DUPLICADO
    global _tokens_usados
    token = data.get('transaction_token')
    if token:
        if token in _tokens_usados:
            return jsonify({'success': False, 'message': '⚠️ Esta venta ya fue procesada.'})
        _tokens_usados.add(token)
        if len(_tokens_usados) > 500:
            _tokens_usados.clear()
    def seguro_decimal(valor):
        if valor is None or str(valor).strip() == "" or str(valor).lower() == "none":
            return Decimal('0.00')
        try:
            return Decimal(str(valor).replace(',', '.'))
        except:
            return Decimal('0.00')

    try:
        if not data.get('items') or len(data['items']) == 0:
            return jsonify({'success': False, 'message': 'El carrito está vacío'})

        total_venta  = seguro_decimal(data.get('total_usd'))
        tasa         = seguro_decimal(data.get('tasa'))
        if tasa <= Decimal('0'): tasa = Decimal('1.0')

        p_usd = seguro_decimal(data.get('pago_efectivo_usd'))
        p_bs  = seguro_decimal(data.get('pago_efectivo_bs'))
        p_pm  = seguro_decimal(data.get('pago_movil_bs'))
        p_tr  = seguro_decimal(data.get('pago_transferencia_bs'))
        p_bio = seguro_decimal(data.get('biopago_bdv'))
        # ... el resto de tu código igual desde aquí
        bs_total     = p_bs + p_pm + p_tr + p_bio
        total_pagado = p_usd + (bs_total / tasa)

        falta_usd = total_venta - total_pagado

        vuelto_usd = Decimal('0.00')
        vuelto_bs  = Decimal('0.00')

        if falta_usd < Decimal('0.00'):
            vuelto_usd = abs(falta_usd)
            vuelto_bs  = vuelto_usd * tasa
            falta_usd  = Decimal('0.00')

            exceso_usd = vuelto_usd

            if exceso_usd > 0 and p_bs > 0:
                p_bs_usd = p_bs / tasa
                if p_bs_usd >= exceso_usd:
                    p_bs = (p_bs_usd - exceso_usd) * tasa
                    exceso_usd = Decimal('0.00')
                else:
                    exceso_usd -= p_bs_usd
                    p_bs = Decimal('0.00')

            if exceso_usd > 0 and p_usd > 0:
                if p_usd >= exceso_usd:
                    p_usd -= exceso_usd
                    exceso_usd = Decimal('0.00')
                else:
                    exceso_usd -= p_usd
                    p_usd = Decimal('0.00')

            if exceso_usd > 0 and p_pm > 0:
                p_pm_usd = p_pm / tasa
                if p_pm_usd >= exceso_usd:
                    p_pm = (p_pm_usd - exceso_usd) * tasa
                    exceso_usd = Decimal('0.00')
                else:
                    exceso_usd -= p_pm_usd
                    p_pm = Decimal('0.00')

            if exceso_usd > 0 and p_tr > 0:
                p_tr_usd = p_tr / tasa
                if p_tr_usd >= exceso_usd:
                    p_tr = (p_tr_usd - exceso_usd) * tasa
                    exceso_usd = Decimal('0.00')
                else:
                    exceso_usd -= p_tr_usd
                    p_tr = Decimal('0.00')

            if exceso_usd > 0 and p_bio > 0:
                p_bio_usd = p_bio / tasa
                if p_bio_usd >= exceso_usd:
                    p_bio = (p_bio_usd - exceso_usd) * tasa
                    exceso_usd = Decimal('0.00')
                else:
                    exceso_usd -= p_bio_usd
                    p_bio = Decimal('0.00')

        elif falta_usd < Decimal('0.01'):
            falta_usd = Decimal('0.00')

        pedido_id    = data.get('pedido_id')
        cliente_id   = data.get('cliente_id')
        cliente_tipo = data.get('cliente_tipo', 'cliente')
        es_productor = False
        productor    = None
        cliente      = None

        # SOLO busca en proveedores si el frontend dice explícitamente que es productor
        if cliente_id and cliente_tipo == 'productor':
            productor = Proveedor.query.get(int(cliente_id))
            if productor:
                es_productor = True

        # SOLO busca en clientes si el frontend dice que es cliente
        elif cliente_id and cliente_tipo == 'cliente':
            cliente = Cliente.query.get(int(cliente_id))

        # 🔒 CANDADO: Fiado sin cliente real = BLOQUEADO
        es_fiado = falta_usd > Decimal('0.00')
        if es_fiado and not es_productor and not cliente:
            return jsonify({'success': False, 'message': f'⚠️ Faltan ${falta_usd:.2f}. Seleccione un cliente válido.'})

        # 🔒 Si es productor, la venta NO se vincula a ningún cliente
        id_final_historial = None if es_productor else (cliente.id if cliente else None)

        nueva_venta = Venta(
            cliente_id=id_final_historial,
            total_usd=total_venta,
            tasa_momento=tasa,
            es_fiado=es_fiado,
            pagada=(not es_fiado),
            pago_efectivo_usd=p_usd,
            pago_efectivo_bs=p_bs,
            pago_movil_bs=p_pm,
            pago_transferencia_bs=p_tr,
            biopago_bdv=p_bio,
            saldo_pendiente_usd=falta_usd
        )
        db.session.add(nueva_venta)
        db.session.flush()

        if es_productor and productor:
            if falta_usd > Decimal('0.00'):
                nuevo_saldo = productor.saldo_pendiente_usd - falta_usd
                mov_pos = MovimientoProductor(
                    proveedor_id=productor.id,
                    tipo='COMPRA_POS',
                    descripcion=f'Compra POS #{nueva_venta.id} | Cash: ${total_pagado:.2f} | Libreta: ${falta_usd:.2f}',
                    monto_usd=total_venta,
                    debe=falta_usd,
                    saldo_momento=nuevo_saldo,
                    anio=datetime.utcnow().year,
                    semana_del_anio=datetime.utcnow().isocalendar()[1]
                )
                productor.saldo_pendiente_usd = nuevo_saldo
                db.session.add(mov_pos)
            else:
                mov_pos = MovimientoProductor(
                    proveedor_id=productor.id,
                    tipo='COMPRA_POS',
                    descripcion=f'Compra POS #{nueva_venta.id} | Pagado completo en efectivo/móvil',
                    monto_usd=total_venta,
                    debe=Decimal('0.00'),
                    saldo_momento=productor.saldo_pendiente_usd,
                    anio=datetime.utcnow().year,
                    semana_del_anio=datetime.utcnow().isocalendar()[1]
                )
                db.session.add(mov_pos)

        total_costo_usd = Decimal('0.00')
        for item in data['items']:
            prod = Producto.query.get(item['id'])
            if not prod: continue
            cantidad = Decimal(str(item.get('cantidad') or 0))
            if Decimal(str(prod.stock)) < cantidad:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'No hay stock de {prod.nombre}'})
            total_costo_usd += (prod.costo_usd or Decimal('0.00')) * cantidad
            # ✅ CORRECCIÓN: Mantener Decimal para precisión total en kilos/bolsas
            prod.stock = Decimal(str(prod.stock)) - cantidad
            db.session.add(DetalleVenta(
                venta_id=nueva_venta.id,
                producto_id=prod.id,
                cantidad=float(cantidad),
                precio_unitario_usd=Decimal(str(item.get('precio', 0)))
            ))

        premio_club     = False
        puntos_sobrantes = 0
       # 🔒 Solo procesar puntos/fiado si es un CLIENTE real (no productor)
        if not es_productor and cliente:
                if es_fiado:
                    cliente.saldo_usd = (cliente.saldo_usd or Decimal('0.00')) + falta_usd
                    # Sincronizar saldo BS
                    cliente.saldo_bs = (cliente.saldo_usd * tasa).quantize(Decimal('0.01'))

                    if total_pagado > Decimal('0.00'):
                        db.session.add(HistorialPago(
                            cliente_id=cliente.id, venta_id=nueva_venta.id,
                            monto_usd=total_pagado, monto_bs=bs_total,
                            tasa_dia=tasa, metodo_pago='ABONO INICIAL'
                        ))
                if not es_fiado and total_venta > Decimal('2.00'):
                    puntos_ganados = int(total_venta)
                    cliente.puntos = (cliente.puntos or 0) + puntos_ganados
                    if cliente.puntos >= 200:
                        premios_ganados  = cliente.puntos // 200
                        puntos_sobrantes = cliente.puntos % 200
                        cliente.puntos   = puntos_sobrantes
                        premio_club      = premios_ganados
        # ============================================================
        #   ASIENTOS CONTABLES
        # ============================================================
        try:
            t_bs         = float(total_venta) * float(tasa)
            movimientos  = []
            cuenta_deuda = '1.1.02.02' if es_productor else '1.1.02.01'

            if es_fiado:
                # ENTRADAS (DEBE)
                if p_usd > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.01', 'debe_usd': float(p_usd), 'haber_usd': 0, 'debe_bs': 0,           'haber_bs': 0})
                if p_bs > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.02', 'debe_usd': 0,            'haber_usd': 0, 'debe_bs': float(p_bs),  'haber_bs': 0})
                if p_pm > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.03', 'debe_usd': 0,            'haber_usd': 0, 'debe_bs': float(p_pm),  'haber_bs': 0})
                if p_bio > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.04', 'debe_usd': 0,            'haber_usd': 0, 'debe_bs': float(p_bio), 'haber_bs': 0})
                if p_tr > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.05', 'debe_usd': 0,            'haber_usd': 0, 'debe_bs': float(p_tr),  'haber_bs': 0})
                # DEUDA FIADO
                if falta_usd > 0:
                    movimientos.append({'cuenta_codigo': cuenta_deuda,  'debe_usd': float(falta_usd), 'haber_usd': 0, 'debe_bs': float(falta_usd) * float(tasa), 'haber_bs': 0})
                # INGRESO VENTA FIADO (HABER)
                movimientos.append({'cuenta_codigo': '4.1.02', 'debe_usd': 0, 'haber_usd': float(total_venta), 'debe_bs': 0, 'haber_bs': t_bs})

            else:
                # ENTRADAS (DEBE)
                if p_usd > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.01', 'debe_usd': float(p_usd), 'haber_usd': 0, 'debe_bs': 0,           'haber_bs': 0})
                if p_bs > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.02', 'debe_usd': 0,            'haber_usd': 0, 'debe_bs': float(p_bs),  'haber_bs': 0})
                if p_pm > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.03', 'debe_usd': 0,            'haber_usd': 0, 'debe_bs': float(p_pm),  'haber_bs': 0})
                if p_bio > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.04', 'debe_usd': 0,            'haber_usd': 0, 'debe_bs': float(p_bio), 'haber_bs': 0})
                if p_tr > 0:
                    movimientos.append({'cuenta_codigo': '1.1.01.05', 'debe_usd': 0,            'haber_usd': 0, 'debe_bs': float(p_tr),  'haber_bs': 0})
                # INGRESO VENTA CONTADO (HABER)
                movimientos.append({'cuenta_codigo': '4.1.01', 'debe_usd': 0, 'haber_usd': float(total_venta), 'debe_bs': 0, 'haber_bs': t_bs})

            # COSTO DE VENTAS
            if total_costo_usd > Decimal('0.00'):
                costo_bs = float(total_costo_usd) * float(tasa)
                movimientos.append({'cuenta_codigo': '5.1.01',    'debe_usd': float(total_costo_usd), 'haber_usd': 0,                    'debe_bs': costo_bs, 'haber_bs': 0})
                movimientos.append({'cuenta_codigo': '1.1.03.01', 'debe_usd': 0,                     'haber_usd': float(total_costo_usd), 'debe_bs': 0,        'haber_bs': costo_bs})

            registrar_asiento(
                descripcion=f"Venta #{nueva_venta.id} - {'PRODUCTOR' if es_productor else 'CLIENTE'} {'FIADO' if es_fiado else 'CONTADO'}",
                tasa=float(tasa),
                referencia_tipo='VENTA',
                referencia_id=nueva_venta.id,
                movimientos=movimientos
            )
        except Exception as cont_err:
            print(f"⚠️ Contabilidad falló: {cont_err}")

        # ============================================================
        #   MOVIMIENTOS DE CAJA
        # ============================================================
        try:
            if p_usd > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Caja USD',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_usd, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Efectivo USD',
                    modulo_origen='Venta', referencia_id=nueva_venta.id
                ))
            if p_bs > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Caja Bs',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_bs, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Efectivo Bs',
                    modulo_origen='Venta', referencia_id=nueva_venta.id
                ))
            if p_pm > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_pm, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Pago Móvil',
                    modulo_origen='Venta', referencia_id=nueva_venta.id
                ))
            if p_tr > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_tr, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Tarjeta Débito',
                    modulo_origen='Venta', referencia_id=nueva_venta.id
                ))
            if p_bio > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_bio, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Biopago',
                    modulo_origen='Venta', referencia_id=nueva_venta.id
                ))
        except Exception as caja_err:
            print(f"⚠️ Caja falló: {caja_err}")

        # ✅ Si la venta viene de un pedido, lo marcamos como LISTO
        if pedido_id:
            pedido_obj = Pedido.query.get(pedido_id)
            if pedido_obj:
                pedido_obj.estado = 'listo'
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Venta procesada exitosamente.',
            'venta_id': nueva_venta.id,
            'premio_club': premio_club,
            'premios_ganados': premio_club if premio_club else 0, # <--- AGREGAR
            'puntos_actuales': cliente.puntos if cliente else 0   # <--- AGREGAR
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# ============================================================
# 🛒 API DE PEDIDOS (PARA CARGAR DESDE EL PORTAL)
# ============================================================
@pos_bp.route('/api/pedidos/pendientes')
@login_required
@staff_required
def api_pedidos_pendientes():
    pedidos = Pedido.query.filter_by(estado='pendiente').all()
    res = []
    for p in pedidos:
        res.append({
            'id': p.id,
            'cliente': p.cliente.nombre,
            'fecha': p.fecha.strftime('%d/%m %H:%M'),
            'items_count': len(p.detalles)
        })
    return jsonify(res)

@pos_bp.route('/api/pedido/<int:id>')
@login_required
@staff_required
def api_get_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    items = []
    for d in pedido.detalles:
        precio_oferta = d.producto.precio_oferta_usd or Decimal('0.00')
        precio_normal = d.producto.precio_normal_usd or Decimal('0.00')
        items.append({
            'producto_id': d.producto_id,
            'nombre': d.producto.nombre,
            'precio': float(precio_oferta if precio_oferta > 0 else precio_normal),
            'cantidad': float(d.cantidad)
        })
    
    # Cambiar estado a "recibido" para que el cliente sepa que ya se está preparando
    pedido.estado = 'recibido'
    db.session.commit()

    return jsonify({
        'success': True,
        'cliente': {
            'id': pedido.cliente.id,
            'nombre': pedido.cliente.nombre,
            'cedula': pedido.cliente.cedula
        },
        'items': items
    })

@pos_bp.route('/api/pagos_reportados/pendientes')
@login_required
@staff_required
def api_pagos_reportados_pendientes():
    pagos = PagoReportado.query.filter_by(estado='pendiente').all()
    res = []
    for p in pagos:
        res.append({
            'id': p.id,
            'cliente': p.cliente.nombre if p.cliente else 'N/A',
            'monto_usd': float(p.monto_usd),
            'monto_bs': float(p.monto_bs),
            'metodo_pago': p.metodo_pago,
            'referencia': p.referencia,
            'fecha_reporte': p.fecha_reporte.strftime('%d/%m %H:%M')
        })
    return jsonify(res)



@pos_bp.route('/canjear_documento/<int:cliente_id>', methods=['POST'])
@login_required
@staff_required
def canjear_documento(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.documentos = 0
    db.session.commit()
    return jsonify({'success': True, 'message': f'Premio entregado a {cliente.nombre}'})


@pos_bp.route('/ticket/<int:venta_id>')
@login_required
def ticket(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    cajero = current_user.username if current_user.is_authenticated else "SISTEMA"
    
    es_primera_compra = False
    if venta.cliente_id:
        count = Venta.query.filter_by(cliente_id=venta.cliente_id).count()
        if count == 1:
            es_primera_compra = True

    return render_template('ticket.html', venta=venta, cajero=cajero, es_primera_compra=es_primera_compra)




@pos_bp.route('/historial_ventas')
def historial_ventas():
    ventas = Venta.query.order_by(Venta.id.desc()).limit(300).all()
    return render_template('historial_ventas.html', ventas=ventas)


@pos_bp.route('/historial_ventas/<int:venta_id>')
def detalle_venta(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    tasa = venta.tasa_momento or Decimal('1.0')
    return render_template('detalle_venta.html', venta=venta, tasa=tasa)

@pos_bp.route('/detalle_venta/<int:venta_id>/json')
def detalle_venta_json(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    resultado = []
    for d in venta.detalles:
        prod = Producto.query.get(d.producto_id)
        resultado.append({
            'nombre': prod.nombre if prod else f'Producto #{d.producto_id}',
            'cantidad': float(d.cantidad or 0),
            'precio_unitario': float(d.precio_unitario_usd or 0)
        })
    return jsonify(resultado)


@pos_bp.route('/anular_venta/<int:id>', methods=['POST'])
@login_required
@staff_required
def anular_venta(id):
    try:
        venta = Venta.query.get_or_404(id)
        if getattr(venta, 'pagada', False) is False:
            return jsonify({'success': False, 'message': '⚠️ Esta venta ya parece no estar vigente.'}), 400

        for detalle in getattr(venta, 'detalles', []):
            prod = Producto.query.get(detalle.producto_id)
            if prod:
                antes = prod.stock or Decimal('0.000')
                prod.stock = antes + (detalle.cantidad or Decimal('0.000'))
                try:
                    audit = AuditoriaInventario(
                        usuario_id=getattr(current_user, 'id', None) or 0,
                        usuario_nombre=getattr(current_user, 'username', 'system'),
                        producto_id=prod.id,
                        producto_nombre=prod.nombre,
                        accion='ANULACION_VENTA_REINGRESO',
                        cantidad_antes=antes,
                        cantidad_despues=prod.stock,
                        fecha=datetime.now()
                    )
                    db.session.add(audit)
                except Exception:
                    pass

        try:
            monto_usd = Decimal(venta.pago_efectivo_usd or 0)
            if monto_usd > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Caja USD',
                    tipo_movimiento='Salida', categoria='Anulación Venta',
                    monto=monto_usd, tasa_dia=getattr(venta, 'tasa_momento', Decimal('1.00')),
                    descripcion=f'Anulación venta #{venta.id} - Efectivo USD',
                    modulo_origen='Venta', referencia_id=venta.id
                ))
            monto_bs = Decimal(venta.pago_efectivo_bs or 0)
            if monto_bs > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Caja Bs',
                    tipo_movimiento='Salida', categoria='Anulación Venta',
                    monto=monto_bs, tasa_dia=getattr(venta, 'tasa_momento', Decimal('1.00')),
                    descripcion=f'Anulación venta #{venta.id} - Efectivo Bs',
                    modulo_origen='Venta', referencia_id=venta.id
                ))
            monto_banco = (Decimal(venta.pago_movil_bs or 0) +
                           Decimal(venta.pago_transferencia_bs or 0) +
                           Decimal(venta.biopago_bdv or 0))
            if monto_banco > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='Salida', categoria='Anulación Venta',
                    monto=monto_banco, tasa_dia=getattr(venta, 'tasa_momento', Decimal('1.00')),
                    descripcion=f'Anulación venta #{venta.id} - Banco/PagoMovil/TarjetaDebito/Biopago',
                    modulo_origen='Venta', referencia_id=venta.id
                ))
        except Exception:
            pass

        venta.pagada = False
        # Si era productor, devolvemos el saldo a su libreta
        if venta.cliente_id is None and (venta.total_usd or 0) > 0:
            # Buscamos si hubo movimiento de productor asociado
            v_prod = MovimientoProductor.query.filter(
                 MovimientoProductor.tipo == 'COMPRA_POS',
                 MovimientoProductor.descripcion.like(f'%#{venta.id}%')
            ).first()
            if v_prod and v_prod.proveedor:
                 v_prod.proveedor.saldo_pendiente_usd += (venta.saldo_pendiente_usd or 0)
        
        # Si era un cliente fiado, restamos la deuda de su balance general
        elif venta.cliente_id and venta.es_fiado:
            cliente_afectado = Cliente.query.get(venta.cliente_id)
            if cliente_afectado:
                deuda_a_restar = Decimal(str(venta.saldo_pendiente_usd or 0))
                cliente_afectado.saldo_usd -= deuda_a_restar
                
                # Sincronizar saldo BS
                tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
                tasa_act = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')
                cliente_afectado.saldo_bs = (cliente_afectado.saldo_usd * tasa_act).quantize(Decimal('0.01'))

        venta.saldo_pendiente_usd = Decimal(venta.total_usd or 0)

        # 🌟 CLUB DEL VECINO: Descontar puntos si la venta era contado
        if venta.cliente_id and not venta.es_fiado and venta.total_usd:
            cliente_anulado = Cliente.query.get(venta.cliente_id)
            if cliente_anulado:
                puntos_a_quitar = int(Decimal(venta.total_usd))
                cliente_anulado.puntos = max(0, (cliente_anulado.puntos or 0) - puntos_a_quitar)

        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Venta anulada exitosamente.'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
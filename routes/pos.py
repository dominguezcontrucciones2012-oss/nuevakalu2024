from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from models import db, User, Producto, Cliente, Venta, DetalleVenta, TasaBCV, HistorialPago, Proveedor, MovimientoProductor, MovimientoCaja, Pedido, DetallePedido, PagoReportado, VentaPausada, DetalleVentaPausada

from flask_login import login_required, current_user
from routes.decorators import staff_required
from decimal import Decimal
from datetime import datetime
from utils import seguro_decimal
from routes.contabilidad import registrar_asiento
from models import CierreCaja, AuditoriaInventario

import logging

pos_bp = Blueprint('pos', __name__)
logger = logging.getLogger('KALU.pos')

# 🔒 CANDADO ANTI-DUPLICADO - Set global para tokens usados
_tokens_usados = set()  # ← AQUÍ, como variable global del módulo

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
    productores = Proveedor.query.filter((Proveedor.es_productor == True) | (Proveedor.es_obrero == True)).order_by(Proveedor.nombre).all()
    return render_template('pos.html', productos=productos, clientes=clientes,
                           productores=productores, tasa=tasa_valor, fecha=fecha_sistema)

@pos_bp.route('/buscar_producto/<codigo>')
@login_required
@staff_required
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
            'precio': str(prod.precio_normal_usd),
            'precio_normal': str(prod.precio_normal_usd),
            'precio_oferta': str(prod.precio_oferta_usd),
            'stock': str(prod.stock)
        })
    return jsonify({'success': False, 'message': 'Producto no encontrado'})


# ==========================================================
#   BUSCAR CLIENTE O PRODUCTOR (busca en ambas tablas)
# ==========================================================
@pos_bp.route('/buscar_cliente/<cedula>')
@login_required
@staff_required
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
            'saldo_usd': str(cliente.saldo_usd or Decimal('0.00')),
            'puntos': cliente.puntos or 0
        })

    productor = Proveedor.query.filter(
        (Proveedor.es_productor == True) | (Proveedor.es_obrero == True)
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
            'saldo_usd': str(productor.saldo_pendiente_usd or Decimal('0.00')),
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
        p_deb = seguro_decimal(data.get('pago_debito_bs')) # 👈 NUEVO: Tarjeta de Débito
        p_bio = seguro_decimal(data.get('biopago_bdv'))
        
        bs_total     = p_bs + p_pm + p_tr + p_deb + p_bio
        total_pagado = p_usd + (bs_total / tasa)

        falta_usd = total_venta - total_pagado

        # 1.3 Lógica de vuelto y cobro real
        vuelto_usd = Decimal('0.00')
        vuelto_bs  = Decimal('0.00')

        if falta_usd < Decimal('0.00'):
            vuelto_usd = abs(falta_usd)
            vuelto_bs  = vuelto_usd * tasa
            falta_usd  = Decimal('0.00')

            # Ajustar montos para contabilidad (No reportar el vuelto como ingreso)
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
        elif falta_usd < Decimal('0.01'):
            falta_usd = Decimal('0.00')

        # 2. Identificación de Cliente / Productor
        pedido_id    = data.get('pedido_id')
        cliente_id   = data.get('cliente_id')
        cliente_tipo = data.get('cliente_tipo', 'cliente')
        es_productor = (cliente_tipo == 'productor')
        productor    = None
        cliente      = None

        if es_productor and cliente_id:
            productor = Proveedor.query.get(int(cliente_id))
        elif cliente_id:
            cliente = Cliente.query.get(int(cliente_id))

        # 3. Estado de Fiado y Deuda
        es_fiado_opcion = data.get('es_fiado', False)
        # Si el usuario mandó es_fiado=True, forzamos que falte algo (aunque sea 0 si pagó completo, pero es raro)
        # El problema anterior era que si pagaba completo, falta_usd era 0 y no se registraba deuda.
        # Si es_fiado es True, la deuda REAL es falta_usd.
        es_fiado = es_fiado_opcion or (falta_usd > Decimal('0.00'))
        
        if es_fiado and not es_productor and not cliente:
            return jsonify({'success': False, 'message': f'⚠️ Venta a crédito requiere seleccionar un cliente.'})

        # 4. Crear Objeto Venta
        nueva_venta = Venta(
            cliente_id=cliente.id if (cliente and not es_productor) else None,
            total_usd=total_venta,
            tasa_momento=tasa,
            es_fiado=es_fiado,
            pagada=(not es_fiado and falta_usd <= 0),
            pago_efectivo_usd=p_usd,
            pago_efectivo_bs=p_bs,
            pago_movil_bs=p_pm,
            pago_transferencia_bs=p_tr,
            biopago_bdv=p_bio,
            pago_debito_bs=p_deb,
            saldo_pendiente_usd=falta_usd,
            user_id=current_user.id
        )
        db.session.add(nueva_venta)
        db.session.flush()

        logger.info(f"💰 Venta #{nueva_venta.id}: Total=${total_venta:.2f} | Fiado={es_fiado} | Deuda=${falta_usd:.2f}")

        # 5. Manejo de Deuda Productor (Libreta)
        if es_productor and productor:
            nuevo_saldo = productor.saldo_pendiente_usd - falta_usd
            mov_pos = MovimientoProductor(
                proveedor_id=productor.id,
                tipo='COMPRA_POS',
                descripcion=f'Compra POS #{nueva_venta.id} | Deuda: ${falta_usd:.2f}',
                monto_usd=total_venta,
                debe=falta_usd,
                saldo_momento=nuevo_saldo,
                anio=datetime.utcnow().year,
                semana_del_anio=datetime.utcnow().isocalendar()[1]
            )
            productor.saldo_pendiente_usd = nuevo_saldo
            db.session.add(mov_pos)

        # 6. Procesar Items e Inventario
        total_costo_usd = Decimal('0.00')
        for item in data['items']:
            prod = Producto.query.get(item['id'])
            if not prod: continue
            cantidad = Decimal(str(item.get('cantidad') or 0))
            if Decimal(str(prod.stock)) < cantidad:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'Sin stock de {prod.nombre}'})
            
            total_costo_usd += (prod.costo_usd or Decimal('0.00')) * cantidad
            antes = Decimal(str(prod.stock))
            prod.stock = antes - cantidad
            
            db.session.add(AuditoriaInventario(
                usuario_id=current_user.id, producto_id=prod.id,
                producto_nombre=prod.nombre, accion='VENTA_POS',
                cantidad_antes=antes, cantidad_despues=prod.stock
            ))
            db.session.add(DetalleVenta(
                venta_id=nueva_venta.id, producto_id=prod.id,
                cantidad=cantidad, precio_unitario_usd=seguro_decimal(item.get('precio', 0))
            ))

        # 7. Fidelización y Saldo Cliente
        premio_club = False
        if cliente and not es_productor:
            if es_fiado:
                cliente.saldo_usd = (cliente.saldo_usd or Decimal('0.00')) + falta_usd
                cliente.saldo_bs = (cliente.saldo_usd * tasa).quantize(Decimal('0.01'))
                if total_pagado > 0:
                    db.session.add(HistorialPago(
                        cliente_id=cliente.id, venta_id=nueva_venta.id,
                        monto_usd=total_pagado, monto_bs=bs_total,
                        tasa_dia=tasa, metodo_pago='ABONO INICIAL',
                        user_id=current_user.id
                    ))
            elif total_venta > 2:
                cliente.puntos = (cliente.puntos or 0) + int(total_venta)
                if cliente.puntos >= 200:
                    premio_club = cliente.puntos // 200
                    cliente.puntos %= 200

        # 8. Contabilidad (Asiento Único Balanceado)
        try:
            cuenta_deuda = '1.1.02.02' if es_productor else '1.1.02.01'
            movimientos = []
            total_debe = Decimal('0.00')

            # Entradas de dinero
            pagos = [
                ('1.1.01.01', p_usd, 'USD'),
                ('1.1.01.02', p_bs / tasa if tasa > 0 else 0, 'BS'),
                ('1.1.01.03', (p_pm + p_tr) / tasa if tasa > 0 else 0, 'PM/TR'),
                ('1.1.01.04', p_bio / tasa if tasa > 0 else 0, 'BIO'),
                ('1.1.01.05', p_deb / tasa if tasa > 0 else 0, 'DEBITO')
            ]
            for cta, val, ref in pagos:
                if val > 0:
                    val_c = val.quantize(Decimal('0.01'))
                    movimientos.append({'cuenta_codigo': cta, 'debe_usd': val_c, 'haber_usd': 0, 'debe_bs': (val_c*tasa).quantize(Decimal('0.01')), 'haber_bs': 0})
                    total_debe += val_c

            # Registro de Deuda
            if falta_usd > 0:
                movimientos.append({'cuenta_codigo': cuenta_deuda, 'debe_usd': falta_usd, 'haber_usd': 0, 'debe_bs': (falta_usd*tasa).quantize(Decimal('0.01')), 'haber_bs': 0})
                total_debe += falta_usd

            # Ingreso por Venta (Haber)
            cta_vta = '4.1.02' if es_fiado else '4.1.01'
            movimientos.append({'cuenta_codigo': cta_vta, 'debe_usd': 0, 'haber_usd': total_venta, 'debe_bs': 0, 'haber_bs': (total_venta*tasa).quantize(Decimal('0.01'))})

            # Costo de Ventas
            if total_costo_usd > 0:
                movimientos.append({'cuenta_codigo': '5.1.01', 'debe_usd': total_costo_usd, 'haber_usd': 0, 'debe_bs': (total_costo_usd*tasa).quantize(Decimal('0.01')), 'haber_bs': 0})
                movimientos.append({'cuenta_codigo': '1.1.03.01', 'debe_usd': 0, 'haber_usd': total_costo_usd, 'debe_bs': 0, 'haber_bs': (total_costo_usd*tasa).quantize(Decimal('0.01'))})

            # Ajuste de centavos para balance
            diff = total_debe - total_venta
            if abs(diff) > 0 and abs(diff) < 0.10:
                cta_adj = '4.1.04' if diff < 0 else '5.1.04'
                if diff < 0:
                    movimientos.append({'cuenta_codigo': cta_adj, 'debe_usd': abs(diff), 'haber_usd': 0})
                else:
                    movimientos.append({'cuenta_codigo': cta_adj, 'debe_usd': 0, 'haber_usd': abs(diff)})

            registrar_asiento(
                descripcion=f"Venta #{nueva_venta.id} - {'Fiado' if es_fiado else 'Contado'}",
                tasa=tasa, referencia_tipo='VENTA', referencia_id=nueva_venta.id,
                movimientos=movimientos, user_id=current_user.id
            )
        except Exception as e:
            logger.error(f"Error contable en venta {nueva_venta.id}: {e}")

            registrar_asiento(
                descripcion=f"Venta #{nueva_venta.id} - {'PRODUCTOR' if es_productor else 'CLIENTE'} {'FIADO' if es_fiado else 'CONTADO'}",
                tasa=tasa,
                referencia_tipo='VENTA',
                referencia_id=nueva_venta.id,
                movimientos=movimientos,
                user_id=current_user.id
            )
        except Exception as cont_err:
            logger.error(f"Contabilidad falló: {cont_err}")

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
                    modulo_origen='Venta', referencia_id=nueva_venta.id,
                    user_id=current_user.id
                ))
            if p_bs > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Caja Bs',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_bs, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Efectivo Bs',
                    modulo_origen='Venta', referencia_id=nueva_venta.id,
                    user_id=current_user.id
                ))
            if p_pm > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_pm, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Pago Móvil',
                    modulo_origen='Venta', referencia_id=nueva_venta.id,
                    user_id=current_user.id
                ))
            if p_tr > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_tr, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Tarjeta/Transf',
                    modulo_origen='Venta', referencia_id=nueva_venta.id,
                    user_id=current_user.id
                ))
            if p_bio > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_bio, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Biopago BDV',
                    modulo_origen='Venta', referencia_id=nueva_venta.id,
                    user_id=current_user.id
                ))
            if p_deb > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='INGRESO', categoria='Venta POS',
                    monto=p_deb, tasa_dia=tasa,
                    descripcion=f'Venta #{nueva_venta.id} - Tarjeta Débito',
                    modulo_origen='Venta', referencia_id=nueva_venta.id,
                    user_id=current_user.id
                ))
        except Exception as caja_err:
            logger.error(f"Caja falló: {caja_err}")

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
            'premios_ganados': premio_club if premio_club else 0,
            'puntos_actuales': cliente.puntos if cliente else 0
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
            'precio': str(precio_oferta if precio_oferta > 0 else precio_normal),
            'cantidad': str(d.cantidad)
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
            'cliente': p.cliente.nombre if p.cliente else (f"PROD: {p.proveedor.nombre}" if p.proveedor else 'N/A'),
            'monto_usd': str(p.monto_usd),
            'monto_bs': str(p.monto_bs),
            'metodo_pago': p.metodo_pago,
            'banco': p.banco or 'N/A',
            'referencia': p.referencia or 'N/A',
            'observacion': p.observacion or '',
            'imagen': p.imagen_comprobante or '',
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
@staff_required
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
@login_required
@staff_required
def historial_ventas():
    ventas = Venta.query.order_by(Venta.id.desc()).limit(300).all()
    return render_template('historial_ventas.html', ventas=ventas)


@pos_bp.route('/historial_ventas/<int:venta_id>')
@login_required
@staff_required
def detalle_venta(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    tasa = venta.tasa_momento or Decimal('1.0')
    return render_template('detalle_venta.html', venta=venta, tasa=tasa)

@pos_bp.route('/detalle_venta/<int:venta_id>/json')
@login_required
@staff_required
def detalle_venta_json(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    resultado = []
    for d in venta.detalles:
        prod = Producto.query.get(d.producto_id)
        resultado.append({
            'nombre': prod.nombre if prod else f'Producto #{d.producto_id}',
            'cantidad': str(d.cantidad or Decimal('0.000')),
            'precio_unitario': str(d.precio_unitario_usd or Decimal('0.00'))
        })
    return jsonify(resultado)


@pos_bp.route('/anular_venta/<int:id>', methods=['POST'])
@login_required
@staff_required
def anular_venta(id):
    try:
        # --- 🔒 SEGUNDA PUERTA (VALIDACIÓN EN BD) ---
        pin_ingresado = request.json.get('pin') if request.is_json else request.form.get('pin')
        
        # Buscar algún supervisor o admin que tenga ese PIN
        autorizador = User.query.filter(
            User.role.in_(['admin', 'supervisor']),
            User.pin == str(pin_ingresado)
        ).first()

        if not pin_ingresado or not autorizador:
             return jsonify({'success': False, 'message': '🚫 PIN DE AUTORIZACIÓN INCORRECTO. Solo un Supervisor o Admin puede anular.'}), 403

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
                        usuario_id=current_user.id,
                        usuario_nombre=current_user.username,
                        producto_id=prod.id,
                        producto_nombre=prod.nombre,
                        accion=f'ANULACION_VENTA (Autoriza: {autorizador.username})',
                        cantidad_antes=antes,
                        cantidad_despues=prod.stock,
                        fecha=datetime.now()
                    )
                    db.session.add(audit)
                except Exception:
                    pass

        # ============================================================
        #   REVERSIÓN CONTABLE
        # ============================================================
        try:
            tasa_v = getattr(venta, 'tasa_momento', Decimal('1.00'))
            t_bs   = (venta.total_usd or 0) * tasa_v
            movs_reverso = []
            
            # 1. Reverse Payments (CREDIT to Cash/Bank)
            if (venta.pago_efectivo_usd or 0) > 0:
                movs_reverso.append({'cuenta_codigo': '1.1.01.01', 'debe_usd': 0, 'haber_usd': venta.pago_efectivo_usd, 'debe_bs': 0, 'haber_bs': 0})
            if (venta.pago_efectivo_bs or 0) > 0:
                movs_reverso.append({'cuenta_codigo': '1.1.01.02', 'debe_usd': 0, 'haber_usd': venta.pago_efectivo_bs / tasa_v, 'debe_bs': 0, 'haber_bs': venta.pago_efectivo_bs})
            if (venta.pago_movil_bs or 0) > 0:
                movs_reverso.append({'cuenta_codigo': '1.1.01.03', 'debe_usd': 0, 'haber_usd': venta.pago_movil_bs / tasa_v, 'debe_bs': 0, 'haber_bs': venta.pago_movil_bs})
            if (venta.pago_transferencia_bs or 0) > 0:
                movs_reverso.append({'cuenta_codigo': '1.1.01.03', 'debe_usd': 0, 'haber_usd': venta.pago_transferencia_bs / tasa_v, 'debe_bs': 0, 'haber_bs': venta.pago_transferencia_bs})
            if (venta.pago_debito_bs or 0) > 0:
                movs_reverso.append({'cuenta_codigo': '1.1.01.05', 'debe_usd': 0, 'haber_usd': venta.pago_debito_bs / tasa_v, 'debe_bs': 0, 'haber_bs': venta.pago_debito_bs})
            if (venta.biopago_bdv or 0) > 0:
                movs_reverso.append({'cuenta_codigo': '1.1.01.04', 'debe_usd': 0, 'haber_usd': venta.biopago_bdv / tasa_v, 'debe_bs': 0, 'haber_bs': venta.biopago_bdv})
            
            # 2. Reverse Fiado (CREDIT to Accounts Receivable)
            if (venta.saldo_pendiente_usd or 0) > 0:
                cuenta_deuda = '1.1.02.02' if (venta.cliente_id is None) else '1.1.02.01' # Productor (Compuesto) vs Cliente
                movs_reverso.append({'cuenta_codigo': cuenta_deuda, 'debe_usd': 0, 'haber_usd': venta.saldo_pendiente_usd, 'debe_bs': 0, 'haber_bs': (venta.saldo_pendiente_usd or 0)*tasa_v})

            # 3. Reverse Income (DEBIT to Sales)
            cuenta_ingreso = '4.1.02' if venta.es_fiado else '4.1.01'
            movs_reverso.append({'cuenta_codigo': cuenta_ingreso, 'debe_usd': venta.total_usd, 'haber_usd': 0, 'debe_bs': 0, 'haber_bs': t_bs})

            # 4. Reverse Cost of Sales (CREDIT to 5.1.01, DEBIT to Inventory 1.1.03.01)
            total_costo_reverso = Decimal('0.00')
            for det in getattr(venta, 'detalles', []):
                p = Producto.query.get(det.producto_id)
                if p:
                    total_costo_reverso += (p.costo_usd or Decimal('0.00')) * (det.cantidad or Decimal('0.00'))

            if total_costo_reverso > 0:
                costo_bs_rev = total_costo_reverso * tasa_v
                movs_reverso.append({'cuenta_codigo': '1.1.03.01', 'debe_usd': total_costo_reverso, 'haber_usd': 0,                    'debe_bs': 0,            'haber_bs': costo_bs_rev})
                movs_reverso.append({'cuenta_codigo': '5.1.01',    'debe_usd': 0,                   'haber_usd': total_costo_reverso, 'debe_bs': 0,            'haber_bs': costo_bs_rev})

            registrar_asiento(
                descripcion=f"ANULACIÓN VENTA #{venta.id} - Reversión de Operación",
                tasa=tasa_v,
                referencia_tipo='ANULACION_VENTA',
                referencia_id=venta.id,
                movimientos=movs_reverso,
                user_id=current_user.id
            )
        except Exception as cont_err:
            logger.error(f"Error en reversión contable por anulación: {cont_err}")

        try:
            monto_usd = seguro_decimal(venta.pago_efectivo_usd)
            if monto_usd > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Caja USD',
                    tipo_movimiento='EGRESO', categoria='Anulación Venta',
                    monto=monto_usd, tasa_dia=getattr(venta, 'tasa_momento', Decimal('1.00')),
                    descripcion=f'Anulación venta #{venta.id} - Efectivo USD',
                    modulo_origen='Venta', referencia_id=venta.id,
                    user_id=current_user.id
                ))
            monto_bs = seguro_decimal(venta.pago_efectivo_bs)
            if monto_bs > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Caja Bs',
                    tipo_movimiento='EGRESO', categoria='Anulación Venta',
                    monto=monto_bs, tasa_dia=getattr(venta, 'tasa_momento', Decimal('1.00')),
                    descripcion=f'Anulación venta #{venta.id} - Efectivo Bs',
                    modulo_origen='Venta', referencia_id=venta.id,
                    user_id=current_user.id
                ))
            monto_banco = (seguro_decimal(venta.pago_movil_bs) +
                           seguro_decimal(venta.pago_transferencia_bs) +
                           seguro_decimal(venta.biopago_bdv) +
                           seguro_decimal(venta.pago_debito_bs))
            if monto_banco > 0:
                db.session.add(MovimientoCaja(
                    fecha=datetime.now(), tipo_caja='Banco',
                    tipo_movimiento='EGRESO', categoria='Anulación Venta',
                    monto=monto_banco, tasa_dia=getattr(venta, 'tasa_momento', Decimal('1.00')),
                    descripcion=f'Anulación venta #{venta.id} - Movimientos Banco/Debito',
                    modulo_origen='Venta', referencia_id=venta.id,
                    user_id=current_user.id
                ))
        except Exception as e:
            logger.error(f"Error en reversión de caja por anulación: {e}")

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
                deuda_a_restar = seguro_decimal(venta.saldo_pendiente_usd)
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

# ==========================================================
#   NUEVO: RUTAS PARA VENTAS PAUSADAS (PERSISTENCIA 💾)
# ==========================================================

@pos_bp.route('/pausar_venta', methods=['POST'])
@login_required
@staff_required
def pausar_venta():
    try:
        data = request.get_json()
        if not data.get('items') or len(data['items']) == 0:
            return jsonify({'success': False, 'message': 'Nada que pausar.'})

        cliente_id = data.get('cliente_id')
        cliente_nombre = data.get('cliente_nombre', 'Sin nombre')
        cliente_tipo = data.get('cliente_tipo', 'cliente')
        total = seguro_decimal(data.get('total'))

        nueva_pausa = VentaPausada(
            cliente_id=int(cliente_id) if (cliente_id and str(cliente_id).isdigit()) else None,
            cliente_nombre_manual=cliente_nombre,
            cliente_tipo=cliente_tipo,
            total_usd=total,
            user_id=current_user.id
        )
        db.session.add(nueva_pausa)
        db.session.flush()

        for item in data['items']:
            # El frontend usa 'cant', pero manejamos ambos por seguridad
            cantidad_val = item.get('cant') or item.get('cantidad') or 0
            
            nuevo_detalle = DetalleVentaPausada(
                venta_pausada_id=nueva_pausa.id,
                producto_id=item['id'],
                cantidad=cantidad_val,
                precio_unitario_usd=item['precio']
            )

            db.session.add(nuevo_detalle)

        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Venta pausada en el servidor.'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al pausar venta: {e}")
        return jsonify({'success': False, 'message': str(e)})

@pos_bp.route('/ventas_pausadas')
@login_required
@staff_required
def listar_ventas_pausadas():
    try:
        # Mostramos todas las pausadas (cualquier cajero puede verlas)
        pausadas = VentaPausada.query.order_by(VentaPausada.fecha.desc()).all()
        res = []
        for p in pausadas:
            res.append({
                'id': p.id,
                'fecha': p.fecha.strftime('%d/%m %H:%M'),
                'cliente': p.cliente_nombre_manual or (p.cliente.nombre if p.cliente else "Desconocido"),
                'cliente_id': p.cliente_id,
                'cliente_tipo': p.cliente_tipo,
                'total': str(p.total_usd),
                'items_count': len(p.detalles),
                'cajero': p.user.username if p.user else "N/A"
            })
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@pos_bp.route('/recuperar_pausada/<int:id>')
@login_required
@staff_required
def recuperar_pausada(id):
    try:
        p = VentaPausada.query.get_or_404(id)
        items = []
        for d in p.detalles:
            items.append({
                'id': d.producto_id,
                'nombre': d.producto.nombre,
                'precio': str(d.precio_unitario_usd),
                'cantidad': str(d.cantidad),
                'subtotal': str(d.precio_unitario_usd * d.cantidad)
            })
        
        # Opcional: Borrarla al recuperarla? Mejor dejar que el frontend maneje si la borra tras éxito
        # User prefirió que el cajero la borre, pero recuperar suele implicar sacarla de "espera"
        return jsonify({
            'success': True,
            'cliente_id': p.cliente_id,
            'cliente_nombre': p.cliente_nombre_manual,
            'cliente_tipo': p.cliente_tipo,
            'items': items
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@pos_bp.route('/eliminar_pausada/<int:id>', methods=['POST'])
@login_required
@staff_required
def eliminar_pausada(id):
    try:
        p = VentaPausada.query.get_or_404(id)
        db.session.delete(p)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Venta pausada eliminada.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
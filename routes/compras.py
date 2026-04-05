from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from models import db, Producto, Proveedor, Compra, CompraDetalle, CuentaPorPagar, AbonoCuentaPorPagar, MovimientoCaja, TasaBCV
from decimal import Decimal
from datetime import datetime
import io
import openpyxl

compras_bp = Blueprint('compras', __name__)

# ==========================================================
#   LISTA DE COMPRAS + CARGA RÁPIDA
# ==========================================================
@compras_bp.route('/compras')
def lista_compras():
    compras     = Compra.query.order_by(Compra.fecha.desc()).all()
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    return render_template('compras.html', compras=compras, proveedores=proveedores)


# ==========================================================
#   BUSCAR PRODUCTO POR CÓDIGO (Para el escáner)
# ==========================================================
@compras_bp.route('/buscar_producto/<codigo>')
def buscar_producto(codigo):
    prod = Producto.query.filter_by(codigo=codigo).first()
    if prod:
        return jsonify({
            'id':     prod.id,
            'codigo': prod.codigo,
            'nombre': prod.nombre,
            'costo':  float(prod.costo_usd or 0)
        })
    return jsonify({'id': None})


# ==========================================================
#   BUSCAR PRODUCTO POR NOMBRE (búsqueda parcial)
# ==========================================================
@compras_bp.route('/buscar_producto_nombre/<texto>')
def buscar_producto_nombre(texto):
    texto = texto.strip()
    if not texto:
        return jsonify([])
    productos = Producto.query.filter(Producto.nombre.ilike(f'%{texto}%')).limit(10).all()
    resultados = []
    for p in productos:
        resultados.append({
            'id':     p.id,
            'codigo': p.codigo,
            'nombre': p.nombre,
            'costo':  float(p.costo_usd or 0)
        })
    return jsonify(resultados)


# ==========================================================
#   CREAR PRODUCTO RÁPIDO (Producto nuevo desde compras)
# ==========================================================
@compras_bp.route('/crear_producto_rapido', methods=['POST'])
def crear_producto_rapido():
    try:
        data          = request.get_json()
        codigo        = data.get('codigo', '').strip()
        nombre        = data.get('nombre', '').strip()
        costo         = Decimal(str(data.get('costo', 0)))
        precio        = Decimal(str(data.get('precio', 0)))
        precio_oferta = Decimal(str(data.get('precio_oferta', 0)))
        # ✅ CORREGIDO: Decimal en vez de int para aceptar kilos y bultos
        stock_inicial = Decimal(str(data.get('stock', 0)))

        if not nombre:
            return jsonify({'id': None, 'message': 'Falta el nombre'}), 400

        existente = Producto.query.filter_by(codigo=codigo).first()
        if existente:
            return jsonify({
                'id':     existente.id,
                'codigo': existente.codigo,
                'nombre': existente.nombre,
                'costo':  float(existente.costo_usd or 0)
            })

        nuevo = Producto(
            codigo            = codigo,
            nombre            = nombre,
            costo_usd         = costo,
            precio_normal_usd = precio,
            precio_oferta_usd = precio_oferta if precio_oferta > 0 else precio,
            stock             = stock_inicial
        )
        db.session.add(nuevo)
        db.session.commit()

        return jsonify({
            'id':     nuevo.id,
            'codigo': nuevo.codigo,
            'nombre': nuevo.nombre,
            'costo':  float(nuevo.costo_usd or 0)
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crear_producto_rapido: {e}")
        return jsonify({'id': None, 'message': str(e)}), 500


# ==========================================================
#   PROCESAR COMPRA RÁPIDA (Guardar factura + subir stock)
# ==========================================================
@compras_bp.route('/procesar_compra_rapida', methods=['POST'])
def procesar_compra_rapida():
    try:
        data         = request.get_json()
        proveedor_id = data.get('proveedor_id')
        num_factura  = data.get('numero_factura', '').strip()
        items        = data.get('items', [])
        metodo_pago  = data.get('metodo_pago', 'Credito')
        caja_origen  = data.get('caja_origen', None)

        if not proveedor_id or not items:
            return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400

        # 1. Calcular total
        # ✅ CORREGIDO: Decimal en vez de int para que 1.5 kilos no se convierta en 1
        total_usd = Decimal('0.00')
        for i in items:
            total_usd += Decimal(str(i['costo'])) * Decimal(str(i['cantidad']))

        # 2. Crear la Compra
        nueva_compra = Compra(
            proveedor_id   = proveedor_id,
            numero_factura = num_factura,
            fecha          = datetime.now(),
            total_usd      = total_usd,
            metodo_pago    = metodo_pago,
            caja_origen    = caja_origen,
            estado         = 'Pagado' if metodo_pago != 'Credito' else 'Pendiente'
        )
        db.session.add(nueva_compra)
        db.session.flush()

        # 3. Actualizar stock y costos de productos
        for item in items:
            prod = Producto.query.get(item['id'])
            if prod:
                # ✅ CORREGIDO: Decimal para que 20.5 kilos no se convierta en 20
                cantidad_item  = Decimal(str(item['cantidad']))
                prod.stock     = (prod.stock or Decimal('0')) + cantidad_item
                prod.costo_usd = Decimal(str(item['costo']))
                detalle = CompraDetalle(
                    compra_id      = nueva_compra.id,
                    producto_id    = prod.id,
                    cantidad       = cantidad_item,
                    costo_unitario = Decimal(str(item['costo']))
                )
                db.session.add(detalle)

        # 4. Lógica financiera según método de pago
        if metodo_pago in ('Contado USD', 'Contado Bs'):
            mov = MovimientoCaja(
                tipo_caja       = caja_origen,
                tipo_movimiento = 'EGRESO',
                categoria       = 'Compra de Mercancía',
                monto           = total_usd,
                descripcion     = f'Pago contado factura {num_factura}',
                modulo_origen   = 'Compra',
                referencia_id   = nueva_compra.id
            )
            db.session.add(mov)
        else:
            nueva_cxp = CuentaPorPagar(
                proveedor_id        = proveedor_id,
                compra_id           = nueva_compra.id,
                numero_factura      = num_factura,
                monto_total_usd     = total_usd,
                saldo_pendiente_usd = total_usd
            )
            db.session.add(nueva_cxp)

            prov = Proveedor.query.get(proveedor_id)
            prov.saldo_pendiente_usd = (prov.saldo_pendiente_usd or Decimal('0.00')) + total_usd

        db.session.commit()
        return jsonify({'status': 'success'})

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error procesar_compra_rapida: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==========================================================
#   ABONAR A PROVEEDOR (Bajar deuda de una factura)
# ==========================================================
@compras_bp.route('/compras/abonar', methods=['POST'])
def abonar_proveedor():
    try:
        data        = request.get_json()
        cxp_id      = data.get('cxp_id')
        caja_origen = data.get('caja_origen')
        moneda      = data.get('moneda', 'USD')
        tasa        = Decimal(str(data.get('tasa_bcv', 1) or 1))

        monto_raw = Decimal(str(data.get('monto_usd', 0)))

        if moneda == 'Bs' or caja_origen == 'Caja Bs':
            monto_usd = (monto_raw / tasa).quantize(Decimal('0.01'))
        else:
            monto_usd = monto_raw

        cxp = CuentaPorPagar.query.get(cxp_id)
        if not cxp or monto_usd <= 0:
            return jsonify({'status': 'error', 'message': 'Datos inválidos'})

        # ✅ VALIDACIÓN DE SEGURIDAD REPARADA
        # 🛑 BLOQUEO: Verificar que la caja tiene saldo suficiente
        ingresos = db.session.query(db.func.sum(MovimientoCaja.monto))\
            .filter_by(tipo_caja=caja_origen, tipo_movimiento='INGRESO').scalar() or Decimal('0')
        egresos = db.session.query(db.func.sum(MovimientoCaja.monto))\
            .filter_by(tipo_caja=caja_origen, tipo_movimiento='EGRESO').scalar() or Decimal('0')
        saldo_caja = Decimal(str(ingresos)) - Decimal(str(egresos))

        if monto_raw > saldo_caja:
            return jsonify({
                'status': 'error',
                'message': f'❌ Saldo insuficiente en {caja_origen}. Disponible: {saldo_caja:.2f}, necesitas: {monto_raw:.2f}'
            })
        if monto_usd > cxp.saldo_pendiente_usd + Decimal('0.05'):
            return jsonify({
                'status': 'error',
                'message': f'El monto (${monto_usd}) supera el saldo pendiente (${cxp.saldo_pendiente_usd})'
            })

        nuevo_abono = AbonoCuentaPorPagar(
            cuenta_id   = cxp.id,
            monto_usd   = monto_usd,
            metodo_pago = caja_origen,
            descripcion = f'Abono a factura {cxp.numero_factura} | '
                          f'{"Bs " + str(monto_raw) + " @ " + str(tasa) if moneda == "Bs" else "$" + str(monto_usd)}'
        )
        db.session.add(nuevo_abono)

        cxp.monto_abonado_usd   += monto_usd
        cxp.saldo_pendiente_usd -= monto_usd
        
        if cxp.saldo_pendiente_usd <= 0:
            cxp.saldo_pendiente_usd = Decimal('0.00')
            cxp.estatus = 'Pagado'
        else:
            cxp.estatus = 'Parcial'

        prov = Proveedor.query.get(cxp.proveedor_id)
        prov.saldo_pendiente_usd = (prov.saldo_pendiente_usd or Decimal('0.00')) - monto_usd
        if prov.saldo_pendiente_usd < 0:
            prov.saldo_pendiente_usd = Decimal('0.00')

        mov = MovimientoCaja(
            tipo_caja       = caja_origen,
            tipo_movimiento = 'EGRESO',
            categoria       = 'Pago a Proveedor',
            monto           = monto_raw,
            descripcion     = f'Abono a proveedor: {prov.nombre} | Factura: {cxp.numero_factura} | '
                              f'{"Bs " + str(monto_raw) + " (equiv. $" + str(monto_usd) + ")" if moneda == "Bs" else "$" + str(monto_usd)}',
            modulo_origen   = 'Abono Proveedor',
            referencia_id   = cxp.id
        )
        db.session.add(mov)

        db.session.commit()
        return jsonify({
            'status':     'success',
            'monto_usd':  float(monto_usd),
            'monto_raw':  float(monto_raw),
            'moneda':     moneda
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error abonar_proveedor: {e}")
        return jsonify({'status': 'error', 'message': str(e)})
# ==========================================================
#   DESCARGAR PLANTILLA EXCEL
# ==========================================================
@compras_bp.route('/inventario/plantilla_excel')
def descargar_plantilla():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventario"
    # ✅ CORREGIDO: Agregada columna unidad_medida en la plantilla
    ws.append(["codigo", "nombre", "costo_usd", "precio_normal_usd", "precio_oferta_usd", "stock", "unidad_medida"])
    ws.append(["00001", "Ejemplo Harina", 1.50, 2.00, 1.80, 45.5, "KG"])
    ws.append(["00002", "Ejemplo Refresco", 0.50, 0.80, 0.70, 24, "UND"])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, download_name="plantilla_inventario.xlsx",
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ==========================================================
#   CARGAR INVENTARIO DESDE EXCEL
# ==========================================================
@compras_bp.route('/inventario/cargar_excel', methods=['POST'])
def cargar_excel():
    archivo = request.files.get('archivo_excel')
    if not archivo:
        return jsonify({'status': 'error', 'message': 'No se recibió archivo'})
    try:
        wb = openpyxl.load_workbook(archivo)
        ws = wb.active
        creados = 0
        actualizados = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            # ✅ CORREGIDO: Lee unidad_medida del Excel (columna 7, opcional)
            codigo, nombre, costo, precio, oferta, stock, *extra = row
            unidad = extra[0] if extra else 'UND'
            if not nombre:
                continue
            prod = Producto.query.filter_by(codigo=str(codigo)).first()
            if prod:
                prod.costo_usd         = Decimal(str(costo or 0))
                prod.precio_normal_usd = Decimal(str(precio or 0))
                prod.precio_oferta_usd = Decimal(str(oferta or precio or 0))
                # ✅ CORREGIDO: Decimal en vez de int para kilos
                prod.stock             = Decimal(str(stock or 0))
                prod.unidad_medida     = str(unidad or 'UND').strip().upper()
                actualizados += 1
            else:
                nuevo = Producto(
                    codigo            = str(codigo),
                    nombre            = str(nombre),
                    costo_usd         = Decimal(str(costo or 0)),
                    precio_normal_usd = Decimal(str(precio or 0)),
                    precio_oferta_usd = Decimal(str(oferta or precio or 0)),
                    stock             = Decimal(str(stock or 0)),
                    unidad_medida     = str(unidad or 'UND').strip().upper()
                )
                db.session.add(nuevo)
                creados += 1
        db.session.commit()
        return jsonify({'status': 'success', 'creados': creados, 'actualizados': actualizados})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})


# ==========================================================
#   VISTA CUENTAS POR PAGAR
# ==========================================================
@compras_bp.route('/cuentas_por_pagar')
def cuentas_por_pagar():
    from models import TasaBCV
    cuentas     = CuentaPorPagar.query.order_by(CuentaPorPagar.fecha.desc()).all()
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    tasa_obj    = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
    tasa_bcv    = float(tasa_obj.valor) if tasa_obj else 1.0
    return render_template('cuentas_por_pagar.html',
                           cuentas=cuentas,
                           proveedores=proveedores,
                           tasa_bcv=tasa_bcv)


@compras_bp.route('/compras/<int:compra_id>/detalle')
def detalle_compra(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    return render_template('detalle_compra.html', compra=compra)
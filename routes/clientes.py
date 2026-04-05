from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db, Cliente, HistorialPago, TasaBCV, MovimientoCaja, PagoReportado, ahora_ve
from flask_login import login_required, current_user
from decimal import Decimal
from datetime import datetime
from sqlalchemy import func
from routes.contabilidad import registrar_asiento
from routes.usuarios import crear_acceso_sistema

clientes_bp = Blueprint('clientes', __name__)

def aplicar_pago_a_ventas(cliente, monto_usd):
    from models import Venta

    monto_restante = Decimal(str(monto_usd or 0))
    facturas_aplicadas = []

    if monto_restante <= Decimal('0.00'):
        return Decimal('0.00'), facturas_aplicadas

    ventas_pendientes = Venta.query.filter(
        Venta.cliente_id == cliente.id,
        Venta.saldo_pendiente_usd > 0
    ).order_by(Venta.fecha.asc()).all()

    for venta in ventas_pendientes:
        if monto_restante <= Decimal('0.00'):
            break

        saldo_actual = Decimal(str(venta.saldo_pendiente_usd or 0))
        if saldo_actual <= Decimal('0.00'):
            continue

        abono = min(saldo_actual, monto_restante)
        nuevo_saldo = saldo_actual - abono

        venta.saldo_pendiente_usd = nuevo_saldo
        if nuevo_saldo <= Decimal('0.00'):
            venta.saldo_pendiente_usd = Decimal('0.00')
            venta.pagada = True
        else:
            venta.pagada = False

        facturas_aplicadas.append({
            'venta_id': venta.id,
            'abonado': float(abono),
            'saldo_anterior': float(saldo_actual),
            'saldo_nuevo': float(venta.saldo_pendiente_usd)
        })

        monto_restante -= abono

    # Forzar el guardado temporal para que la sumatoria sea real
    db.session.flush()

    # Recalcamos el saldo REAL sumando todas las facturas que quedaron con deuda
    ventas_fiadas = Venta.query.filter(
        Venta.cliente_id == cliente.id,
        Venta.saldo_pendiente_usd > 0
    ).all()

    # ✅ CORRECCIÓN: sum() con Decimal('0.00') para evitar error 'int' object has no attribute 'quantize'
    saldo_sumado = sum((Decimal(str(v.saldo_pendiente_usd or 0)) for v in ventas_fiadas), Decimal('0.00'))
    
    # Manejar saldos a favor (si el abono superó la deuda)
    if monto_restante > 0:
        saldo_sumado -= monto_restante

    cliente.saldo_usd = saldo_sumado.quantize(Decimal('0.01'))
    
    # Sincronizar saldo BS con la tasa actual
    tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
    tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')
    cliente.saldo_bs = (cliente.saldo_usd * tasa).quantize(Decimal('0.01'))

    return monto_restante, facturas_aplicadas

# ========== LISTA DE CLIENTES ==========
@clientes_bp.route('/clientes')
def lista_clientes():
    todos = Cliente.query.all()
    hoy = datetime.now()
    cumpleaneros = []
    for c in todos:
        if c.fecha_nacimiento:
            fecha = c.fecha_nacimiento if hasattr(c.fecha_nacimiento, 'day') else None
            if fecha and fecha.day == hoy.day and fecha.month == hoy.month:
                cumpleaneros.append(c.nombre)
    return render_template('clientes.html', clientes=todos, cumpleaneros=cumpleaneros)

# ========== GUARDAR CLIENTE NUEVO ==========
@clientes_bp.route('/guardar_cliente', methods=['POST'])
def guardar_cliente():
    nombre    = request.form.get('nombre', '').strip()
    cedula    = request.form.get('cedula', '').strip()
    telefono  = request.form.get('telefono', '').strip()
    direccion = request.form.get('direccion', '').strip()
    f_str     = request.form.get('fecha_nacimiento')

    if not nombre:
        return "<script>alert('⚠️ El NOMBRE es obligatorio'); window.history.back();</script>"
    if not cedula:
        return "<script>alert('⚠️ La CÉDULA es obligatoria'); window.history.back();</script>"
    if Cliente.query.filter_by(cedula=cedula).first():
        return f"<script>alert('⚠️ Ya existe un cliente con la cédula {cedula}'); window.history.back();</script>"

    f_nac = None
    if f_str:
        try:
            f_nac = datetime.strptime(f_str, '%Y-%m-%d').date()
        except ValueError:
            f_nac = None

    try:
        nuevo = Cliente(
            nombre=nombre, cedula=cedula,
            telefono=telefono or None,
            direccion=direccion or None,
            fecha_nacimiento=f_nac,
            puntos=20, documentos=0
        )
        db.session.add(nuevo)
        db.session.flush() # Para obtener el ID del cliente antes de crear el usuario
        
        # Generar usuario automáticamente
        crear_acceso_sistema(nuevo, 'cliente')
        
        db.session.commit()
        return "<script>alert('✅ Cliente y Usuario guardados con éxito\\n🌟 ¡Bienvenido al Club del Vecino con 20 puntos!'); window.location.href='/clientes';</script>"
    except Exception as e:
        db.session.rollback()
        return f"<script>alert('❌ Error al guardar: {str(e)}'); window.history.back();</script>"

# ========== EDITAR CLIENTE ==========
@clientes_bp.route('/editar_cliente/<int:id>')
def editar_cliente(id):
    cliente = db.session.get(Cliente, id)
    if not cliente:
        return "Cliente no encontrado", 404
    return render_template('editar_cliente.html', cliente=cliente)

@clientes_bp.route('/actualizar_cliente/<int:id>', methods=['POST'])
def actualizar_cliente(id):
    cliente = db.session.get(Cliente, id)
    if not cliente:
        return "Cliente no encontrado", 404

    nombre    = request.form.get('nombre', '').strip()
    cedula    = request.form.get('cedula', '').strip()
    telefono  = request.form.get('telefono', '').strip()
    direccion = request.form.get('direccion', '').strip()
    f_str     = request.form.get('fecha_nacimiento')

    if not nombre:
        return "<script>alert('El nombre es obligatorio'); window.history.back();</script>"
    if not cedula:
        return "<script>alert('La cédula es obligatoria'); window.history.back();</script>"

    c_exist = Cliente.query.filter_by(cedula=cedula).first()
    if c_exist and c_exist.id != id:
        return f"<script>alert('Ya existe otro cliente con la cédula {cedula}'); window.history.back();</script>"

    f_nac = None
    if f_str:
        try:
            f_nac = datetime.strptime(f_str, '%Y-%m-%d').date()
        except:
            pass

    try:
        cliente.nombre    = nombre
        cliente.cedula    = cedula
        cliente.telefono  = telefono or None
        cliente.direccion = direccion or None
        cliente.fecha_nacimiento = f_nac
        db.session.commit()
        return "<script>alert('Cliente actualizado con éxito'); window.location.href='/clientes';</script>"
    except Exception as e:
        db.session.rollback()
        return f"<script>alert('❌ Error: {str(e)}'); window.history.back();</script>"

# ========== ELIMINAR CLIENTE ==========
@clientes_bp.route('/eliminar_cliente/<int:id>')
def eliminar_cliente(id):
    try:
        from models import Venta, Pedido, PagoReportado, User
        cliente = Cliente.query.get(id)
        if cliente:
            # 1. Conservar las ventas pasándolas a Consumidor Final
            Venta.query.filter_by(cliente_id=id).update({'cliente_id': None})
            
            # 2. Eliminar dependencias que no pueden quedar huérfanas
            Pedido.query.filter_by(cliente_id=id).delete()
            PagoReportado.query.filter_by(cliente_id=id).delete()
            HistorialPago.query.filter_by(cliente_id=id).delete()
            User.query.filter_by(cliente_id=id).delete()
            
            # 3. Eliminar el cliente
            db.session.delete(cliente)
            db.session.commit()
            flash('✅ Cliente eliminado correctamente. Sus ventas pasaron a ser de Consumidor Final.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al eliminar: {str(e)}', 'danger')
    return redirect(url_for('clientes.lista_clientes'))

# ========== MOROSOS ==========
@clientes_bp.route('/morosos')
def vista_morosos():
    # Más robusto: Filtra clientes cuya deuda absoluta en USD sea mayor a 0.01
    morosos = Cliente.query.filter(
        (func.abs(Cliente.saldo_usd) > 0.01) | (func.abs(Cliente.saldo_bs) > 0.1)
    ).all()
    total_deuda_usd = sum(c.saldo_usd for c in morosos if c.saldo_usd > 0)
    tasa = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
    tasa_bcv = Decimal(str(tasa.valor)) if tasa else Decimal('0')
    return render_template('morosos.html',
                           morosos=morosos,
                           total=total_deuda_usd,
                           tasa_bcv=tasa_bcv)

# ========== REGISTRAR ABONO (CONECTADO A CAJA) ==========
@clientes_bp.route('/clientes/abono/<int:id>', methods=['POST'])
def registrar_abono(id):
    try:
        cliente = Cliente.query.get_or_404(id)
        monto_raw = request.form.get('monto_usd', '0').replace(',', '.')
        monto_input = Decimal(monto_raw)
        metodo = request.form.get('metodo_pago', 'EFECTIVO_USD')

        if monto_input <= Decimal('0.00'):
            flash("⚠️ El monto debe ser mayor a 0", "danger")
            return redirect(url_for('clientes.vista_morosos'))

        tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
        tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')

        if metodo == 'EFECTIVO_USD':
            monto_usd = monto_input
            monto_bs = monto_usd * tasa
        else:
            monto_bs = monto_input
            monto_usd = monto_bs / tasa

        # --- SOLUCIÓN ATÓMICA ---
        monto_usd_dec = Decimal(str(monto_usd)).quantize(Decimal('0.01'))
        
        # 1. Aplicar pago real a las facturas pendientes y recalcular saldo del cliente
        # La función aplicar_pago_a_ventas ya actualiza cliente.saldo_usd y cliente.saldo_bs
        monto_sobrante, facturas_aplicadas = aplicar_pago_a_ventas(cliente, monto_usd_dec)

        # 3. Crear historial del pago
        nuevo_pago = HistorialPago(
            cliente_id=cliente.id,
            monto_usd=monto_usd,
            monto_bs=monto_bs,
            tasa_dia=tasa,
            metodo_pago=metodo,
            fecha=ahora_ve()
        )
        db.session.add(nuevo_pago)

        # 4. Texto de facturas afectadas
        facturas_txt = ', '.join([f"#{x['venta_id']}" for x in facturas_aplicadas]) if facturas_aplicadas else 'Sin facturas'

        # 5. Registrar ingreso en caja
        mapa_caja = {
            'EFECTIVO_USD': ('Caja USD', monto_usd),
            'EFECTIVO_BS':  ('Caja Bs',  monto_bs),
            'PAGO_MOVIL':   ('Banco',    monto_bs),
            'BIOPAGO':      ('Banco',    monto_bs),
            'DEBITO':       ('Banco',    monto_bs),
        }
        tipo_caja, monto_caja = mapa_caja.get(metodo, ('Caja USD', monto_usd))

        db.session.add(MovimientoCaja(
            fecha=ahora_ve(),
            tipo_movimiento='INGRESO',
            tipo_caja=tipo_caja,
            categoria='Cobro Fiado',
            monto=monto_caja,
            tasa_dia=tasa,
            descripcion=f"Abono deuda: {cliente.nombre} ({metodo}) | Facturas: {facturas_txt}",
            modulo_origen='Clientes',
            referencia_id=cliente.id,
            user_id=current_user.id if current_user.is_authenticated else None
        ))

        # 6. Asiento contable (Sin commit interno)
        try:
            mapa_cuentas = {
                'EFECTIVO_USD': '1.1.01.01',
                'EFECTIVO_BS':  '1.1.01.02',
                'PAGO_MOVIL':   '1.1.01.03',
                'BIOPAGO':      '1.1.01.04',
                'DEBITO':       '1.1.01.05',
            }
            cuenta_destino = mapa_cuentas.get(metodo, '1.1.01.01')
            es_usd = (metodo == 'EFECTIVO_USD')

            registrar_asiento(
                descripcion=f"Cobro de Deuda: {cliente.nombre} | {metodo} | Facturas: {facturas_txt}",
                tasa=float(tasa),
                referencia_tipo='ABONO_CLIENTE',
                referencia_id=cliente.id,
                movimientos=[
                    {
                        'cuenta_codigo': cuenta_destino,
                        'debe_usd': float(monto_usd) if es_usd else 0,
                        'haber_usd': 0,
                        'debe_bs': float(monto_bs) if not es_usd else 0,
                        'haber_bs': 0
                    },
                    {
                        'cuenta_codigo': '1.1.02.01',
                        'debe_usd': 0,
                        'haber_usd': float(monto_usd),
                        'debe_bs': 0,
                        'haber_bs': float(monto_bs)
                    }
                ],
                commit=False
            )
        except Exception as e:
            print(f"⚠️ Error contable en abono (se continúa el proceso): {e}")

        # ÚNICO COMMIT PARA TODO EL PROCESO
        db.session.commit()


        saldo_nuevo = Decimal(str(cliente.saldo_usd or 0))

        if saldo_nuevo == Decimal('0.00'):
            flash(f"✅ Pago registrado. Deuda saldada. Facturas aplicadas: {facturas_txt}", "success")
        else:
            flash(f"✅ Pago registrado. Saldo pendiente: ${saldo_nuevo:.2f}. Facturas aplicadas: {facturas_txt}", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error crítico al registrar abono: {str(e)}", "danger")

    return redirect(url_for('clientes.vista_morosos'))

# ========== CREAR CLIENTE DESDE EL POS (AJAX) ==========
@clientes_bp.route('/crear_cliente_pos', methods=['POST'])
def crear_cliente_pos():
    data = request.get_json() or {}
    try:
        nombre        = (data.get('nombre') or '').strip().upper()
        cedula        = (data.get('cedula') or '').strip()
        telefono      = (data.get('telefono') or '').strip()
        fecha_nac_str = data.get('fecha_nacimiento')

        if not nombre or not cedula or not fecha_nac_str:
            return jsonify({'success': False,
                            'message': 'Nombre, Cédula y Fecha de Nacimiento son obligatorios.'})

        existe = Cliente.query.filter_by(cedula=cedula).first()
        if existe:
            return jsonify({'success': False,
                            'message': f'La cédula {cedula} ya pertenece a {existe.nombre}.'})

        try:
            f_nac = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Fecha de nacimiento inválida.'})

        nuevo = Cliente(
            nombre=nombre, cedula=cedula,
            telefono=telefono or None,
            direccion=None,
            fecha_nacimiento=f_nac,
            puntos=20, documentos=0
        )
        db.session.add(nuevo)
        db.session.flush() # Necesario para conseguir el ID del cliente
        
        # Crear usuario automáticamente
        crear_acceso_sistema(nuevo, 'cliente')
        
        db.session.commit()

        return jsonify({'success': True, 'id': nuevo.id,
                        'nombre': nuevo.nombre, 'cedula': nuevo.cedula, 'puntos': 20})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# ========== HISTORIAL DE ABONOS ==========
@clientes_bp.route('/historial_abonos')
def historial_abonos():
    pagos = HistorialPago.query.order_by(HistorialPago.fecha.desc()).all()
    return render_template('historial_abonos.html', pagos=pagos)

# ========== EDITAR PUNTOS (SOLO ADMIN) ==========
@clientes_bp.route('/actualizar_puntos/<int:id>', methods=['POST'])
@login_required
def actualizar_puntos(id):
    if getattr(current_user, 'role', '').lower() != 'admin':
        return jsonify({'success': False,
                        'message': '🚫 Sin permiso. Solo el administrador puede editar puntos.'}), 403

    cliente = Cliente.query.get_or_404(id)
    data = request.get_json() or {}
    try:
        nuevos_puntos = int(data.get('puntos', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Puntos inválidos'}), 400

    if nuevos_puntos < 0:
        return jsonify({'success': False, 'message': 'Los puntos no pueden ser negativos.'}), 400

    try:
        cliente.puntos = nuevos_puntos
        db.session.commit()
        return jsonify({'success': True,
                        'message': f'✅ Puntos de {cliente.nombre} actualizados a {nuevos_puntos}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# ========== DETALLES DEUDA (AJAX) ==========
@clientes_bp.route('/clientes/detalles_deuda/<int:id>')
@login_required
def detalles_deuda(id):
    from models import Venta, HistorialPago, db
    
    # 1. Buscamos TODOS los abonos (Libro Diario / Reportados / Iniciales)
    pagos = HistorialPago.query.filter_by(cliente_id=id).all()
    abono_total_disponible = float(sum(p.monto_usd for p in pagos)) if pagos else 0.0

    # 2. Traemos todas las ventas con deuda, de orden viejo a nuevo
    ventas = Venta.query.filter(
        Venta.cliente_id == id,
        Venta.saldo_pendiente_usd > 0
    ).order_by(Venta.fecha.asc()).all()

    detalles = []
    cambios_realizados = False

    for v in ventas:
        total_v = float(v.total_usd or 0)
        
        if abono_total_disponible >= total_v:
            # El abono histórico cubre toda esta factura. Curamos el saldo fantasma.
            if float(v.saldo_pendiente_usd) > 0:
                v.saldo_pendiente_usd = 0
                cambios_realizados = True
            
            abono_total_disponible -= total_v
            continue # Se omite porque está 100% pagada
        else:
            # Queda una fracción por pagar o cero abono disponible
            pago_parcial = abono_total_disponible
            pendiente_real = total_v - pago_parcial
            
            if abs(float(v.saldo_pendiente_usd or 0) - pendiente_real) > 0.01:
                v.saldo_pendiente_usd = pendiente_real
                cambios_realizados = True
            
            abono_total_disponible = 0 
            
            detalles.append({
                'id':         v.id,
                'fecha':      v.fecha.strftime('%d/%m/%Y %H:%M'),
                'total_usd':  total_v,
                'pagado_usd': round(pago_parcial, 2),
                'pendiente':  round(pendiente_real, 2)
            })

    if cambios_realizados:
        db.session.commit()
    
    # Alineamos el cliente general con la realidad de las facturas no pagadas
    saldo_real_facturas = sum(d['pendiente'] for d in detalles)
    cliente = db.session.get(Cliente, id)
    if cliente:
        # Forzar a cero si es insignificante
        if abs(saldo_real_facturas) < 0.01:
            saldo_real_facturas = 0
            
        cliente.saldo_usd = Decimal(str(saldo_real_facturas)).quantize(Decimal('0.01'))
        
        # Sincronizar saldo BS también
        tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
        tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')
        cliente.saldo_bs = (cliente.saldo_usd * tasa).quantize(Decimal('0.01'))
        
        db.session.commit()

    detalles.reverse()
    return jsonify(detalles)

# ========== DETALLE FACTURA (AJAX) ==========
@clientes_bp.route('/clientes/detalle_factura/<int:venta_id>')
def detalle_factura(venta_id):
    from models import Venta, DetalleVenta
    venta    = Venta.query.get_or_404(venta_id)
    detalles = DetalleVenta.query.filter_by(venta_id=venta_id).all()

    productos = [{
        'nombre':          d.producto.nombre,
        'cantidad':        float(d.cantidad),
        'precio_unitario': float(d.precio_unitario_usd),
        'subtotal':        float(d.cantidad * d.precio_unitario_usd)
    } for d in detalles]

    return jsonify({
        'id':        venta.id,
        'fecha':     venta.fecha.strftime('%d/%m/%Y %H:%M'),
        'cliente':   venta.cliente.nombre if venta.cliente else 'Consumidor Final',
        'total_usd': float(venta.total_usd),
        'productos': productos
    })

# ========== PAGOS REPORTADOS ==========
@clientes_bp.route('/pagos_reportados')
@login_required
def pagos_reportados():
    rol = (getattr(current_user, 'role', '') or '').lower()
    if rol not in ['admin', 'cajero', 'superadmin']:
        flash('⛔ No tienes permiso para ver pagos reportados.', 'danger')
        return redirect(url_for('clientes.vista_morosos'))

    pagos = PagoReportado.query.order_by(PagoReportado.fecha_reporte.desc()).all()
    return render_template('clientes/pagos_reportados.html', pagos=pagos)

@clientes_bp.route('/pagos_reportados/<int:pago_id>/estado', methods=['POST'])
@login_required
def cambiar_estado_pago_reportado(pago_id):
    rol = (getattr(current_user, 'role', '') or '').lower()
    if rol not in ['admin', 'cajero', 'superadmin']:
        flash('⛔ No tienes permiso para cambiar el estado de pagos reportados.', 'danger')
        return redirect(url_for('clientes.vista_morosos'))

    pago = PagoReportado.query.get_or_404(pago_id)
    nuevo_estado = (request.form.get('estado') or '').strip().lower()

    estados_validos = ['pendiente', 'aprobado', 'rechazado', 'revisado']
    if nuevo_estado not in estados_validos:
        flash('⚠️ Estado inválido.', 'warning')
        return redirect(url_for('clientes.pagos_reportados'))

    # Compatibilidad con el botón viejo "revisado"
    if nuevo_estado == 'revisado':
        nuevo_estado = 'aprobado'

    try:
        # Si lo están aprobando, aplicar el abono real
        if nuevo_estado == 'aprobado':
            # evitar aplicar dos veces
            if (pago.estado or '').lower() in ['aprobado', 'revisado']:
                flash(f'⚠️ El pago reportado #{pago.id} ya fue aplicado anteriormente.', 'warning')
                return redirect(url_for('clientes.pagos_reportados'))

            cliente = pago.cliente
            if not cliente:
                flash('❌ El pago reportado no tiene cliente asociado.', 'danger')
                return redirect(url_for('clientes.pagos_reportados'))

            tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
            tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')

            monto_usd = Decimal(str(pago.monto_usd or 0))
            monto_bs = Decimal(str(pago.monto_bs or 0))
            metodo = (pago.metodo_pago or 'PAGO_MOVIL').strip().upper()

            # Normalizar método según tus métodos válidos de caja
            mapa_metodos = {
                'PAGO MOVIL': 'PAGO_MOVIL',
                'PAGO_MOVIL': 'PAGO_MOVIL',
                'TRANSFERENCIA': 'PAGO_MOVIL',
                'TRANSFERENCIA BS': 'PAGO_MOVIL',
                'EFECTIVO BS': 'EFECTIVO_BS',
                'EFECTIVO_BS': 'EFECTIVO_BS',
                'EFECTIVO USD': 'EFECTIVO_USD',
                'EFECTIVO_USD': 'EFECTIVO_USD',
                'BIOPAGO': 'BIOPAGO',
                'DEBITO': 'DEBITO'
            }
            metodo = mapa_metodos.get(metodo, metodo)

            # Completar montos si uno viene en cero
            if monto_usd <= Decimal('0.00') and monto_bs > Decimal('0.00'):
                monto_usd = monto_bs / tasa

            if monto_bs <= Decimal('0.00') and monto_usd > Decimal('0.00'):
                monto_bs = monto_usd * tasa

            if monto_usd <= Decimal('0.00') and monto_bs <= Decimal('0.00'):
                flash('❌ El pago reportado no tiene un monto válido.', 'danger')
                return redirect(url_for('clientes.pagos_reportados'))

            # 1. Historial de pagos
            nuevo_pago = HistorialPago(
                cliente_id=cliente.id,
                monto_usd=monto_usd,
                monto_bs=monto_bs,
                tasa_dia=tasa,
                metodo_pago=metodo,
                fecha=ahora_ve()
            )
            db.session.add(nuevo_pago)

            # 2. Aplicar pago a las facturas reales para que elimine la deuda!
            monto_sobrante, facturas_aplicadas = aplicar_pago_a_ventas(cliente, monto_usd)
            
            # Mantener saldo Bs alineado
            cliente.saldo_bs = (cliente.saldo_usd or Decimal('0.00')) * tasa

            # 3. Registrar ingreso en MovimientoCaja
            mapa_caja = {
                'EFECTIVO_USD': ('Caja USD', monto_usd),
                'EFECTIVO_BS':  ('Caja Bs',  monto_bs),
                'PAGO_MOVIL':   ('Banco',    monto_bs),
                'BIOPAGO':      ('Banco',    monto_bs),
                'DEBITO':       ('Banco',    monto_bs),
            }
            tipo_caja, monto_caja = mapa_caja.get(metodo, ('Banco', monto_bs))

            db.session.add(MovimientoCaja(
                fecha=ahora_ve(),
                tipo_movimiento='INGRESO',
                tipo_caja=tipo_caja,
                categoria='Cobro Fiado',
                monto=monto_caja,
                tasa_dia=tasa,
                descripcion=f"Pago reportado aprobado: {cliente.nombre} ({metodo}) Ref: {pago.referencia or ''}",
                modulo_origen='PagosReportados',
                referencia_id=pago.id,
                user_id=current_user.id
            ))

            # 4. Asiento contable
            try:
                mapa_cuentas = {
                    'EFECTIVO_USD': '1.1.01.01',
                    'EFECTIVO_BS':  '1.1.01.02',
                    'PAGO_MOVIL':   '1.1.01.03',
                    'BIOPAGO':      '1.1.01.04',
                    'DEBITO':       '1.1.01.05',
                }
                cuenta_destino = mapa_cuentas.get(metodo, '1.1.01.03')
                es_usd = (metodo == 'EFECTIVO_USD')

                registrar_asiento(
                    descripcion=f"Pago reportado aprobado: {cliente.nombre} | {metodo}",
                    tasa=float(tasa),
                    referencia_tipo='PAGO_REPORTADO',
                    referencia_id=pago.id,
                    movimientos=[
                        {
                            'cuenta_codigo': cuenta_destino,
                            'debe_usd': float(monto_usd) if es_usd else 0,
                            'haber_usd': 0,
                            'debe_bs': float(monto_bs) if not es_usd else 0,
                            'haber_bs': 0
                        },
                        {
                            'cuenta_codigo': '1.1.02.01',
                            'debe_usd': 0,
                            'haber_usd': float(monto_usd),
                            'debe_bs': 0,
                            'haber_bs': float(monto_bs)
                        }
                    ]
                )
            except Exception as e:
                print(f"⚠️ Error contable en pago reportado (no crítico): {e}")

        # Si cambia a pendiente o rechazado, solo cambiar estado
        pago.estado = nuevo_estado
        db.session.commit()

        flash(f'✅ Pago reportado #{pago.id} marcado como "{nuevo_estado}".', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error actualizando estado: {str(e)}', 'danger')

    return redirect(url_for('clientes.pagos_reportados'))
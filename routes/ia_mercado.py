from flask import Blueprint, render_template, current_app, redirect, url_for, flash, request
from models import Producto, Venta, Cliente, db, MovimientoCaja
from datetime import datetime, timedelta
from sqlalchemy import func
from decimal import Decimal
from flask_login import login_required, current_user

ia_mercado_bp = Blueprint('ia_mercado', __name__)

@ia_mercado_bp.route('/ia-mercado')
@login_required
def index():
    hoy = datetime.now().date()

    # ============================================================
    # 📒 AUDITORÍA CONTABLE IA
    # ============================================================
    total_ventas_hoy = db.session.query(func.sum(Venta.total_usd)).filter(
        func.date(Venta.fecha) == hoy
    ).scalar() or 0

    # Traemos monto Y tasa para convertir a USD
    movimientos_hoy = db.session.query(
        MovimientoCaja.monto, MovimientoCaja.tasa_dia
    ).filter(
        func.date(MovimientoCaja.fecha) == hoy,
        MovimientoCaja.tipo_movimiento == 'INGRESO',
        MovimientoCaja.categoria.ilike('%Venta%')
    ).all()

    # Convertimos cada movimiento a USD dividiendo entre su tasa
    total_caja_hoy = sum(
        float(m.monto) / float(m.tasa_dia)
        for m in movimientos_hoy
        if m.tasa_dia and float(m.tasa_dia) > 0
    )

    descuadre = float(total_ventas_hoy) - float(total_caja_hoy)

    informe_contable = {
        'ventas':    total_ventas_hoy,
        'en_caja':   total_caja_hoy,
        'descuadre': descuadre,
        'estado':    '✅ CUADRADO' if abs(descuadre) < 0.01 else '⚠️ DESCUADRADO'
    }

    # ============================================================
    # 📦 INVENTARIO CRÍTICO
    # ============================================================
    productos_criticos = Producto.query.filter(
        Producto.stock <= Producto.stock_minimo
    ).all()

    # ============================================================
    # 💰 PRODUCTOS ESTANCADOS (sin ventas en 30 días)
    # ============================================================
    hace_30_dias = datetime.now() - timedelta(days=30)
    ids_vendidos = db.session.query(func.distinct(Venta.id)).filter(
        Venta.fecha >= hace_30_dias
    ).subquery()
    productos_estancados = Producto.query.limit(10).all()

    # ============================================================
    # ⭐ CLUB DEL VECINO
    # ============================================================
    clientes_top = Cliente.query.filter(
        Cliente.puntos >= 150, Cliente.puntos < 200
    ).all()

    hace_15_dias = datetime.now() - timedelta(days=15)
    clientes_activos_ids = db.session.query(Venta.cliente_id).filter(
        Venta.fecha >= hace_15_dias,
        Venta.cliente_id != None
    ).subquery()
    clientes_inactivos = Cliente.query.filter(
        ~Cliente.id.in_(clientes_activos_ids)
    ).limit(5).all()

    # ============================================================
    # 🌾 TEMPORADA / ZAFRA
    # ============================================================
    mes_actual = datetime.now().month
    if mes_actual in [2, 3, 4]:
        sugerencia_zafra = "ALERTA ZAFRA: Temporada de Caraotas. Priorizar stock de Herbicidas y sacos."
    elif mes_actual in [5, 6, 7]:
        sugerencia_zafra = "ALERTA INVIERNO: Temporada de Queso. Asegurar Sal y Cuajo."
    else:
        sugerencia_zafra = "TEMPORADA REGULAR: Mantener víveres y repuestos."

    return render_template('ia_mercado.html',
                           informe=informe_contable,
                           criticos=productos_criticos,
                           estancados=productos_estancados,
                           clientes_top=clientes_top,
                           clientes_inactivos=clientes_inactivos,
                           sugerencia_zafra=sugerencia_zafra,
                           now=datetime.now())

# ============================================================
# 🤖 ACCIÓN IA: AJUSTE CONTABLE
# ============================================================
@ia_mercado_bp.route('/ia/ajuste_contable', methods=['POST'])
@login_required
def ia_ajuste_contable():
    from routes.contabilidad import registrar_asiento
    try:
        registrar_asiento(
            descripcion="IA: Ajuste automático por diferencia de cambio/redondeo",
            tasa=1.0,
            referencia_tipo='AJUSTE_IA',
            referencia_id=0,
            movimientos=[
                {'cuenta_codigo': '5.1.01.01', 'debe_usd': 1.0, 'haber_usd': 0, 'debe_bs': 0, 'haber_bs': 0},
                {'cuenta_codigo': '1.1.01.01', 'debe_usd': 0, 'haber_usd': 1.0, 'debe_bs': 0, 'haber_bs': 0},
            ]
        )
        db.session.commit()
        flash("✅ IA: Asiento de ajuste contable generado.", "success")
    except Exception as e:
        flash(f"❌ Error en ajuste IA: {str(e)}", "danger")
    return redirect(url_for('ia_mercado.index'))

# ============================================================
# 🤖 ACCIÓN IA: APLICAR OFERTA
# ============================================================
@ia_mercado_bp.route('/ia/aplicar_oferta/<int:id>', methods=['POST'])
@login_required
def ia_aplicar_oferta(id):
    prod = Producto.query.get_or_404(id)
    nuevo_precio = prod.precio_normal_usd * Decimal('0.90')
    prod.precio_oferta_usd = nuevo_precio
    db.session.commit()
    flash(f"✅ IA: Oferta aplicada a {prod.nombre}. Nuevo precio: ${nuevo_precio:.2f}", "info")
    return redirect(url_for('ia_mercado.index'))

# ============================================================
# 🤖 ACCIÓN IA: BONO CLUB DEL VECINO
# ============================================================
@ia_mercado_bp.route('/ia/enviar_bono/<int:id>', methods=['POST'])
@login_required
def ia_enviar_bono(id):
    cliente = Cliente.query.get_or_404(id)
    cliente.puntos += 10
    db.session.commit()
    flash(f"✅ IA: +10 puntos otorgados a {cliente.nombre}.", "success")
    return redirect(url_for('ia_mercado.index'))
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz
from decimal import Decimal
from flask_login import UserMixin
from sqlalchemy.ext.hybrid import hybrid_property

db = SQLAlchemy()

# ============================================================
# ⏰ FUNCIONES PARA LA HORA DE VENEZUELA
# ============================================================
def ahora_ve():
    return datetime.now(pytz.timezone('America/Caracas')).replace(tzinfo=None)

def hoy_ve():
    return datetime.now(pytz.timezone('America/Caracas')).date()


class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.Text)
    fecha_nacimiento = db.Column(db.Date)
    saldo_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    saldo_bs = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    puntos = db.Column(db.Integer, default=0)
    documentos = db.Column(db.Integer, default=0)
    ventas = db.relationship('Venta', backref='cliente', lazy=True)
    abonos = db.relationship('HistorialPago', backref='cliente', lazy=True)

    def __repr__(self):
        return f'<Cliente {self.nombre} - {self.cedula}>'


class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    costo_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    precio_normal_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    precio_oferta_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    stock = db.Column(db.Numeric(12, 3), default=Decimal('0.000'))
    stock_minimo = db.Column(db.Numeric(12, 3), default=Decimal('5.000'))
    unidad_medida = db.Column(db.String(10), default='UND')

    def __repr__(self):
        return f'<Producto {self.nombre} ({self.codigo})>'


class TasaBCV(db.Model):
    __tablename__ = 'tasas_bcv'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=hoy_ve, unique=True)
    valor = db.Column(db.Numeric(10, 4), nullable=False)


class Venta(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    total_usd = db.Column(db.Numeric(10, 2), nullable=False)
    tasa_momento = db.Column(db.Numeric(10, 4), nullable=False)
    es_fiado = db.Column(db.Boolean, default=False)
    pagada = db.Column(db.Boolean, default=True)
    pago_efectivo_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    pago_efectivo_bs = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    pago_movil_bs = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    pago_transferencia_bs = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    biopago_bdv = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    saldo_pendiente_usd = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    detalles = db.relationship('DetalleVenta', backref='venta', lazy=True)

    @property
    def nombre_cliente_final(self):
        if self.cliente:
            return self.cliente.nombre
        mov = MovimientoProductor.query.filter(
            MovimientoProductor.tipo == 'COMPRA_POS',
            MovimientoProductor.descripcion.like(f'%#{self.id}%')
        ).first()
        if mov and mov.proveedor:
            return f"PROD: {mov.proveedor.nombre}"
        return "Consumidor Final"


class DetalleVenta(db.Model):
    __tablename__ = 'detalles_ventas'
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Numeric(12, 3), nullable=False)
    precio_unitario_usd = db.Column(db.Numeric(10, 2), nullable=False)
    producto = db.relationship('Producto', backref='detalles', lazy=True)


class HistorialPago(db.Model):
    __tablename__ = 'historial_pagos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=True)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    monto_usd = db.Column(db.Numeric(10, 2), nullable=False)
    monto_bs = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    tasa_dia = db.Column(db.Numeric(10, 4), default=Decimal('1.00'))
    metodo_pago = db.Column(db.String(50))


class PagoReportado(db.Model):
    __tablename__ = 'pagos_reportados'

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    fecha_reporte = db.Column(db.DateTime, default=ahora_ve, nullable=False)
    fecha_pago = db.Column(db.Date, nullable=True)

    monto_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    monto_bs = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))

    metodo_pago = db.Column(db.String(50))
    referencia = db.Column(db.String(100))
    banco = db.Column(db.String(100))
    observacion = db.Column(db.Text)

    imagen_comprobante = db.Column(db.String(255))
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, aprobado, rechazado

    cliente = db.relationship('Cliente', backref='pagos_reportados')
    user = db.relationship('User', backref='pagos_reportados')

    def __repr__(self):
        return f'<PagoReportado {self.id} - Cliente {self.cliente_id} - {self.estado}>'


class Proveedor(db.Model):
    __tablename__ = 'proveedores'
    id = db.Column(db.Integer, primary_key=True)
    rif = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.Text)
    vendedor_nombre = db.Column(db.String(100))
    vendedor_telefono = db.Column(db.String(20))
    saldo_pendiente_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    es_productor = db.Column(db.Boolean, default=False)


class Compra(db.Model):
    __tablename__ = 'compras'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'))
    numero_factura = db.Column(db.String(50))
    total_usd = db.Column(db.Numeric(10, 2))
    estado = db.Column(db.String(20), default='Pendiente')
    metodo_pago = db.Column(db.String(30), default='Credito')
    caja_origen = db.Column(db.String(30), nullable=True)
    proveedor = db.relationship('Proveedor', backref=db.backref('compras', lazy=True))
    detalles = db.relationship('CompraDetalle', backref='compra', lazy=True)


class CompraDetalle(db.Model):
    __tablename__ = 'compras_detalles'
    id = db.Column(db.Integer, primary_key=True)
    compra_id = db.Column(db.Integer, db.ForeignKey('compras.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Numeric(12, 3), nullable=False)
    costo_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    producto = db.relationship('Producto', backref='compra_detalles', lazy=True)


class CierreCaja(db.Model):
    __tablename__ = 'cierres_caja'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=hoy_ve)
    monto_bs = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    monto_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    pago_movil = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    transferencia = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    biopago = db.Column(db.Numeric(15, 2), default=Decimal('0.00'))
    tasa_cierre = db.Column(db.Numeric(10, 4), default=Decimal('1.00'))
    total_ventas_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    total_compras_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    fiado_dia_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    detalle_ventas = db.Column(db.Text, default='[]')
    detalle_compras = db.Column(db.Text, default='[]')


# ==========================================================
#              MÓDULO DE CONTABILIDAD
# ==========================================================

class CuentaContable(db.Model):
    __tablename__ = 'cuentas_contables'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20))
    naturaleza = db.Column(db.String(10))
    es_detalle = db.Column(db.Boolean, default=True)


class Asiento(db.Model):
    __tablename__ = 'asientos'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    descripcion = db.Column(db.String(255), nullable=False)
    tasa_referencia = db.Column(db.Numeric(16, 2), nullable=False)
    referencia_tipo = db.Column(db.String(50))
    referencia_id = db.Column(db.Integer)
    detalles = db.relationship('DetalleAsiento', backref='asiento', lazy=True)


class DetalleAsiento(db.Model):
    __tablename__ = 'detalles_asientos'
    id = db.Column(db.Integer, primary_key=True)
    asiento_id = db.Column(db.Integer, db.ForeignKey('asientos.id'), nullable=False)
    cuenta_id = db.Column(db.Integer, db.ForeignKey('cuentas_contables.id'), nullable=False)
    debe_usd = db.Column(db.Numeric(16, 2), default=Decimal('0.00'))
    haber_usd = db.Column(db.Numeric(16, 2), default=Decimal('0.00'))
    debe_bs = db.Column(db.Numeric(16, 2), default=Decimal('0.00'))
    haber_bs = db.Column(db.Numeric(16, 2), default=Decimal('0.00'))
    cuenta = db.relationship('CuentaContable', backref='movimientos', lazy=True)


class LiquidacionCiudad(db.Model):
    __tablename__ = 'liquidaciones_ciudad'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    kilos_vendidos = db.Column(db.Numeric(10, 2), nullable=False)
    precio_venta_usd = db.Column(db.Numeric(10, 2), nullable=False)
    ingreso_bruto_usd = db.Column(db.Numeric(10, 2), nullable=False)
    gastos_operativos_usd = db.Column(db.Numeric(10, 2), nullable=False)
    utilidad_neta_usd = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago = db.Column(db.String(50))


# ==========================================================
#        MÓDULO DE PRODUCTORES PRO (LIBRETA DIGITAL)
# ==========================================================

class MovimientoProductor(db.Model):
    __tablename__ = 'movimientos_productores'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    descripcion = db.Column(db.String(200))
    kilos = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    monto_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    debe = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    haber = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    saldo_momento = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    soporte_digital = db.Column(db.String(255))
    anio = db.Column(db.Integer, default=lambda: ahora_ve().year)
    semana_del_anio = db.Column(db.Integer, default=lambda: ahora_ve().isocalendar()[1])
    proveedor = db.relationship('Proveedor', backref=db.backref('movimientos', lazy=True))


class PagoProductor(db.Model):
    __tablename__ = 'pagos_productor'
    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    monto_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    metodo = db.Column(db.String(50))
    beneficiario = db.Column(db.String(150))
    referencia = db.Column(db.String(100))
    descripcion = db.Column(db.String(200))
    proveedor = db.relationship('Proveedor', backref='pagos')


# ==========================================================
#   MÓDULO DE CUENTAS POR PAGAR Y TESORERÍA
# ==========================================================

class CuentaPorPagar(db.Model):
    __tablename__ = 'cuentas_por_pagar'
    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    compra_id = db.Column(db.Integer, db.ForeignKey('compras.id'), nullable=False)
    numero_factura = db.Column(db.String(50))
    fecha = db.Column(db.DateTime, default=ahora_ve)
    monto_total_usd = db.Column(db.Numeric(10, 2), nullable=False)
    monto_abonado_usd = db.Column(db.Numeric(10, 2), default=Decimal('0.00'))
    saldo_pendiente_usd = db.Column(db.Numeric(10, 2), nullable=False)
    estatus = db.Column(db.String(20), default='Pendiente')
    proveedor = db.relationship('Proveedor', backref=db.backref('cuentas_por_pagar', lazy=True))
    compra = db.relationship('Compra', backref=db.backref('cuenta_por_pagar', uselist=False))
    abonos = db.relationship('AbonoCuentaPorPagar', backref='cuenta', lazy=True)

    @hybrid_property
    def fecha_emision(self):
        return self.fecha

    @fecha_emision.expression
    def fecha_emision(cls):
        return cls.fecha

    @hybrid_property
    def estado(self):
        return self.estatus

    @estado.expression
    def estado(cls):
        return cls.estatus


class AbonoCuentaPorPagar(db.Model):
    __tablename__ = 'abonos_cuentas_por_pagar'
    id = db.Column(db.Integer, primary_key=True)
    cuenta_id = db.Column(db.Integer, db.ForeignKey('cuentas_por_pagar.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    monto_usd = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago = db.Column(db.String(50))
    referencia = db.Column(db.String(100))
    descripcion = db.Column(db.String(200))


class AuditoriaInventario(db.Model):
    __tablename__ = 'auditoria_inventario'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, nullable=False)
    usuario_nombre = db.Column(db.String(100))
    producto_id = db.Column(db.Integer, nullable=False)
    producto_nombre = db.Column(db.String(200))
    accion = db.Column(db.String(50))
    cantidad_antes = db.Column(db.Numeric(12, 3), default=Decimal('0.000'))
    cantidad_despues = db.Column(db.Numeric(12, 3), default=Decimal('0.000'))
    fecha = db.Column(db.DateTime, default=ahora_ve)


# ==========================================================
#   SISTEMA DE USUARIOS Y SEGURIDAD 🔒
# ==========================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='cajero')
    
    # Nuevos campos para Seguridad y Google Sign-In 🔒
    email = db.Column(db.String(100), unique=True, nullable=True)
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    nombre_completo = db.Column(db.String(150), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=True)

    cliente = db.relationship('Cliente', backref='usuario', uselist=False)
    proveedor = db.relationship('Proveedor', backref='usuario', uselist=False)


# ==========================================================
#   FASE 5: MOVIMIENTOS DE CAJA 💰
# ==========================================================

class MovimientoCaja(db.Model):
    __tablename__ = 'movimientos_caja'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    tipo_caja = db.Column(db.String(30), nullable=False)
    tipo_movimiento = db.Column(db.String(10), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    monto = db.Column(db.Numeric(15, 2), nullable=False)
    tasa_dia = db.Column(db.Numeric(15, 2), default=Decimal('60.00'))
    descripcion = db.Column(db.String(200))
    modulo_origen = db.Column(db.String(50))
    referencia_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    usuario = db.relationship('User', backref='movimientos')

    def __repr__(self):
        return f'<Movimiento {self.tipo_movimiento} - {self.monto}>'


class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, procesado, cancelado
    observacion = db.Column(db.Text)
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True, cascade="all, delete-orphan")
    cliente = db.relationship('Cliente', backref='pedidos_portal')

class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedidos'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Numeric(12, 3), nullable=False)
    producto = db.relationship('Producto', backref='items_pedidos', lazy=True)


# ==========================================================
#   SISTEMA DE PUBLICIDAD Y FEEDBACK / QUEJAS (MINI-APPS)
# ==========================================================

class Publicidad(db.Model):
    __tablename__ = 'publicidades'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), default='Publicidad')
    descripcion = db.Column(db.String(255))
    archivo_url = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), default='imagen') # 'imagen', 'video'
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=ahora_ve)

class QuejaSugerencia(db.Model):
    __tablename__ = 'quejas_sugerencias'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Puede ser anonimo en caso extremo, pero referenciará al cliente
    tipo = db.Column(db.String(50), default='Queja') # 'Queja', 'Sugerencia', 'Otro'
    mensaje = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.DateTime, default=ahora_ve)
    leido = db.Column(db.Boolean, default=False)
    usuario = db.relationship('User', backref='quejas_enviadas')
from flask import Flask, render_template, redirect, url_for, flash, request, session
from models import db, TasaBCV, Producto, LiquidacionCiudad, Proveedor, MovimientoProductor, ahora_ve, hoy_ve, User
from datetime import datetime # Mantener para datetime.now() en set_tasa_bcv si es necesario
from decimal import Decimal
from sqlalchemy import func, desc
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth
from routes.portal import portal_bp
import logging
import pytz
import os
from dotenv import load_dotenv

# Cargar variables de entorno (para CLIENT_ID y CLIENT_SECRET de Google) 🔐
load_dotenv()

# Blueprints
from routes.clientes import clientes_bp
from routes.proveedores import proveedores_bp
from routes.pos import pos_bp
from routes.inventario import inventario_bp
from routes.compras import compras_bp
from routes.cierre import cierre_bp
from routes.historial import historial_bp
from routes.reportes import reportes_bp
from routes.contabilidad import contabilidad_bp
from routes.ia_mercado import ia_mercado_bp
from routes.ia_kalu import ia_kalu_bp
from routes.productores import productores_bp
from routes.auth import auth_bp
from routes.usuarios import usuarios_bp
from routes.caja import caja_bp
from routes.dueno import dueno_bp
from cargar_excel import cargar_bp
from routes.marketing import marketing_bp

# ============================================================
# ⏰ ZONA HORARIA VENEZUELA
# ============================================================
VE_TZ = pytz.timezone('America/Caracas')
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kalu_master.db'
app.config['SECRET_KEY'] = 'kalu_secret'
app.config['SESSION_COOKIE_NAME'] = 'kalu_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True # En producción, SECRET_KEY debe ser una variable de entorno y SESSION_COOKIE_SECURE = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_PERMANENT'] = False
app.config['REMEMBER_COOKIE_DURATION'] = 0

logging.basicConfig(level=logging.ERROR)
log = logging.getLogger('KALU')

# ============================================================
# 🔒 CONFIGURACIÓN DE SEGURIDAD (FLASK-LOGIN)
# ============================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = "⚠️ Por seguridad, debes iniciar sesión."
login_manager.login_message_category = "warning"

# ============================================================
# 🌐 CONFIGURACIÓN GOOGLE OAUTH2 (Authlib)
# ============================================================
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return db.session.get(User, int(user_id))

# ============================================================
# INICIALIZACIÓN DE BASE DE DATOS
# ============================================================
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

# ============================================================
# REGISTRO DE BLUEPRINTS
# ============================================================
app.register_blueprint(clientes_bp)
app.register_blueprint(proveedores_bp)
app.register_blueprint(pos_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(compras_bp)
app.register_blueprint(cierre_bp)
app.register_blueprint(historial_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(contabilidad_bp)
app.register_blueprint(ia_mercado_bp)
app.register_blueprint(ia_kalu_bp)
app.register_blueprint(productores_bp)
app.register_blueprint(cargar_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(caja_bp)
app.register_blueprint(dueno_bp)
app.register_blueprint(portal_bp)
app.register_blueprint(marketing_bp)

# ============================================================
# RUTAS PRINCIPALES Y ERRORES
# ============================================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback() # Prevenir bloqueos si hubo un error en DB
    return render_template('500.html'), 500

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if current_user.role in ['admin', 'cajero']:
        return redirect(url_for('pos.pos'))

    if current_user.role == 'cliente':
        return redirect(url_for('portal.mi_deuda'))

    if current_user.role == 'productor':
        return redirect(url_for('portal.mi_libreta'))

    return redirect(url_for('auth.login'))

@app.context_processor
def inject_tasa_actual():
    try:
        hoy = hoy_ve()
        tasa_hoy = TasaBCV.query.filter_by(fecha=hoy).first()
        if tasa_hoy:
            return dict(tasa_actual=float(tasa_hoy.valor), alerta_tasa=False)
        else:
            ultima = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
            valor = float(ultima.valor) if ultima else 0.0
            return dict(tasa_actual=valor, alerta_tasa=True)
    except Exception as e:
        log.error(f"Error al inyectar tasa actual: {e}")
        return dict(tasa_actual=0.0, alerta_tasa=True)

@app.route('/set_tasa_bcv', methods=['GET', 'POST'])
def set_tasa_bcv():
    if request.method == 'POST':
        nuevo_valor = request.form.get('valor')
        if nuevo_valor:
            try:
                valor_decimal = Decimal(str(nuevo_valor).replace(',', '.'))
                hoy = hoy_ve()
                tasa_hoy = TasaBCV.query.filter_by(fecha=hoy).first()

                if tasa_hoy:
                    tasa_hoy.valor = valor_decimal
                else:
                    nueva_tasa = TasaBCV(fecha=hoy, valor=valor_decimal)
                    db.session.add(nueva_tasa)

                db.session.commit()
                flash("¡Tasa actualizada correctamente!", "success")
                return redirect(url_for('index'))

            except Exception as e:
                db.session.rollback()
                flash(f"Error al guardar: {str(e)}", "danger")

    tasa_actual = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
    return render_template(
        'set_tasa.html',
        tasa=tasa_actual,
        fecha=ahora_ve().strftime('%d/%m/%Y')
    )

@app.route('/liquidar_queso_ciudad', methods=['POST'])
def liquidar_queso_ciudad():
    kilos = Decimal(request.form.get('kilos', '0'))
    precio_vta = Decimal(request.form.get('precio_vta', '0'))
    gastos = Decimal(request.form.get('gastos', '0'))
    metodo = request.form.get('metodo_pago', 'Efectivo')

    queso = Producto.query.filter(Producto.nombre.ilike('%Queso%')).first()

    if not queso:
        flash("Error: No se encontró el producto 'Queso' en el inventario.", "danger")
        return redirect(url_for('inventario.lista_inventario'))

    if queso.stock < kilos:
        flash(f"Error: Stock insuficiente. Solo tienes {queso.stock}kg.", "warning")
        return redirect(url_for('inventario.lista_inventario'))

    ingreso_bruto = kilos * precio_vta
    costo_total = kilos * queso.costo_usd
    utilidad_neta = ingreso_bruto - costo_total - gastos

    queso.stock -= kilos

    nueva_liq = LiquidacionCiudad(
        kilos_vendidos=kilos,
        precio_venta_usd=precio_vta,
        ingreso_bruto_usd=ingreso_bruto,
        gastos_operativos_usd=gastos,
        utilidad_neta_usd=utilidad_neta,
        metodo_pago=metodo
    )

    try:
        db.session.add(nueva_liq)
        db.session.commit()
        flash(f"¡Liquidación registrada! Utilidad neta: ${utilidad_neta:.2f}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al guardar: {str(e)}", "danger")

    return redirect(url_for('reportes.reportes'))

# ============================================================
# RUTA DEL TICKET TÉRMICO 58mm
# ============================================================
@app.route('/ticket/<int:venta_id>')
@login_required
def ver_ticket(venta_id):
    from models import Venta
    venta = Venta.query.get_or_404(venta_id)
    
    es_primera_compra = False
    if venta.cliente_id:
        count = Venta.query.filter_by(cliente_id=venta.cliente_id).count()
        if count == 1:
            es_primera_compra = True
            
    return render_template('ticket_58mm.html', venta=venta, cajero=current_user.username, es_primera_compra=es_primera_compra)

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("       🚀 SISTEMA KALU 2.0 - ¡DESPEGANDO! 🚀")
    print("=" * 50)
    print(" ✅ Base de Datos: kalu_master.db")
    print(" ✅ Estado:        OPERATIVO")
    print(" ✅ Puerto:        5002")
    print(" ✅ Modo:          DEBUG ACTIVADO")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5002, debug=True)
from flask import Flask, render_template, redirect, url_for, flash, request, session
from models import db, TasaBCV, Producto, LiquidacionCiudad, Proveedor, MovimientoProductor, ahora_ve, hoy_ve, User
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
from utils import seguro_decimal

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
from routes.herramientas import herramientas_bp

# ============================================================
# ⏰ ZONA HORARIA VENEZUELA
# ============================================================
VE_TZ = pytz.timezone('America/Caracas')
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# Configuración de Base de Datos
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'instance', 'kalu_master.db')}"

# 🔒 SEGURIDAD (Google Standards)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'kalu_fallback_secret')
app.config['SESSION_COOKIE_NAME'] = 'kalu_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Si estamos en producción (GCP), forzamos cookies seguras para cumplir con Google OAuth
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('ENV') == 'production'
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
login_manager.login_view = 'auth.ingresar'
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
    user = db.session.get(User, int(user_id))
    if user and not getattr(user, 'activo', True):
        return None
    return user

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
app.register_blueprint(herramientas_bp)

# ============================================================
# RUTAS PRINCIPALES Y ERRORES
# ============================================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    import traceback
    log.error(f"❌ ERROR 500: {str(error)}")
    log.error(traceback.format_exc())
    db.session.rollback()
    return render_template('500.html'), 500

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.ingresar'))

    if current_user.role in ['admin', 'cajero']:
        return redirect(url_for('pos.pos'))

    if current_user.role == 'cliente':
        return redirect(url_for('portal.mi_deuda'))

    if current_user.role == 'productor':
        return redirect(url_for('portal.mi_libreta'))

    if current_user.role == 'dueno':
        return redirect(url_for('dueno.dashboard'))

    return redirect(url_for('auth.ingresar'))

@app.context_processor
def inject_tasa_actual():
    try:
        hoy = hoy_ve()
        tasa_hoy = TasaBCV.query.filter_by(fecha=hoy).first()
        if tasa_hoy:
            return dict(tasa_actual=tasa_hoy.valor, alerta_tasa=False)
        else:
            ultima = TasaBCV.query.order_by(TasaBCV.fecha.desc()).first()
            valor = ultima.valor if ultima else Decimal('0.00')
            return dict(tasa_actual=valor, alerta_tasa=True)
    except Exception as e:
        log.error(f"Error al inyectar tasa actual: {e}")
        return dict(tasa_actual=Decimal('0.00'), alerta_tasa=True)

@app.route('/set_tasa_bcv', methods=['GET', 'POST'])
def set_tasa_bcv():
    if request.method == 'POST':
        nuevo_valor = request.form.get('valor')
        if nuevo_valor:
            try:
                valor_decimal = seguro_decimal(nuevo_valor)
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
    kilos = seguro_decimal(request.form.get('kilos'))
    precio_vta = seguro_decimal(request.form.get('precio_vta'))
    gastos = seguro_decimal(request.form.get('gastos'))
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


if __name__ == '__main__':
    import socket
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    local_ip = get_local_ip()
    port = int(os.environ.get("PORT", 5002))

    log.info("\n" + "#" * 30)
    log.info("  KALUNEVA2024 - OPERATIVO")
    log.info(" " + "#" * 30)
    log.info(f" [OK] Acceso Local:  http://localhost:{port}")
    log.info(f" [OK] En Red (CEL): http://{local_ip}:{port}")
    log.info(" [OK] Base Datos:   kalu_master.db")
    log.info(" [OK] PIN POS:      1234 (Edit en .env)")
    log.info("=" * 30 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=True)
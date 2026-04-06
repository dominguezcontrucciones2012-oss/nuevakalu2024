from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'cliente':
            return redirect(url_for('portal.mi_deuda'))
        elif current_user.role == 'productor':
            return redirect(url_for('portal.mi_libreta'))
        return redirect(url_for('pos.pos'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f"👋 ¡Bienvenido de nuevo, {user.username}!", "success")
            
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user.role == 'cliente':
                return redirect(url_for('portal.mi_deuda'))
            elif user.role == 'productor':
                return redirect(url_for('portal.mi_libreta'))
            else:
                return redirect(url_for('pos.pos'))
        else:
            flash("❌ Usuario o contraseña incorrectos.", "danger")
            
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("🔒 Sesión cerrada correctamente.", "info")
    return redirect(url_for('auth.login'))

# ============================================================
# 🌐 GOOGLE LOGIN ROUTES
# ============================================================

@auth_bp.route('/login/google')
def login_google():
    from app import google
    # Si estamos en el dominio oficial, forzamos HTTPS.
    # Si estamos probando localmente (127.0.0.1 o localhost), dejamos que Flask decida.
    scheme = 'https' if not request.host.startswith('127.0.0.1') and not request.host.startswith('localhost') else 'http'
    redirect_uri = url_for('auth.callback_google', _external=True, _scheme=scheme)
    # 🚨 SEGURO EXTRA: Forzamos a Google a preguntar qué cuenta usar siempre (prompt='select_account')
    return google.authorize_redirect(redirect_uri, prompt='select_account')

@auth_bp.route('/callback_google') # 👈 Nombre simplificado para la interna
def callback_google():
    from app import google
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            # Reintentar extraer de id_token si userinfo falla
            user_info = google.parse_id_token(token, nonce=None)

        if not user_info:
            flash("❌ No se pudo extraer información del perfil de Google.", "danger")
            return redirect(url_for('auth.login'))

        email = user_info.get('email')
        google_id = user_info.get('sub')

        # Buscar usuario administrativo por email
        user = User.query.filter_by(email=email).first()

        if user:
            user.google_id = google_id
            db.session.commit()
            
            login_user(user)
            flash(f"👋 Acceso seguro vía Google: {user.username}", "success")
            
            if user.role in ['admin', 'supervisor', 'cajero']:
                return redirect(url_for('pos.pos'))
            return redirect(url_for('portal.mi_deuda'))
        else:
            flash(f"⛔ ACCESO DENEGADO: El correo {email} NO TIENE PERMISO en KALU. Vincúlalo en la gestión de usuarios primero.", "danger")
            return redirect(url_for('auth.login'))
            
    except Exception as e:
        flash(f"❌ Error en la autenticación de Google: {str(e)}", "danger")
        return redirect(url_for('auth.login'))
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/politica-privacidad')
def privacidad():
    return render_template('privacidad.html')

@auth_bp.route('/terminos-servicio')
def terminos():
    return render_template('terminos.html')

@auth_bp.route('/ingresar', methods=['GET', 'POST'])
def ingresar():
    if current_user.is_authenticated:
        if current_user.role == 'cliente':
            return redirect(url_for('portal.mi_deuda'))
        elif current_user.role == 'productor':
            return redirect(url_for('portal.mi_libreta'))
        return redirect(url_for('pos.pos'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        
        # Buscamos por username exacto o email
        user = User.query.filter((User.username == username) | (User.email == username)).first()
        
        # Si no lo encontramos, intentamos normalizar (útil para Cédulas/RIF con guiones)
        if not user:
            username_norm = "".join(filter(str.isalnum, username)).upper()
            user = User.query.filter(User.username == username_norm).first()
        
        if user and check_password_hash(user.password, password):
            # 🔓 ACCESO RESTAURADO: Se permite acceso con contraseña mientras se estabiliza Google
            # if user.role in ['admin', 'dueno', 'cajero', 'supervisor']:
            #     flash("🔒 Seguridad KALU: El personal administrativo debe ingresar exclusivamente con el botón de Google.", "warning")
            #     return redirect(url_for('auth.ingresar'))

            login_user(user)
            flash(f"👋 ¡Bienvenido de nuevo, {user.username}!", "success")
            
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user.role == 'cliente':
                return redirect(url_for('portal.mi_deuda'))
            elif user.role == 'productor':
                return redirect(url_for('portal.mi_libreta'))
            
            return redirect(url_for('pos.pos'))
        else:
            flash("❌ Usuario o contraseña incorrectos.", "danger")
            
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("🔒 Sesión cerrada correctamente.", "info")
    return redirect(url_for('auth.ingresar'))

# ============================================================
# 🌐 GOOGLE LOGIN ROUTES
# ============================================================

@auth_bp.route('/ingresar/google')
@auth_bp.route('/login/google')
def ingresar_google():
    from app import google
    # Flask genera automáticamente la URL completa con _external=True
    # respetando el host y puerto configurados o detectados por ProxyFix.
    redirect_uri = url_for('auth.callback_google', _external=True)
    return google.authorize_redirect(redirect_uri, prompt='select_account')

@auth_bp.route('/auth/callback-google') # 👈 Ruta única y estandarizada
def callback_google():
    from app import google
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            user_info = google.parse_id_token(token, nonce=None)

        if not user_info:
            flash("❌ No se pudo extraer información del perfil de Google.", "danger")
            return redirect(url_for('auth.ingresar'))

        email = user_info.get('email')
        google_id = user_info.get('sub')

        # Buscar usuario por email
        user = User.query.filter_by(email=email).first()

        if user:
            user.google_id = google_id
            db.session.commit()
            
            login_user(user)
            flash(f"👋 Acceso seguro vía Google: {user.username}", "success")
            
            if user.role == 'admin':
                return redirect(url_for('reportes.panel_reportes'))
            elif user.role == 'dueno':
                return redirect(url_for('dueno.dashboard'))
            elif user.role in ['cajero', 'supervisor']:
                return redirect(url_for('pos.pos'))
            elif user.role == 'cliente':
                return redirect(url_for('portal.mi_deuda'))
            elif user.role == 'productor':
                return redirect(url_for('portal.mi_libreta'))
            
            return redirect(url_for('pos.pos'))
        else:
            flash(f"⛔ ACCESO DENEGADO: El correo {email} NO TIENE PERMISO en KALU. Vincúlalo en la gestión de usuarios primero.", "danger")
            return redirect(url_for('auth.ingresar'))
            
    except Exception as e:
        import traceback
        print(f"Error Google Auth: {str(e)}")
        print(traceback.format_exc())
        flash(f"❌ Error en la autenticación de Google. Verifica tu conexión.", "danger")
        return redirect(url_for('auth.ingresar'))
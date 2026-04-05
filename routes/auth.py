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
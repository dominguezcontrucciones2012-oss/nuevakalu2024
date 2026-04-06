from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'cajero']:
            flash("🚫 Acceso denegado. Esta sección es solo para personal autorizado.", "danger")
            if current_user.is_authenticated and current_user.role == 'cliente':
                return redirect(url_for('portal.mi_deuda'))
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

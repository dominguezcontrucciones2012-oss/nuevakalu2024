from app import app
from routes.inventario import reporte_inventario
from flask import url_for
from models import db, User

with app.app_context():
    # Simulate a request
    with app.test_request_context('/reporte_inventario'):
        try:
            # We need a logged in user for solo_admin
            user = User.query.filter_by(role='admin').first()
            from flask_login import login_user
            login_user(user)
            res = reporte_inventario()
            print("Successfully rendered")
        except Exception as e:
            import traceback
            print(f"ERROR: {e}")
            traceback.print_exc()

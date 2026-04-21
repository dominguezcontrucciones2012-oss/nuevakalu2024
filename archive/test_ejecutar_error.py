from app import app
from routes.cierre import ejecutar_cierre
from flask import request, session
from models import db, User, TasaBCV
from decimal import Decimal
import traceback

with app.app_context():
    user = User.query.first()
    if not user:
        print("Creando usuario temporal...")
        user = User(username="testadmin", role="admin")
        db.session.add(user)
        db.session.commit()
    
    # Asegurar que haya una tasa
    if not TasaBCV.query.first():
        db.session.add(TasaBCV(fecha=datetime.now().date(), valor=Decimal('36.50')))
        db.session.commit()

with app.test_request_context('/ejecutar_cierre', method='POST', data={
    'real_usd': '0',
    'real_bs': '0',
    'real_pago_movil': '0',
    'real_biopago': '0',
    'real_transferencia': '0',
    'real_debito': '0',
    'observaciones': 'Test'
}):
    session['_user_id'] = user.id
    from flask_login import login_user
    with app.app_context():
        # Login mock
        from flask_login import login_user
        login_user(user)
        
        try:
            print(f"Simulando ejecutar_cierre con usuario {user.username}...")
            res = ejecutar_cierre()
            print("Resultado:", res)
        except Exception as e:
            print(f"ERROR DETECTADO: {e}")
            traceback.print_exc()

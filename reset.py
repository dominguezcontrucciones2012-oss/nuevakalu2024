from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    nuevo = User(username='kalu_test', password=generate_password_hash('1234'), role='admin')
    db.session.add(nuevo)
    db.session.commit()
    print('✅ USUARIO CREADO: kalu_test | CLAVE: 1234')
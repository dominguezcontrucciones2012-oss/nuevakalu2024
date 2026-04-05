from app import app, db
from models import User
from werkzeug.security import generate_password_hash

def crear_usuario_maestro():
    with app.app_context():
        # 1. Buscamos si ya existe el admin
        admin_existente = User.query.filter_by(username='admin').first()
        
        if admin_existente:
            # Si existe, solo le actualizamos la clave por si acaso
            admin_existente.password = generate_password_hash('kalu2024', method='pbkdf2:sha256')
            admin_existente.role = 'admin'
            db.session.commit()
            print("✅ Usuario 'admin' actualizado con clave: kalu2024")
        else:
            # 2. Si no existe, lo creamos desde cero
            nuevo_admin = User(
                username='admin',
                password=generate_password_hash('kalu2024', method='pbkdf2:sha256'),
                role='admin'
            )
            db.session.add(nuevo_admin)
            db.session.commit()
            print("🚀 ¡USUARIO MAESTRO CREADO EXITOSAMENTE!")
            print("-----------------------------------------")
            print("👤 Usuario: admin")
            print("🔑 Clave:   kalu2024")
            print("-----------------------------------------")

if __name__ == '__main__':
    crear_usuario_maestro()
from app import app
from models import db, User
from werkzeug.security import generate_password_hash

def crear_maestro():
    with app.app_context():
        master = User.query.filter_by(username='maestro').first()
        if not master:
            master = User(
                username='maestro',
                password=generate_password_hash('maestro123'),
                role='dueno',
                nombre_completo='Usuario Maestro'
            )
            db.session.add(master)
            db.session.commit()
            print("Usuario 'maestro' creado con éxito.")
            print("Username: maestro")
            print("Password: maestro123")
            print("Rol: dueno")
        else:
            master.password = generate_password_hash('maestro123')
            master.role = 'dueno'
            db.session.commit()
            print("El usuario 'maestro' ya existía. La contraseña ha sido restablecida.")
            print("Username: maestro")
            print("Password: maestro123")
            print("Rol: dueno")

if __name__ == '__main__':
    crear_maestro()

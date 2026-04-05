from app import app, db
from models import User

def ver_usuarios():
    with app.app_context():
        usuarios = User.query.all()
        if not usuarios:
            print("⚠️ No hay usuarios en la base de datos.")
        else:
            print("📋 Usuarios en la base de datos:")
            for u in usuarios:
                print(f"- id={u.id}, username={u.username}, role={u.role}")

if __name__ == "__main__":
    ver_usuarios()
from app import app
from models import db, User

def check_special_users():
    with app.app_context():
        print("\n--- ESTADO DE USUARIOS ADMINISTRATIVOS ---")
        usernames = ['maestro', 'dominguezcontrucciones', 'deisycorro', 'dueno']
        users = User.query.filter(User.username.in_(usernames)).all()
        
        found = [u.username for u in users]
        for u in users:
            print(f"Usuario: {u.username} | Rol: {u.role} | Activo: {u.activo}")
            
        for name in usernames:
            if name not in found:
                print(f"Usuario: {name} | No encontrado en la base de datos.")
        print("------------------------------------------\n")

if __name__ == '__main__':
    check_special_users()

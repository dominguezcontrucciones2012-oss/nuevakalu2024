import sys
import os

# Asegurar que el directorio raíz esté en el path para importar app y models
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from app import app
    from models import db, User
    
    with app.app_context():
        print("\n--- LISTADO DE USUARIOS REGISTRADOS EN KALU 2.0 ---\n")
        users = User.query.all()
        header = f"{'ID':<4} | {'Usuario':<20} | {'Email':<25} | {'Rol':<12} | {'PIN':<6}"
        print(header)
        print("-" * len(header))
        for u in users:
            # Manejar posibles valores None
            uname = u.username if u.username else "---"
            uemail = u.email if u.email else "---"
            uroll = u.role if u.role else "---"
            upin = u.pin if u.pin else "N/A"
            
            print(f"{u.id:<4} | {uname:<20} | {uemail:<25} | {uroll:<12} | {upin:<6}")
        print(f"\nTotal: {len(users)} usuarios.\n")
except ImportError as e:
    print(f"❌ Error de importación (FROM): {e}")
    print("Asegúrate de ejecutar este script desde la raíz del proyecto.")
except Exception as e:
    print(f"❌ Error inesperado: {e}")

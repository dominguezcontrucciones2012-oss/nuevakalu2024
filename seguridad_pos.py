from app import app
from models import db
from sqlalchemy import text

def asegurar_columna():
    with app.app_context():
        try:
            # Solo agrega la columna si no existe, NO toca tus datos
            db.session.execute(text("ALTER TABLE ventas ADD COLUMN productor_id INTEGER REFERENCES proveedores(id)"))
            db.session.commit()
            print("✅ Sistema blindado: Columna productor_id lista.")
        except Exception as e:
            db.session.rollback()
            print(f"ℹ️ El sistema ya está protegido: {e}")

if __name__ == "__main__":
    asegurar_columna()
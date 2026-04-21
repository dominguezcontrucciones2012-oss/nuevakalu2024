from app import app
from models import db, User

def listar():
    with app.app_context():
        users = User.query.all()
        for u in users:
            print(f"User: {u.username}, Role: {u.role}, Email: {u.email}")

if __name__ == '__main__':
    listar()

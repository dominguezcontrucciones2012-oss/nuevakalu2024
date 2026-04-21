from app import app
from models import db, User
from werkzeug.security import generate_password_hash

def fix_accounts():
    with app.app_context():
        # Setup dominguezcontrucciones@gmail.com as dueno
        d_email = 'dominguezcontrucciones@gmail.com'
        d_user = User.query.filter_by(email=d_email).first()
        if d_user:
            d_user.role = 'dueno'
            print(f"Updated {d_user.username} (email: {d_email}) to role: dueno")
        else:
            new_d = User(
                username='dominguez_dueno',
                email=d_email,
                password=generate_password_hash('kalu1234'),
                role='dueno'
            )
            db.session.add(new_d)
            print(f"Created dominguez_dueno with email {d_email} and role: dueno")

        # Setup deisycorro77@gmail.com as admin
        deisy_email = 'deisycorro77@gmail.com'
        deisy_user = User.query.filter_by(email=deisy_email).first()
        if deisy_user:
            deisy_user.role = 'admin'
            print(f"Updated {deisy_user.username} (email: {deisy_email}) to role: admin")
        else:
            new_deisy = User(
                username='deisy corro',
                email=deisy_email,
                password=generate_password_hash('kalu1234'),
                role='admin'
            )
            db.session.add(new_deisy)
            print(f"Created deisy corro with email {deisy_email} and role: admin")

        db.session.commit()

if __name__ == '__main__':
    fix_accounts()

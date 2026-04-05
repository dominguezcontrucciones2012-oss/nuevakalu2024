from app import app
from models import db, User, Cliente
from werkzeug.security import generate_password_hash

with app.app_context():
    creados = 0
    saltados = 0

    for c in Cliente.query.all():
        if not c.cedula or len(c.cedula.strip()) < 4:
            print(f"[SIN CEDULA VALIDA] {c.nombre}")
            saltados += 1
            continue

        existente_por_cliente = User.query.filter_by(cliente_id=c.id).first()
        if existente_por_cliente:
            print(f"[YA TIENE USUARIO] {c.nombre} -> {existente_por_cliente.username}")
            saltados += 1
            continue

        username = c.cedula.strip()
        password_plana = username[-4:]

        existente_username = User.query.filter_by(username=username).first()
        if existente_username:
            print(f"[USERNAME YA EXISTE] {c.nombre} -> {username}")
            saltados += 1
            continue

        nuevo = User(
            username=username,
            password=generate_password_hash(password_plana),
            role='cliente',
            cliente_id=c.id
        )

        db.session.add(nuevo)
        print(f"[CREADO] {c.nombre} -> usuario: {username} | clave: {password_plana}")
        creados += 1

    db.session.commit()

    print(f"\nUsuarios creados: {creados}")
    print(f"Saltados: {saltados}")
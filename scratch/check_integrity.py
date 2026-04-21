import os
import sys

# Add root to sys.path
sys.path.append(os.getcwd())

from app import app
from models import db, User, Cliente, Proveedor

with app.app_context():
    # 1. Check for duplicate usernames
    from sqlalchemy import func
    dups = db.session.query(User.username, func.count(User.username)).group_by(User.username).having(func.count(User.username) > 1).all()
    if dups:
        print(f"ERROR: Duplicate usernames found: {dups}")
    else:
        print("No duplicate usernames in User table.")

    # 2. Check for duplicate cedulas in Cliente
    c_dups = db.session.query(Cliente.cedula, func.count(Cliente.cedula)).group_by(Cliente.cedula).having(func.count(Cliente.cedula) > 1).all()
    if c_dups:
        print(f"WARNING: Duplicate cedulas in Cliente: {c_dups}")
    else:
        print("No duplicate cedulas in Cliente table.")

    # 3. Check for users with same CID or PID
    cid_dups = db.session.query(User.cliente_id, func.count(User.cliente_id)).filter(User.cliente_id != None).group_by(User.cliente_id).having(func.count(User.cliente_id) > 1).all()
    if cid_dups:
        print(f"ERROR: Multiple users linked to same Cliente ID: {cid_dups}")
    
    pid_dups = db.session.query(User.proveedor_id, func.count(User.proveedor_id)).filter(User.proveedor_id != None).group_by(User.proveedor_id).having(func.count(User.proveedor_id) > 1).all()
    if pid_dups:
        print(f"ERROR: Multiple users linked to same Proveedor ID: {pid_dups}")

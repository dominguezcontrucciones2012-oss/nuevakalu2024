import sys
import os
sys.path.append(os.getcwd())

from app import app
from flask import url_for

with app.app_context():
    with app.test_request_context(base_url='http://localhost:5002'):
        print(f"Ingresar Google: {url_for('auth.ingresar_google')}")
        print(f"Callback Google: {url_for('auth.callback_google')}")
        
        # List all routes to be sure
        print("\n--- TODAS LAS RUTAS REGISTRADAS ---")
        rules = sorted(list(app.url_map.iter_rules()), key=lambda x: str(x))
        for rule in rules:
            print(f"{rule.endpoint}: {rule}")

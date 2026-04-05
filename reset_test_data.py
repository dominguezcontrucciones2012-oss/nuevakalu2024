from app import app
from models import db
from sqlalchemy import text

def clean():
    with app.app_context():
        tables = [
            'detalles_ventas', 'ventas', 'detalles_pedidos', 'pedidos', 
            'historial_pagos', 'pagos_reportados', 'detalles_asientos', 'asientos', 
            'movimientos_caja', 'cierres_caja', 'movimientos_productores', 
            'pagos_productor', 'auditoria_inventario', 'abonos_cuentas_por_pagar', 
            'cuentas_por_pagar', 'compras_detalles', 'compras'
        ]
        print("Iniciando limpieza...")
        for table in tables:
            try:
                db.session.execute(text(f"DELETE FROM {table}"))
                print(f"Borrando {table}...")
            except Exception as e:
                print(f"Omitiendo {table}: {e}")
        
        # Resetear balances
        db.session.execute(text("UPDATE clientes SET saldo_usd=0, saldo_bs=0, puntos=0, documentos=0"))
        db.session.execute(text("UPDATE proveedores SET saldo_pendiente_usd=0"))
        
        db.session.commit()
        print("✅ Todo limpio.")

if __name__ == "__main__":
    clean()

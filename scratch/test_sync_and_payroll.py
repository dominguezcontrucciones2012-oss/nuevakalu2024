import sys
import os
from datetime import datetime
from decimal import Decimal

# Añadir el directorio actual al path para importar app y modelos
sys.path.append(os.getcwd())

from app import app
from models import db, Proveedor, CuentaPorPagar, MovimientoProductor, MovimientoCaja, Compra, User

def test_producer_cxp_sync():
    print("\n--- TEST 1: SINCRONIZACION PRODUCTOR -> CXP (FIFO) ---")
    with app.app_context():
        # Utilizaremos un nombre unico para evitar interferencias
        p_name = "TEST_FIFO_SYNC"
        productor = Proveedor.query.filter_by(nombre=p_name).first()
        if not productor:
            productor = Proveedor(nombre=p_name, rif="V-SYNC-TEST", es_productor=True, saldo_pendiente_usd=0)
            db.session.add(productor)
            db.session.commit()

        print(f"Utilizando productor: {productor.nombre} (ID: {productor.id})")
        
        # Limpiar facturas viejas de este test si existen
        CuentaPorPagar.query.filter_by(proveedor_id=productor.id).delete()
        productor.saldo_pendiente_usd = 0
        db.session.commit()

        # 1. Crear dos facturas: Una de $100 y otra de $50
        c1 = Compra(proveedor_id=productor.id, numero_factura="FAC-1", total_usd=100)
        c2 = Compra(proveedor_id=productor.id, numero_factura="FAC-2", total_usd=50)
        db.session.add_all([c1, c2])
        db.session.flush()

        f1 = CuentaPorPagar(proveedor_id=productor.id, compra_id=c1.id, numero_factura="FAC-1", monto_total_usd=100, saldo_pendiente_usd=100)
        f2 = CuentaPorPagar(proveedor_id=productor.id, compra_id=c2.id, numero_factura="FAC-2", monto_total_usd=50, saldo_pendiente_usd=50)
        db.session.add_all([f1, f2])
        productor.saldo_pendiente_usd = 150
        db.session.commit()
        print("OK: Creadas Factura 1 ($100) y Factura 2 ($50). Total deuda: $150.")

        # 2. Simular pago de $120. 
        # Deberia: Pagar FAC-1 completa ($100) y quedar $20 en FAC-2.
        monto_pago = Decimal('120.00')
        print(f"Registrando pago de ${monto_pago}...")
        
        facturas = CuentaPorPagar.query.filter(
            CuentaPorPagar.proveedor_id == productor.id,
            CuentaPorPagar.estatus.in_(['Pendiente', 'Parcial'])
        ).order_by(CuentaPorPagar.fecha.asc()).all()

        rem = monto_pago
        for f in facturas:
            if rem <= 0: break
            p = min(rem, f.saldo_pendiente_usd)
            f.saldo_pendiente_usd -= p
            f.monto_abonado_usd += p
            f.estatus = 'Pagado' if f.saldo_pendiente_usd <= 0 else 'Parcial'
            rem -= p
        
        productor.saldo_pendiente_usd -= monto_pago
        db.session.commit()

        # 3. Verificacion
        f1_new = CuentaPorPagar.query.filter_by(numero_factura="FAC-1").first()
        f2_new = CuentaPorPagar.query.filter_by(numero_factura="FAC-2").first()
        
        print(f"FAC-1: Saldo ${f1_new.saldo_pendiente_usd}, Estatus: {f1_new.estatus}")
        print(f"FAC-2: Saldo ${f2_new.saldo_pendiente_usd}, Estatus: {f2_new.estatus}")
        print(f"Saldo Libreta Productor: ${productor.saldo_pendiente_usd}")

        if f1_new.estatus == 'Pagado' and f2_new.saldo_pendiente_usd == 30:
            print("+++ SUCCESS: Sincronizacion FIFO Perfecta +++")
        else:
            print("--- FAILURE: La sincronizacion no fue exacta ---")

def test_worker_payroll_sync():
    print("\n--- TEST 2: NOMINA DE OBREROS CON COBRO DE DEUDA ---")
    with app.app_context():
        # Limpiar test anterior
        obrero = Proveedor.query.filter_by(nombre="OBRERO_PRUEBA").first()
        if not obrero:
            obrero = Proveedor(nombre="OBRERO_PRUEBA", rif="V0000", es_productor=True)
            db.session.add(obrero)
            db.session.commit()
        
        obrero.saldo_pendiente_usd = Decimal('-15.00')
        db.session.commit()
        print(f"Obrero: {obrero.nombre} | Deuda Inicial: ${obrero.saldo_pendiente_usd}")

        sueldo = Decimal('50.00')
        nuevo_saldo = obrero.saldo_pendiente_usd + sueldo # 35
        pago_real = max(Decimal('0'), nuevo_saldo) # 35
        
        obrero.saldo_pendiente_usd = nuevo_saldo - pago_real # 0
        db.session.commit()

        print(f"Sueldo: ${sueldo} | Pago Cash Real: ${pago_real} | Saldo Final: ${obrero.saldo_pendiente_usd}")
        
        if pago_real == 35 and obrero.saldo_pendiente_usd == 0:
            print("+++ SUCCESS: Nomina OK +++")
        else:
            print("--- FAILURE: Error en nomina ---")

if __name__ == "__main__":
    test_producer_cxp_sync()
    test_worker_payroll_sync()

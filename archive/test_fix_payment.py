
from app import app
from models import db, Proveedor, MovimientoProductor, MovimientoCaja, TasaBCV, Asiento, DetalleAsiento, CuentaContable
from decimal import Decimal
from datetime import datetime

def setup_test_balance(producer_id, amount_usd):
    with app.app_context():
        p = Proveedor.query.get(producer_id)
        if not p: return
        
        print(f"Seteando balance inicial para {p.nombre}: ${amount_usd}")
        
        # Simular Movimiento de Nomina (Haber)
        p.saldo_pendiente_usd += amount_usd
        db.session.add(MovimientoProductor(
            proveedor_id=p.id,
            tipo='NOMINA',
            descripcion=f"Prueba de Saldo Inicial: ${amount_usd}",
            haber=amount_usd,
            debe=0,
            saldo_momento=p.saldo_pendiente_usd,
            fecha=datetime.now()
        ))
        db.session.commit()

def test_payment_route_simulation(producer_id, amount_usd, metodo='EFECTIVO'):
    with app.app_context():
        # Simulamos la lógica de registrar_pago_productor sin el doble error
        p = Proveedor.query.get(producer_id)
        print(f"--- Realizando Pago de ${amount_usd} a {p.nombre} ---")
        
        tasa = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
        valor_tasa = tasa.valor if tasa else Decimal('40.00')
        monto_bs = amount_usd * valor_tasa
        
        # 1. Restar saldo (SOLO UNA VEZ AHORA)
        p.saldo_pendiente_usd -= amount_usd
        
        # 2. Registrar MovimientoProductor
        db.session.add(MovimientoProductor(
            proveedor_id=p.id,
            tipo='PAGO',
            descripcion=f"Pago de Prueba {metodo}",
            debe=amount_usd,
            haber=0,
            saldo_momento=p.saldo_pendiente_usd,
            fecha=datetime.now()
        ))
        
        # 3. Registrar MovimientoCaja
        db.session.add(MovimientoCaja(
            fecha=datetime.now(),
            tipo_caja='Caja USD' if metodo == 'EFECTIVO' else 'Caja Bs',
            tipo_movimiento='EGRESO',
            categoria='Pago Productor',
            monto=amount_usd if metodo == 'EFECTIVO' else monto_bs,
            tasa_dia=valor_tasa,
            descripcion=f"Pago Prueba a {p.nombre}",
            modulo_origen='TEST',
            user_id=1
        ))
        
        db.session.commit()
        print(f"Pago completado. Nuevo saldo de {p.nombre}: ${p.saldo_pendiente_usd}")

if __name__ == "__main__":
    # 1. Limpiar o asegurar un punto de partida
    # Andres (2), Diana (6)
    setup_test_balance(2, Decimal('50.00'))
    setup_test_balance(6, Decimal('50.00'))
    
    # 2. Realizar pagos
    test_payment_route_simulation(2, Decimal('30.00'))
    test_payment_route_simulation(6, Decimal('30.00'))
    
    print("\nTest finalizado. Ejecuta audit_producers_detailed.py para ver el historial.")

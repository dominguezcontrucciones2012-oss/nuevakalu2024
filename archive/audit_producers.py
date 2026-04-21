
from app import app
from models import db, MovimientoProductor, Proveedor, PagoProductor
from decimal import Decimal

def audit_producer(producer_id):
    with app.app_context():
        producer = Proveedor.query.get(producer_id)
        if not producer:
            print(f"Productor {producer_id} no encontrado.")
            return

        print(f"\n--- AUDITORIA PRODUCTOR: {producer.nombre} (ID: {producer_id}) ---")
        print(f"Saldo actual en DB: {producer.saldo_pendiente_usd}")

        movimientos = MovimientoProductor.query.filter_by(proveedor_id=producer_id).order_by(MovimientoProductor.id).all()
        
        calculated_balance = Decimal('0')
        print(f"{'ID':<5} | {'Fecha':<20} | {'Tipo':<15} | {'Debe':<10} | {'Haber':<10} | {'Saldo Momento':<15} | {'Calc Saldo'}")
        print("-" * 90)
        
        for m in movimientos:
            debe = m.debe or Decimal('0')
            haber = m.haber or Decimal('0')
            
            # En la libreta, 'haber' es lo que nos traen (nosotros debemos), 'debe' es lo que pagamos (reducimos deuda)
            # El saldo_pendiente_usd en Proveedor parece ser (Haber - Debe) acumulado.
            # Veamos la logica de MovimientoProductor:
            # registrar_entrega: haber=total_queso, debe=monto_pagado, saldo_momento=productor.saldo_pendiente_usd + (total_queso - monto_pagado)
            # registrar_pago_productor: debe=monto_usd, haber=0, saldo_momento=productor.saldo_pendiente_usd
            
            if m.tipo == 'ENTREGA_QUESO':
                 balance_change = haber - debe
            elif m.tipo == 'PAGO':
                 balance_change = -debe
            else:
                 balance_change = haber - debe # Por si acaso
            
            calculated_balance += balance_change
            print(f"{m.id:<5} | {str(m.fecha):<20} | {m.tipo:<15} | {debe:<10} | {haber:<10} | {m.saldo_momento:<15} | {calculated_balance}")

        print(f"\nSaldo calculado final: {calculated_balance}")
        print(f"Diferencia: {producer.saldo_pendiente_usd - calculated_balance}")

if __name__ == "__main__":
    audit_producer(2)
    audit_producer(6)

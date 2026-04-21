
from app import app
from models import db, MovimientoProductor, Proveedor, CuentaPorPagar
from decimal import Decimal

def audit_producer(producer_id):
    with app.app_context():
        producer = Proveedor.query.get(producer_id)
        if not producer:
            print(f"Productor {producer_id} no encontrado.")
            return

        print(f"\n--- AUDITORIA PRODUCTOR: {producer.nombre} (ID: {producer_id}) ---")
        print(f"Saldo actual en tabla Proveedor: {producer.saldo_pendiente_usd}")

        movimientos = MovimientoProductor.query.filter_by(proveedor_id=producer_id).order_by(MovimientoProductor.id).all()
        
        calculated_balance = Decimal('0')
        print(f"{'ID':<5} | {'Fecha':<20} | {'Tipo':<15} | {'Debe':<10} | {'Haber':<10} | {'Saldo Momento':<15} | {'Calc Saldo'}")
        print("-" * 100)
        
        for m in movimientos:
            debe = m.debe or Decimal('0')
            haber = m.haber or Decimal('0')
            
            # Ajuste de logica para el calculo
            calculated_balance += (haber - debe)
            
            print(f"{m.id:<5} | {str(m.fecha):<20} | {m.tipo:<15} | {debe:<10.2f} | {haber:<10.2f} | {m.saldo_momento:<15.2f} | {calculated_balance:<10.2f}")

        cxp_pendientes = CuentaPorPagar.query.filter_by(proveedor_id=producer_id).filter(CuentaPorPagar.saldo_pendiente_usd > 0).all()
        print(f"\nCuentas por Pagar (CXP) Pendientes:")
        total_cxp = Decimal('0')
        for cxp in cxp_pendientes:
            print(f"Factura: {cxp.numero_factura} | Saldo: {cxp.saldo_pendiente_usd}")
            total_cxp += cxp.saldo_pendiente_usd
        print(f"Total CXP Pendiente: {total_cxp}")

if __name__ == "__main__":
    audit_producer(2)
    audit_producer(6)

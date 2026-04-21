from app import app
from models import Venta, Asiento, DetalleAsiento
from decimal import Decimal

with app.app_context():
    v = Venta.query.get(17)
    if v:
        print(f"VENTA 17:")
        print(f"  Total: {v.total_usd}")
        print(f"  Pendiente: {v.saldo_pendiente_usd}")
        print(f"  Fiado: {v.es_fiado}")
        print(f"  USD Paid: {v.pago_efectivo_usd}")
        print(f"  BS Paid: {v.pago_efectivo_bs}")
        print(f"  PM Paid: {v.pago_movil_bs}")
        print(f"  TR Paid: {v.pago_transferencia_bs}")
        print(f"  DEB Paid: {v.pago_debito_bs}")
        
    a = Asiento.query.filter_by(referencia_tipo='VENTA', referencia_id=17).first()
    if a:
        print(f"\nASIENTO {a.id}:")
        for d in a.detalles:
            print(f"  - {d.cuenta.codigo}: Debe={d.debe_usd}, Haber={d.haber_usd}")
    else:
        print("\nNo asiento found for Venta 17")

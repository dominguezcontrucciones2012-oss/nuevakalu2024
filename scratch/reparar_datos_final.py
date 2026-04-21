from app import app
from models import db, Venta, Cliente, HistorialPago, TasaBCV
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('KALU.reparacion')

def ejecutar_reparacion():
    with app.app_context():
        logger.info("🚀 Iniciando reparación de datos...")

        # 1. REPARACIÓN VENTA 17
        v17 = Venta.query.get(17)
        if v17:
            logger.info(f"Corrigiendo Venta 17 (Total: {v17.total_usd}, Saldo: {v17.saldo_pendiente_usd})")
            # Si el total coincide con lo pagado en Bs (con tasa aproximada), y queremos que sea Fiado
            # pero el saldo es 0, significa que se marcó como pagada pero es fiado.
            # O quizás se pagó y el saldo debe ser 0.
            # Según el usuario, "no registra", tal vez debería tener saldo.
            if v17.saldo_pendiente_usd == 0 and v17.es_fiado:
                logger.info("Venta 17 es fiada pero tiene saldo 0. Verificando pagos...")
                # Si el pago en Bs es sospechosamente alto o bajo
                # Vamos a resetear el saldo pendiente al total si el usuario dice que no registra deuda
                # Pero primero veamos si hay un abono inicial.
                abono_inic = HistorialPago.query.filter_by(venta_id=17, metodo_pago='ABONO INICIAL').first()
                if not abono_inic:
                     logger.info("No hay abono inicial para Venta 17. Re-calculando deuda...")
                     v17.saldo_pendiente_usd = v17.total_usd
                     v17.pagada = False
            db.session.commit()

        # 2. AUDITORÍA GENERAL DE CLIENTES
        clientes = Cliente.query.all()
        tasa_obj = TasaBCV.query.order_by(TasaBCV.id.desc()).first()
        tasa = Decimal(str(tasa_obj.valor)) if tasa_obj else Decimal('1.0')

        for c in clientes:
            logger.info(f"Auditando cliente: {c.nombre} (ID: {c.id})")
            
            # Sumar todas las ventas fiadas
            ventas_fiadas = Venta.query.filter_by(cliente_id=c.id, es_fiado=True).all()
            total_deuda_ventas = sum(v.total_usd for v in ventas_fiadas)
            
            # Sumar todos los abonos (incluyendo iniciales)
            abonos = HistorialPago.query.filter_by(cliente_id=c.id).all()
            total_pagado = sum(a.monto_usd for a in abonos)
            
            saldo_calculado = (total_deuda_ventas - total_pagado).quantize(Decimal('0.01'))
            if saldo_calculado < 0: saldo_calculado = Decimal('0.00') # No permitir saldos negativos técnicos aquí
            
            if c.saldo_usd != saldo_calculado:
                logger.info(f"  ⚠️ Discrepancia en {c.nombre}: DB={c.saldo_usd} | Calculado={saldo_calculado}. Corrigiendo...")
                c.saldo_usd = saldo_calculado
                c.saldo_bs = (c.saldo_usd * tasa).quantize(Decimal('0.01'))
            
            # Sincronizar saldo de facturas individuales
            # Distribuir abonos entre facturas
            abono_disponible = total_pagado
            for v in sorted(ventas_fiadas, key=lambda x: x.fecha):
                if abono_disponible >= v.total_usd:
                    v.saldo_pendiente_usd = Decimal('0.00')
                    v.pagada = True
                    abono_disponible -= v.total_usd
                else:
                    v.saldo_pendiente_usd = (v.total_usd - abono_disponible).quantize(Decimal('0.01'))
                    v.pagada = False
                    abono_disponible = Decimal('0.00')

        db.session.commit()
        logger.info("✅ Reparación completada.")

if __name__ == "__main__":
    ejecutar_reparacion()

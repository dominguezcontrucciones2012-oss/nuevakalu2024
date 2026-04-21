import os
import sys
from datetime import datetime, date, timedelta
from sqlalchemy import func
from decimal import Decimal

# Add main dir to sys path for imports
sys.path.append(r"d:\nuevakalu2024")

from app import app
from models import db, Venta, DetalleVenta, Producto, Asiento, DetalleAsiento

def generar_reportes_para_ia():
    with app.app_context():
        # 1. ROTACIÓN DE PRODUCTOS (Histórico o últimos 30 días)
        # Productos con mayor rotación (más vendidos)
        print("=== ALTA ROTACION ===")
        mas_vendidos = db.session.query(
            Producto.nombre,
            func.sum(DetalleVenta.cantidad).label('total_vendido')
        ).join(DetalleVenta, Producto.id == DetalleVenta.producto_id)\
         .group_by(Producto.nombre)\
         .order_by(func.sum(DetalleVenta.cantidad).desc())\
         .limit(10).all()
        for p in mas_vendidos:
            print(f"- {p.nombre}: {p.total_vendido}")

        print("\n=== BAJA ROTACION ===")
        # Productos con menos rotacion (vendidos pero en menor cantidad, o sin ventas)
        # Consultar primero los menos vendidos excluyendo los que no se venden nada
        menos_vendidos = db.session.query(
            Producto.nombre,
            func.sum(DetalleVenta.cantidad).label('total_vendido')
        ).join(DetalleVenta, Producto.id == DetalleVenta.producto_id)\
         .group_by(Producto.nombre)\
         .order_by(func.sum(DetalleVenta.cantidad).asc())\
         .limit(10).all()
        for p in menos_vendidos:
            print(f"- {p.nombre}: {p.total_vendido}")

        print("\n=== STOCK AGOTADO ===")
        # Productos sin stock o stock <= 0
        sin_stock = Producto.query.filter(Producto.stock <= 0).limit(20).all()
        for p in sin_stock:
            print(f"- {p.nombre} (Stock: {p.stock})")

        print("\n=== CONTABILIDAD DE LA SEMANA ===")
        # Contabilidad detallada por los ultimos 7 dias
        hoy = date.today()
        # Tomaremos los últimos 7 días
        for i in range(6, -1, -1):
            dia = hoy - timedelta(days=i)
            # Buscar ventas y utilidad de ese día
            # Solo ventas que el DATE de la fecha coincida
            ventas_dia = Venta.query.filter(func.date(Venta.fecha) == dia).all()
            total_ventas = sum([v.total_usd for v in ventas_dia if v.total_usd])
            
            # Utilidad = (Ventas - Costos)
            costos_dia = 0
            for v in ventas_dia:
                for d in v.detalles:
                    c = d.producto.costo_usd if d.producto and d.producto.costo_usd else 0
                    costos_dia += c * d.cantidad
            
            utilidad = total_ventas - costos_dia
            print(f"[{dia.strftime('%A, %d %b')}] Ventas: ${total_ventas:.2f} | Costos: ${costos_dia:.2f} | Utilidad: ${utilidad:.2f} | Num. Ventas: {len(ventas_dia)}")

if __name__ == '__main__':
    generar_reportes_para_ia()

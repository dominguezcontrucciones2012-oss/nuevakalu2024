import os
import json
import requests
from datetime import date, timedelta
from decimal import Decimal

# Adjust PYTHONPATH so we can import from app
import sys
sys.path.append('.')

from app import app
from models import Producto, Cliente, Venta, DetalleVenta, db
from utils import seguro_decimal
from sqlalchemy import func
from routes.ia_kalu import URL_API, ABACUS_API_KEY

with app.app_context():
    hoy = date.today()
    
    mas_vendidos = db.session.query(Producto.nombre, func.sum(DetalleVenta.cantidad).label('total'))\
        .join(DetalleVenta, Producto.id == DetalleVenta.producto_id)\
        .group_by(Producto.nombre)\
        .order_by(func.sum(DetalleVenta.cantidad).desc()).limit(10).all()
        
    menos_vendidos = db.session.query(Producto.nombre, func.sum(DetalleVenta.cantidad).label('total'))\
        .join(DetalleVenta, Producto.id == DetalleVenta.producto_id)\
        .group_by(Producto.nombre)\
        .order_by(func.sum(DetalleVenta.cantidad).asc()).limit(10).all()

    sin_stock = Producto.query.filter(Producto.stock <= 0).limit(20).all()

    reporte_dias = []
    total_ventas_semana = Decimal('0.00')
    total_costos_semana = Decimal('0.00')
    total_utilidad_semana = Decimal('0.00')

    print("Fetching db data...")
    try:
        for i in range(6, -1, -1):
            dia = hoy - timedelta(days=i)
            ventas_dia = Venta.query.filter(func.date(Venta.fecha) == dia).all()
            print(f"Date: {dia}, Ventas count: {len(ventas_dia)}")
            
            # Use sum() over Decimals. sum() default start is 0 (int) but works with Decimals? Yes.
            t_ventas = sum([seguro_decimal(v.total_usd) for v in ventas_dia]) if ventas_dia else Decimal('0')
            if type(t_ventas) is int:
                t_ventas = Decimal(t_ventas)
                
            c_dia = Decimal('0.00')
            for v in ventas_dia:
                for d in v.detalles:
                    costo = d.producto.costo_usd if d.producto and d.producto.costo_usd else Decimal('0')
                    c_dia += costo * seguro_decimal(d.cantidad)
            utilidad = t_ventas - c_dia
            
            total_ventas_semana += t_ventas
            total_costos_semana += c_dia
            total_utilidad_semana += utilidad
            
            reporte_dias.append(f"- **{dia.strftime('%d/%m/%Y')}**: 💵 Ventas: **${t_ventas:.2f}** | 📉 Costos: **${c_dia:.2f}** | 📈 Utilidad/Ganancia: **${utilidad:.2f}**")
    except Exception as e:
        print("DB ERROR:", e)

    prompt_datos = """
Eres la IA Financiera (Chief Financial Officer) del sistema KALU. 
Redacta un REPORTE EJECUTIVO SEMANAL extremadamente profesional, muy organizado visualmente y fácil de leer para el dueño del negocio.
Usa formato Markdown avanzado (Usa encabezados ##, Listas con viñetas, negritas, cursivas y Emojis corporativos elegantes).

### REGLAS DE FORMATO Y ESTRUCTURA QUE DEBES CUMPLIR OBLIGATORIAMENTE:
1. **INICIA CON UN RESUMEN SEMANAL:** Muestra los números totales de la cuenta en viñetas destacadas. ¡Felicita al equipo si la ganancia es buena!
2. **DESGLOSE DIARIO:** Muestra cómo le fue al negocio cada día, pero de forma limpia y como una lista.
3. **INVENTARIO Y ROTACIÓN:** Muestra qué se vende más y qué productos están estancados ocupando espacio y dinero. Advierte sobre lo que no tiene stock.
4. **💡 TOP 3 ESTRATEGIAS GERENCIALES:** Toma los números y dale 3 consejos aplicables mañana mismo para aumentar ganancias u optimizar el inventario. Sé muy proactivo y directo (ej. "Recomendamos armar un combo con X para salir de los productos estancados").

### AQUÍ TIENES LOS DATOS CRUCIALES DE LA SEMANA:

**📊 TOTALES DE LA SEMANA:**
- INGRESOS BRUTOS: $""" + f"{total_ventas_semana:.2f}" + """
- COSTOS OPERATIVOS: $""" + f"{total_costos_semana:.2f}" + """
- GANANCIA NETA (UTILIDAD): $""" + f"{total_utilidad_semana:.2f}" + """

**📅 DESGLOSE DÍA POR DÍA:**
""" + "\n".join(reporte_dias) + """

**📦 COMPORTAMIENTO DEL INVENTARIO:**
- ALTA ROTACIÓN (Se venden solos): """ + ", ".join([f"{p[0]} ({p[1]} vendidas)" for p in mas_vendidos]) + """
- BAJA ROTACIÓN (Capital estancado, hay que hacer promociones urgentes): """ + ", ".join([f"{p[0]} ({p[1]} vendidas)" for p in menos_vendidos]) + """
- SIN STOCK / AGOTADOS (Urgente contactar proveedor): """ + ", ".join([p.nombre for p in sin_stock]) + """

Por favor, elabora el reporte directamente. Comienza con un saludo cordial como 'Estimado Gerente, a continuación el balance general...' 
"""

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt_datos}],
        "temperature": 0.5
    }

    headers = {"Authorization": f"Bearer {ABACUS_API_KEY}", "Content-Type": "application/json"}
    
    print("Making API call...")
    try:
        response = requests.post(URL_API, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        print("HTTP Status:", response.status_code)
        
        if 'choices' in res_json and len(res_json['choices']) > 0:
            print("OK, found choices")
        elif 'content' in res_json:
            print("OK, found content")
        else:
            print("FAILED! Unexpected response structure:", res_json)
    except Exception as e:
        print("API Call Exception:", e)


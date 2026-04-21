from decimal import Decimal

total_ventas_semana = Decimal('0.00')
total_costos_semana = Decimal('0.00')
total_utilidad_semana = Decimal('0.00')
reporte_dias = ["- **01/01/2026**: 💵 Ventas: **$0.00**"]
mas_vendidos = [("Producto A", Decimal('10.000')), ("Producto B", Decimal('5.000'))]
menos_vendidos = []

class P:
    pass
sin_stock = []
p = P()
p.nombre = "Producto C"
sin_stock.append(p)

try:
    prompt_datos = """
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
    """
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()


import os
import sys

# Add root to sys.path
sys.path.append(os.getcwd())

from app import app
from decimal import Decimal
from datetime import datetime
from flask import render_template

with app.app_context():
    # Mock data similar to what the routes send
    data = [{
        'id': 1, 'codigo': '001', 'nombre': 'TEST', 'categoria': 'VÍVERES',
        'stock': Decimal('10.5'), 'stock_minimo': Decimal('5.0'),
        'costo_usd': Decimal('1.20'), 'precio_usd': Decimal('2.00'),
        'invertido_usd': Decimal('12.60'), 'valor_venta_usd': Decimal('21.00'),
        'ganancia_usd': Decimal('8.40'), 'invertido_bs': Decimal('450.00'),
        'valor_venta_bs': Decimal('750.00'), 'bajo_minimo': False
    }]
    totales = {
        'total_invertido_usd': Decimal('12.60'),
        'total_venta_usd': Decimal('21.00'),
        'total_ganancia_usd': Decimal('8.40'),
        'total_productos': 1,
        'bajo_minimo': 0
    }
    tasa = Decimal('36.50')
    
    try:
        html = render_template('reporte_inventario.html',
                               data=data,
                               totales=totales,
                               tasa=tasa,
                               categorias=['VÍVERES'],
                               categoria_filtro='TODAS',
                               fecha=datetime.now())
        print("Template rendered successfully!")
    except Exception as e:
        import traceback
        print(f"FAILED: {e}")
        traceback.print_exc()

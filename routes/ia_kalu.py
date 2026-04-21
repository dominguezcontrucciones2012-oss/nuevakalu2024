import os
import json
import requests
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import Producto, Cliente, Venta, DetalleVenta, db
from dotenv import load_dotenv
import logging
from utils import seguro_decimal

# Carga la clave del archivo secreto .env
load_dotenv()

ia_kalu_bp = Blueprint('ia_kalu', __name__)

# Busca la clave automáticamente del .env
ABACUS_API_KEY = os.getenv('ABACUS_API_KEY')
logger = logging.getLogger('KALU.ia_kalu')

# URL OFICIAL Y CORRECTA DE ROUTELLM
URL_API = "https://routellm.abacus.ai/v1/chat/completions"

@ia_kalu_bp.route('/ia-kalu')
@login_required
def index():
    # Análisis rápido para el Dashboard
    stock_bajo = Producto.query.filter(Producto.stock <= 5).all()
    proximos_premios = Cliente.query.filter(Cliente.puntos >= 150).all()
    return render_template('ia_kalu.html', stock_bajo=stock_bajo, proximos_premios=proximos_premios)

@ia_kalu_bp.route('/ia-consultar', methods=['POST'])
@login_required
def consultar_ia():
    pregunta = request.json.get('pregunta')
    
    # Contexto llanero y económico (Modelo gpt-4o-mini es el más barato 🫰)
    contexto = "Eres Kalu-IA, asistente en Guárico. Responde como un llanero serio y directo. Usa 'Epa Juan', 'Camarita', 'Plomo'. Ayuda con el negocio."
    
    payload = {
        "model": "gpt-4o-mini", 
        "messages": [
            {"role": "system", "content": contexto},
            {"role": "user", "content": pregunta}
        ],
        "temperature": 0.7
    }
    
    headers = {
        "Authorization": f"Bearer {ABACUS_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(URL_API, headers=headers, json=payload, timeout=90)
        res_json = response.json()
        
        if 'choices' in res_json and len(res_json['choices']) > 0:
            resultado = res_json['choices'][0]['message']['content']
        elif 'content' in res_json:
            resultado = res_json['content']
        elif 'error' in res_json:
            resultado = f"Epa Juan, la IA dice: {res_json['error'].get('message', 'Error de API')}"
        else:
            logger.debug(f"DEBUG ABACUS: {res_json}")
            resultado = "Epa Juan, recibí una respuesta rara. Revisa la terminal negra."
            
    except Exception as e:
        resultado = f"Epa Juan, no hay señal con la IA: {str(e)}"

    return jsonify({"respuesta": resultado})

# ==========================================================
# 📊 REPORTE INTELIGENTE SEMANAL (Ahorro de Créditos)
# ==========================================================
@ia_kalu_bp.route('/reporte-semanal')
@login_required
def reporte_semanal():
    # Solo dueños o admins deberían verlo
    if current_user.role not in ['admin', 'dueno']:
        return "Acceso denegado. Solo administradores pueden ver este reporte.", 403

    archivo_cache = os.path.join(current_app.instance_path, 'ultimo_reporte_ia.json')
    hoy = date.today()
    
    # 1. CARGAR CACHÉ SI EXISTE Y ES RECIENTE (menos de 7 días)
    if os.path.exists(archivo_cache):
        try:
            with open(archivo_cache, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                fecha_cache = datetime.strptime(datos.get('fecha', '2000-01-01'), '%Y-%m-%d').date()
                # Si el reporte tiene menos de 7 días, lo mostramos de una vez para NO gastar API
                if (hoy - fecha_cache).days < 7:
                    return render_template('reporte_ia_semanal.html', reporte_html=datos.get('html'), fecha=fecha_cache.strftime("%d/%m/%Y"), cached=True)
        except Exception as e:
            logger.error(f"Error leyendo cache de IA: {e}")

    # 2. SI NO HAY CACHÉ O EXPIRÓ, GENERAMOS DATOS DE LA DB
    from sqlalchemy import func
    
    # Alta y baja rotación (Subimos a 15 para un análisis más serio)
    mas_vendidos = db.session.query(Producto.nombre, func.sum(DetalleVenta.cantidad).label('total'))\
        .join(DetalleVenta, Producto.id == DetalleVenta.producto_id)\
        .group_by(Producto.nombre)\
        .order_by(func.sum(DetalleVenta.cantidad).desc()).limit(15).all()
        
    menos_vendidos = db.session.query(Producto.nombre, func.sum(DetalleVenta.cantidad).label('total'))\
        .join(DetalleVenta, Producto.id == DetalleVenta.producto_id)\
        .group_by(Producto.nombre)\
        .order_by(func.sum(DetalleVenta.cantidad).asc()).limit(15).all()

    sin_stock = Producto.query.filter(Producto.stock <= 0).limit(20).all()

    # Contabilidad ultimos 7 dias (Restauramos la semana completa)
    reporte_dias = []
    total_ventas_semana = Decimal('0.00')
    total_costos_semana = Decimal('0.00')
    total_utilidad_semana = Decimal('0.00')

    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        ventas_dia = Venta.query.filter(func.date(Venta.fecha) == dia).all()
        
        t_ventas = sum([seguro_decimal(v.total_usd) for v in ventas_dia], Decimal('0.00'))
        c_dia = Decimal('0.00')
        
        for v in ventas_dia:
            for d in v.detalles:
                costo = d.producto.costo_usd if d.producto and d.producto.costo_usd else Decimal('0.00')
                c_dia += costo * seguro_decimal(d.cantidad)
                
        utilidad = t_ventas - c_dia
        total_ventas_semana += t_ventas
        total_costos_semana += c_dia
        total_utilidad_semana += utilidad
        
        reporte_dias.append(f"| {dia.strftime('%d/%m/%Y')} | ${t_ventas:,.2f} | ${c_dia:,.2f} | ${utilidad:,.2f} |")

    # 3. PREPARAMOS EL PROMPT (REPORTE EJECUTIVO CFO)
    # Nota: Usamos gpt-4o a secas a ver si el router de Abacus le da prioridad y responde más rápido
    prompt_datos = f"""
Actúa como un Auditor Financiero. Genera un reporte semanal corporativo para KALU. 
Sé breve, usa Markdown y tablas.

### DESEMPEÑO DE LA SEMANA:
| Fecha | Ingresos | Margen |
|-------|----------|--------|
""" + "\n".join([f"| {dia[:12]} | {dia[15:30]} | {dia[45:]} |" for dia in reporte_dias]) + f"""

### RESUMEN FINANCIERO:
- INGRESOS: ${total_ventas_semana:,.2f}
- UTILIDAD: ${total_utilidad_semana:,.2f}

### INVENTARIO:
- TOP VENTAS: {", ".join([f"{p[0]}" for p in mas_vendidos])}
- SIN STOCK: {", ".join([p.nombre for p in sin_stock])}

Dame 3 recomendaciones comerciales breves para mejorar las ventas.
"""

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt_datos}],
        "temperature": 0.2,
        "max_tokens": 800
    }

    headers = {"Authorization": f"Bearer {ABACUS_API_KEY}", "Content-Type": "application/json"}
    
    # 4. LLAMADA A LA API
    resultado_ia = "Error al generar el reporte con la IA. Verifica tu saldo/créditos en Abacus."
    try:
        # Volvemos a un tiempo razonable, si no responde en 60s, algo está mal en el servidor de ellos
        response = requests.post(URL_API, headers=headers, json=payload, timeout=90)
        res_json = response.json()
        if 'choices' in res_json and len(res_json['choices']) > 0:
            resultado_ia = res_json['choices'][0]['message']['content']
        elif 'content' in res_json:
            resultado_ia = res_json['content']
        else:
            error_detalles = f"Estructura inesperada de Abacus: {res_json}"
            logger.error(error_detalles)
            resultado_ia = error_detalles
    except Exception as e:
        error_tec = f"Error AI Comunicación: {str(e)}"
        logger.error(error_tec)
        resultado_ia = error_tec
        try:
            with open("scratch/ia_error.txt", "w") as ferr:
                ferr.write(error_tec)
        except:
            pass

    # Convertimos markdown simple a HTML básico o lo mandamos a que marked.js lo procese
    # Por simplicidad, guardamos el markdown y el frontend lo dibuja
    if not resultado_ia.startswith("Error"):
        datos_cache = {
            "fecha": hoy.strftime("%Y-%m-%d"),
            "html": resultado_ia 
        }
        
        os.makedirs(current_app.instance_path, exist_ok=True)
        with open(archivo_cache, 'w', encoding='utf-8') as f:
            json.dump(datos_cache, f, ensure_ascii=False)

    return render_template('reporte_ia_semanal.html', reporte_html=resultado_ia, fecha=hoy.strftime("%d/%m/%Y"), cached=False)
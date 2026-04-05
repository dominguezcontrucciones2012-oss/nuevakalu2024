import os
import requests
from flask import Blueprint, render_template, request, jsonify
from models import Producto, Cliente, db
from dotenv import load_dotenv

# Carga la clave del archivo secreto .env
load_dotenv()

ia_kalu_bp = Blueprint('ia_kalu', __name__)

# Busca la clave automáticamente del .env
ABACUS_API_KEY = os.getenv('ABACUS_API_KEY')

# URL OFICIAL Y CORRECTA DE ROUTELLM
URL_API = "https://routellm.abacus.ai/v1/chat/completions"

@ia_kalu_bp.route('/ia-kalu')
def index():
    # Análisis rápido para el Dashboard
    stock_bajo = Producto.query.filter(Producto.stock <= 5).all()
    proximos_premios = Cliente.query.filter(Cliente.puntos >= 150).all()
    return render_template('ia_kalu.html', stock_bajo=stock_bajo, proximos_premios=proximos_premios)

@ia_kalu_bp.route('/ia-consultar', methods=['POST'])
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
        # Llamada a la API de Abacus
        response = requests.post(URL_API, headers=headers, json=payload, timeout=20)
        res_json = response.json()
        
        # --- EXTRACCIÓN SEGURA DE LA RESPUESTA ---
        if 'choices' in res_json and len(res_json['choices']) > 0:
            resultado = res_json['choices'][0]['message']['content']
        elif 'content' in res_json:
            resultado = res_json['content']
        elif 'error' in res_json:
            resultado = f"Epa Juan, la IA dice: {res_json['error'].get('message', 'Error de API')}"
        else:
            # Si falla, imprimimos en la terminal para saber qué pasó
            print(f"DEBUG ABACUS: {res_json}")
            resultado = "Epa Juan, recibí una respuesta rara. Revisa la terminal negra."
            
    except Exception as e:
        resultado = f"Epa Juan, no hay señal con la IA: {str(e)}"

    return jsonify({"respuesta": resultado})
import time
import requests

URL_API = "https://routellm.abacus.ai/v1/chat/completions"
ABACUS_API_KEY = "s2_6599ec2a5ba74be6a9230a1e2f5fccfb"

prompt_datos = """
Analiza los siguientes datos de ventas semanales y elabora un resumen de 3 parrafos cortos con 2 recomendaciones, no uses emojis ni formato muy complejo.
TOTALES: INGRESOS $5200.00, COSTOS $3800.00, GANANCIA $1400.00
DESGLOSE DIARIO:
- 14/04/2026: Ventas $750, Costos $550
- 15/04/2026: Ventas $800, Costos $600
- 16/04/2026: Ventas $700, Costos $500
INVENTARIO: Alta rotación (Harina, Queso), Baja (Pilas), Sin Stock (Hielo).
"""

payload = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": prompt_datos}],
    "temperature": 0.5,
    "max_tokens": 500
}

headers = {"Authorization": f"Bearer {ABACUS_API_KEY}", "Content-Type": "application/json"}

print("Empezando llamada a la API simplificada...")
start_time = time.time()
try:
    response = requests.post(URL_API, headers=headers, json=payload, timeout=20)
    print(f"Status Code: {response.status_code}")
    print(f"Time Taken: {time.time() - start_time:.2f} seconds")
    try:
        print(response.json()['choices'][0]['message']['content'][:200])
    except:
        print(response.json())
except Exception as e:
    print(f"Time Taken before error: {time.time() - start_time:.2f} seconds")
    print(f"Error: {e}")


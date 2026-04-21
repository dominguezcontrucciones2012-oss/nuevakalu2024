import requests

BASE_URL = "http://127.0.0.1:5002"
USERNAME = "31130671"
PASSWORD = USERNAME[-4:]

def test_client_portal():
    session = requests.Session()
    
    # 1. Intentar Login
    print(f"Probando login para usuario: {USERNAME}...")
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = session.post(f"{BASE_URL}/ingresar", data=login_data, allow_redirects=True)
    
    # Verificamos si logramos entrar (buscando palabras clave o el cambio de URL)
    if response.status_code == 200 and ("mi_deuda" in response.url or "Cerrar" in response.text):
        print("LOGIN EXITOSO (Redirigido a portal).")
    else:
        print(f"AVISO: Login devolvio codigo {response.status_code}")
        if "Usuario o clave incorrecta" in response.text:
            print("ERROR: Credenciales invalidas.")
        return

    # 2. Acceder a Mi Deuda
    print("Verificando acceso a /mi_deuda...")
    response = session.get(f"{BASE_URL}/mi_deuda")
    
    if response.status_code == 200:
        print("PORTAL CARGADO CON EXITO.")
        # Buscamos elementos clave del portal de clientes
        if "Resumen" in response.text or "Total" in response.text or "Saldo" in response.text:
            print("CONTENIDO DE CLIENTE VERIFICADO.")
        else:
            print("ALERTA: El portal cargo pero no parece tener datos de deuda.")
            # print(response.text[:500])
    else:
        print(f"ERROR CRITICO: /mi_deuda devolvio {response.status_code}")


if __name__ == "__main__":
    test_client_portal()

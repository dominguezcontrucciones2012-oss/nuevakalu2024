from decimal import Decimal
import logging

logger = logging.getLogger('KALU.utils')

def seguro_decimal(valor, default='0.00'):
    """
    Convierte un valor a Decimal de forma segura.
    Maneja None, strings vacíos y reemplaza comas por puntos.
    """
    if valor is None or str(valor).strip() == "" or str(valor).lower() == "none":
        return Decimal(default)
    try:
        # Reemplazar coma por punto para soporte de teclados latinos
        limpio = str(valor).replace(',', '.').strip()
        return Decimal(limpio)
    except Exception as e:
        logger.warning(f"Error convirtiendo '{valor}' a Decimal. Usando default {default}. Error: {e}")
        return Decimal(default)

def formatear_decimal(valor, precision=2):
    """
    Formatea un Decimal a string con una precisión específica.
    """
    if not isinstance(valor, Decimal):
        valor = seguro_decimal(valor)
    return "{:,.{}f}".format(valor, precision)

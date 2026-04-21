FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código
COPY . .

# Carpeta para la base de datos se maneja vía volumen /instace

EXPOSE 5002

CMD ["gunicorn", "--bind", ":5002", "--workers", "1", "--threads", "8", "--timeout", "0", "--access-logfile", "-", "app:app"]

#!/bin/bash

# =====================================================================
# 🚀 SCRIPT DE CONFIGURACIÓN MAESTRO: KALUNEVA2024 (Google Cloud Free)
# Creado con Antigravity para: Kalu Master
# =====================================================================

set -e

echo "----------------------------------------------------"
echo "🛠️  Iniciando configuración del servidor KALUNEVA2024..."
echo "----------------------------------------------------"

# 1. Actualizar el sistema
sudo apt-get update && sudo apt-get upgrade -y

# 2. Instalar dependencias necesarias
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

# 3. Instalar Docker
echo "📦 Instalando Docker Engine..."
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 4. Crear carpeta de la App
mkdir -p ~/kaluneva2024/instance
cd ~/kaluneva2024

echo "✅ Docker instalado exitosamente."
echo "----------------------------------------------------"
echo "🌐 CONFIGURACIÓN DE RED (FIREWALL)"
echo "----------------------------------------------------"
echo "Recuerda abrir los siguientes puertos en tu consola de Google Cloud:"
echo " - Puerto 5002 (TCP): Para el acceso a la App."
echo " - Puerto 443 (TCP): Si decides poner SSL/HTTPS."
echo "----------------------------------------------------"

# 5. Instrucciones Finales
echo "🏁 ¡SERVIDOR LISTO!"
echo "----------------------------------------------------"
echo "PRÓXIMOS PASOS:"
echo "1. Sube tus archivos (app.py, templates, static, instance/kalu_master.db) a: ~/kaluneva2024"
echo "2. Ejecuta: 'sudo docker compose up -d' dentro de la carpeta."
echo "3. En Namecheap, apunta tu dominio a la IP de esta máquina."
echo "----------------------------------------------------"
echo "✨ Creada con Antigravity ✨"

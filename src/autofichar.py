from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
import os
import sys
import datetime
from dotenv import load_dotenv
from logger import autofichar_logger, error_logger

# Cargar variables de entorno
load_dotenv('/root/fichar/.env')

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

FESTIVOS_FILE = '/root/fichar/festivos.txt'

# --- Funciones ---
def is_today_holiday():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        with open(FESTIVOS_FILE, 'r') as f:
            festivos = [line.strip() for line in f.readlines()]
        return today in festivos
    except FileNotFoundError:
        autofichar_logger.warning(f"No se encontró el archivo de festivos: {FESTIVOS_FILE}")
        return False

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        autofichar_logger.info(f"Mensaje enviado a Telegram: {message}")
    except Exception as e:
        error_msg = f"Error enviando mensaje a Telegram: {e}"
        error_logger.error(error_msg)
        autofichar_logger.error(error_msg)

# --- Inicio de ejecución ---
autofichar_logger.info("Iniciando proceso de fichaje")

# Si es festivo, salir
if is_today_holiday():
    autofichar_logger.info("Hoy es festivo o vacaciones. No se ficha.")
    exit(0)

# Verificar que se pasó un parámetro
if len(sys.argv) != 2:
    error_msg = "Error: Debes indicar 'entrada' o 'salida' como argumento."
    error_logger.error(error_msg)
    autofichar_logger.error(error_msg)
    exit(1)

tipo_fichaje = sys.argv[1].lower()

if tipo_fichaje not in ["entrada", "salida"]:
    error_msg = "Error: El parámetro debe ser 'entrada' o 'salida'."
    error_logger.error(error_msg)
    autofichar_logger.error(error_msg)
    exit(1)

autofichar_logger.info(f"Iniciando fichaje de {tipo_fichaje}")

# Configuración del navegador
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)

try:
    # 1. Ir a la página de login
    autofichar_logger.info("Accediendo a la página de login")
    driver.get("https://trainingbnetwork.checkjc.com/login")
    
    # 2. Login
    autofichar_logger.info("Realizando login")
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.ID, "btn-login").click()

    # 3. Esperar que el botón esté disponible y hacer clic
    autofichar_logger.info("Esperando botón de fichaje")
    btn_fichar = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "btn-check"))
    )
    btn_fichar.click()

    # 4. Avisar por Telegram si fichaje exitoso
    success_msg = f"✅ Fichaje de {tipo_fichaje} realizado correctamente en CheckJC 🚀"
    send_telegram_message(success_msg)
    autofichar_logger.info(f"Fichaje de {tipo_fichaje} realizado correctamente")

except Exception as e:
    error_msg = f"Error al fichar ({tipo_fichaje}): {str(e)}"
    error_logger.error(error_msg, exc_info=True)
    send_telegram_message(f"❌ {error_msg}")

finally:
    autofichar_logger.info("Cerrando navegador")
    driver.quit()

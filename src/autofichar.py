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
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")

# --- Inicio de ejecución ---

# Si es festivo, salir
if is_today_holiday():
    print("🎉 Hoy es festivo o vacaciones. No se ficha.")
    exit(0)

# Verificar que se pasó un parámetro
if len(sys.argv) != 2:
    print("❌ Error: Debes indicar 'entrada' o 'salida' como argumento.")
    exit(1)

tipo_fichaje = sys.argv[1].lower()

if tipo_fichaje not in ["entrada", "salida"]:
    print("❌ Error: El parámetro debe ser 'entrada' o 'salida'.")
    exit(1)

# Configuración del navegador
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)

try:
    # 1. Ir a la página de login
    driver.get("https://trainingbnetwork.checkjc.com/login")
    
    # 2. Login
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.ID, "btn-login").click()

    # 3. Esperar que el botón esté disponible y hacer clic
    btn_fichar = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "btn-check"))
    )
    btn_fichar.click()

    # 4. Avisar por Telegram si fichaje exitoso
    send_telegram_message(f"✅ Fichaje de {tipo_fichaje} realizado correctamente en CheckJC 🚀")
    print(f"✅ Fichaje de {tipo_fichaje} realizado correctamente.")

except Exception as e:
    error_msg = f"❌ Error al fichar ({tipo_fichaje}): {str(e)}"
    send_telegram_message(error_msg)
    print(error_msg)

finally:
    driver.quit()

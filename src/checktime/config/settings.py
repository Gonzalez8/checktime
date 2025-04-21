import os
from dotenv import load_dotenv
from pathlib import Path
from selenium.webdriver.chrome.options import Options

# Cargar variables de entorno
load_dotenv()

# Directorios
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# URLs
CHECKJC_LOGIN_URL = "https://trainingbnetwork.checkjc.com/login"

# Credenciales
CHECKJC_USERNAME = os.getenv('CHECKJC_USERNAME')
CHECKJC_PASSWORD = os.getenv('CHECKJC_PASSWORD')

# Configuración de Selenium
SELENIUM_TIMEOUT = int(os.getenv("SELENIUM_TIMEOUT", "30"))  # segundos

SELENIUM_OPTIONS = Options()
SELENIUM_OPTIONS.add_argument("--headless")  # Ejecutar en modo headless
SELENIUM_OPTIONS.add_argument("--no-sandbox")
SELENIUM_OPTIONS.add_argument("--disable-dev-shm-usage")
SELENIUM_OPTIONS.add_argument("--disable-gpu")
SELENIUM_OPTIONS.add_argument("--window-size=1920,1080")
SELENIUM_OPTIONS.add_argument("--disable-extensions")
SELENIUM_OPTIONS.add_argument("--disable-infobars")
SELENIUM_OPTIONS.add_argument("--disable-notifications")
SELENIUM_OPTIONS.add_argument("--disable-popup-blocking")

# Configuración de Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Configuración de logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = LOG_DIR / 'autofichar.log'
ERROR_LOG_FILE = LOG_DIR / 'error.log'

# Rutas de archivos
LOG_FILE = LOG_DIR / 'fichar.log'
ERROR_LOG_FILE = LOG_DIR / 'error.log'

# Configuración de logging
LOG_DATE_FORMAT = os.getenv('LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')
LOG_MAX_BYTES = 1024 * 1024  # 1MB
LOG_BACKUP_COUNT = 5 
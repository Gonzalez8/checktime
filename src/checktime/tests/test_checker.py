#!/usr/bin/env python3
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Añadir el directorio raíz al path para poder importar los módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.checktime.core.checker import CheckJCClient
from src.checktime.config.settings import LOG_DIR

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "test_checker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_checker():
    """Prueba la funcionalidad de check-in/check-out."""
    try:
        # Configurar opciones de Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        print("\n=== PRUEBA DE CHECK-IN/CHECK-OUT ===")
        
        # Crear instancia del checker con las opciones configuradas
        with CheckJCClient(options=chrome_options, timeout=10) as checker:
            # Probar check-in
            print("\nProbando check-in...")
            checkin_result = checker.check_in()
            
            if checkin_result:
                print("✅ Check-in realizado correctamente")
            else:
                print("❌ Error al realizar check-in")
            
            # Esperar 5 segundos
            print("\nEsperando 5 segundos...")
            import time
            time.sleep(5)
            
            # Probar check-out
            print("\nProbando check-out...")
            checkout_result = checker.check_out()
            
            if checkout_result:
                print("✅ Check-out realizado correctamente")
            else:
                print("❌ Error al realizar check-out")
        
    except Exception as e:
        logger.error(f"Error en la prueba del checker: {str(e)}")
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_checker() 
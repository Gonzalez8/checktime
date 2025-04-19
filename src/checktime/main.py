import logging
import schedule
import time
from datetime import datetime
from pathlib import Path

from checktime.core.checker import CheckJCClient
from checktime.config.settings import (
    CHECK_IN_TIME,
    CHECK_OUT_TIME,
    LOG_DIR,
    SELENIUM_OPTIONS,
    SELENIUM_TIMEOUT,
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "fichar.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def is_working_day():
    """Verifica si hoy es un día laborable."""
    today = datetime.now()
    return today.weekday() < 5  # 0-4 son días de semana (Lunes-Viernes)

def perform_check_in():
    """Realiza el proceso de fichaje de entrada."""
    if not is_working_day():
        logger.info("Hoy no es un día laborable. No se realizará el fichaje.")
        return

    logger.info("Iniciando proceso de fichaje de entrada...")
    try:
        with CheckJCClient(SELENIUM_OPTIONS, SELENIUM_TIMEOUT) as client:
            client.login()
            client.check_in()
            logger.info("Fichaje de entrada completado exitosamente.")
    except Exception as e:
        logger.error(f"Error durante el fichaje de entrada: {str(e)}")

def perform_check_out():
    """Realiza el proceso de fichaje de salida."""
    if not is_working_day():
        logger.info("Hoy no es un día laborable. No se realizará el fichaje.")
        return

    logger.info("Iniciando proceso de fichaje de salida...")
    try:
        with CheckJCClient(SELENIUM_OPTIONS, SELENIUM_TIMEOUT) as client:
            client.login()
            client.check_out()
            logger.info("Fichaje de salida completado exitosamente.")
    except Exception as e:
        logger.error(f"Error durante el fichaje de salida: {str(e)}")

def main():
    """Función principal que configura y ejecuta los trabajos programados."""
    logger.info("Iniciando el servicio de fichaje automático...")

    # Programar tareas
    schedule.every().day.at(CHECK_IN_TIME).do(perform_check_in)
    schedule.every().day.at(CHECK_OUT_TIME).do(perform_check_out)

    # Ejecutar el bucle de programación
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Revisar cada minuto
        except Exception as e:
            logger.error(f"Error en el bucle principal: {str(e)}")
            time.sleep(300)  # Esperar 5 minutos antes de reintentar

if __name__ == "__main__":
    main() 
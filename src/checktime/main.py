import logging
import schedule
import time
from datetime import datetime
from pathlib import Path

from checktime.core.checker import CheckJCClient
from checktime.config.settings import (
    LOG_DIR,
    SELENIUM_OPTIONS,
    SELENIUM_TIMEOUT,
)
from checktime.utils.telegram import TelegramClient
from checktime.core.holidays import HolidayManager

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

# Inicializar cliente de Telegram y gestor de festivos
telegram_client = TelegramClient()
holiday_manager = HolidayManager()

def is_working_day():
    """Verifica si hoy es un día laborable."""
    today = datetime.now()
    # Verificar si es fin de semana
    if today.weekday() >= 5:  # 5 es sábado, 6 es domingo
        return False
    # Verificar si es festivo
    if holiday_manager.is_holiday():
        return False
    return True

def get_schedule_times():
    """Get check-in and check-out times based on the day of the week"""
    today = datetime.now()
    weekday = today.weekday()
    
    if weekday < 4:  # Monday to Thursday
        return "09:00", "18:00"
    else:  # Friday
        return "08:00", "15:00"

def perform_check(check_type):
    """
    Realiza el proceso de fichaje.
    
    Args:
        check_type (str): Tipo de fichaje ('entrada' o 'salida')
    """
    if not is_working_day():
        message = "Hoy no es un día laborable o es festivo. No se realizará el fichaje."
        logger.info(message)
        telegram_client.send_message(f"ℹ️ {message}")
        return

    logger.info(f"Iniciando proceso de fichaje de {check_type}...")
    telegram_client.send_message(f"🔄 Iniciando proceso de fichaje de {check_type}...")
    
    try:
        with CheckJCClient(SELENIUM_OPTIONS, SELENIUM_TIMEOUT) as client:
            client.login()
            if check_type == "entrada":
                client.check_in()
            else:
                client.check_out()
            logger.info(f"Fichaje de {check_type} completado exitosamente.")
    except Exception as e:
        error_msg = f"Error durante el fichaje de {check_type}: {str(e)}"
        logger.error(error_msg)
        telegram_client.send_message(f"❌ {error_msg}")

def perform_check_in():
    """Realiza el proceso de fichaje de entrada."""
    perform_check("entrada")

def perform_check_out():
    """Realiza el proceso de fichaje de salida."""
    perform_check("salida")

def main():
    """Función principal que configura y ejecuta los trabajos programados."""
    logger.info("Iniciando el servicio de fichaje automático...")
    telegram_client.send_message("🚀 Iniciando el servicio de fichaje automático...")

    # Programar tareas con horarios dinámicos
    schedule.every().minute.do(lambda: schedule_check())

    # Mantener el script en ejecución
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Revisar cada minuto
        except Exception as e:
            error_msg = f"Error en el bucle principal: {str(e)}"
            logger.error(error_msg)
            telegram_client.send_message(f"❌ {error_msg}")
            time.sleep(300)  # Esperar 5 minutos antes de reintentar

def schedule_check():
    """Check if it's time to perform check-in/out based on the schedule"""
    if not is_working_day():
        return

    check_in_time, check_out_time = get_schedule_times()
    current_time = datetime.now().strftime("%H:%M")
    
    if current_time == check_in_time:
        perform_check_in()
    elif current_time == check_out_time:
        perform_check_out()

if __name__ == "__main__":
    main() 
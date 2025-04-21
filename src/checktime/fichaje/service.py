#!/usr/bin/env python
"""
Punto de entrada específico para el servicio de fichaje automático.
Este script solo inicia el servicio de fichaje que comprueba los horarios y realiza fichajes programados.
"""

import logging
import schedule
import time
from datetime import datetime
import threading
import os

from checktime.fichaje.checker import CheckJCClient
from checktime.config.settings import LOG_DIR, SELENIUM_OPTIONS, SELENIUM_TIMEOUT
from checktime.utils.telegram import TelegramClient
from checktime.web import create_app
from checktime.web.models import SchedulePeriod, DaySchedule, Holiday

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "fichaje.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Inicializar cliente de Telegram
telegram_client = TelegramClient()

# Crear aplicación Flask (solo para acceso a la base de datos)
app = create_app()

def is_working_day():
    """Verifica si hoy es un día laborable."""
    today = datetime.now().date()
    
    # Verificar si es fin de semana
    if today.weekday() >= 5:  # 5 es sábado, 6 es domingo
        return False
    
    # Verificar festivos en la base de datos
    with app.app_context():
        if Holiday.query.filter_by(date=today).first():
            logger.info(f"Día festivo encontrado en la base de datos: {today}")
            return False
    
    return True

def get_schedule_times():
    """Get check-in and check-out times based on the current schedule in database"""
    today = datetime.now().date()
    weekday = today.weekday()
    
    # Get schedule from database
    with app.app_context():
        # Get active period for today
        active_period = SchedulePeriod.query.filter(
            SchedulePeriod.is_active == True,
            SchedulePeriod.start_date <= today,
            SchedulePeriod.end_date >= today
        ).first()
        
        if active_period:
            # Get day schedule for today's weekday
            day_schedule = DaySchedule.query.filter_by(
                period_id=active_period.id,
                day_of_week=weekday
            ).first()
            
            if day_schedule:
                logger.info(f"Usando horario de la base de datos: {day_schedule.check_in_time} - {day_schedule.check_out_time}")
                return day_schedule.check_in_time, day_schedule.check_out_time
    
    # Si no hay configuración en la base de datos, no fichar
    logger.info("No hay horario configurado en la base de datos. No se realizará fichaje automático.")
    return None, None

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

def schedule_check():
    """Check if it's time to perform check-in/out based on the schedule"""
    if not is_working_day():
        return

    check_in_time, check_out_time = get_schedule_times()
    
    # Si no hay horarios definidos, no realizar fichaje
    if check_in_time is None or check_out_time is None:
        return
        
    current_time = datetime.now().strftime("%H:%M")
    
    if current_time == check_in_time:
        perform_check_in()
    elif current_time == check_out_time:
        perform_check_out()

def main():
    """Función principal que ejecuta solo el servicio de fichaje."""
    logger.info("Iniciando el servicio de fichaje automático...")
    telegram_client.send_message("🚀 Iniciando el servicio de fichaje automático")

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

if __name__ == "__main__":
    main() 
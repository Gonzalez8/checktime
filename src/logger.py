import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('/root/fichar/.env')

# Configuración de rutas de logs
LOG_FILE = os.getenv('LOG_FILE', 'logs/fichar.log')
ERROR_LOG_FILE = os.getenv('ERROR_LOG_FILE', 'logs/error.log')

# Asegurar que el directorio de logs existe
os.makedirs('logs', exist_ok=True)

def setup_logger(name, log_file=LOG_FILE, level=logging.INFO):
    """
    Configura y retorna un logger con el nombre especificado.
    
    Args:
        name (str): Nombre del logger
        log_file (str): Ruta al archivo de log
        level (int): Nivel de logging
    
    Returns:
        logging.Logger: Logger configurado
    """
    # Crear el logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Formato del log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para archivo
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,  # 1MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def setup_error_logger(name, log_file=ERROR_LOG_FILE):
    """
    Configura y retorna un logger específico para errores.
    
    Args:
        name (str): Nombre del logger
        log_file (str): Ruta al archivo de log de errores
    
    Returns:
        logging.Logger: Logger configurado para errores
    """
    logger = setup_logger(name, log_file, logging.ERROR)
    return logger

# Loggers predefinidos
autofichar_logger = setup_logger('autofichar')
bot_logger = setup_logger('bot')
error_logger = setup_error_logger('error') 
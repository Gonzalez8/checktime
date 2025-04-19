import logging
import os
from logging.handlers import RotatingFileHandler
from ..config.settings import (
    LOG_FILE,
    ERROR_LOG_FILE,
    LOG_FORMAT,
    LOG_DATE_FORMAT,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT
)

# Asegurar que el directorio de logs existe
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

class LoggerFactory:
    """Factory para crear loggers con configuración consistente."""
    
    @staticmethod
    def create_logger(name, log_file=LOG_FILE, level=logging.INFO):
        """
        Crea y configura un logger.
        
        Args:
            name (str): Nombre del logger
            log_file (str): Ruta al archivo de log
            level (int): Nivel de logging
        
        Returns:
            logging.Logger: Logger configurado
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Evitar duplicación de handlers
        if logger.handlers:
            return logger
        
        # Formato del log
        formatter = logging.Formatter(
            LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT
        )
        
        # Handler para archivo
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    @staticmethod
    def create_error_logger(name):
        """
        Crea un logger específico para errores.
        
        Args:
            name (str): Nombre del logger
        
        Returns:
            logging.Logger: Logger configurado para errores
        """
        return LoggerFactory.create_logger(name, ERROR_LOG_FILE, logging.ERROR)

# Loggers predefinidos
autofichar_logger = LoggerFactory.create_logger('autofichar')
bot_logger = LoggerFactory.create_logger('bot')
error_logger = LoggerFactory.create_error_logger('error') 
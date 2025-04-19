import logging
from pathlib import Path
from ..utils.logger import bot_logger, error_logger
from .listener import TelegramBotListener

def main():
    """Función principal para ejecutar el bot de Telegram."""
    try:
        bot_logger.info("Iniciando bot de Telegram para gestión de festivos")
        listener = TelegramBotListener()
        listener.listen()
    except Exception as e:
        error_msg = f"Error en el bot de Telegram: {e}"
        error_logger.error(error_msg, exc_info=True)
        bot_logger.error(error_msg)

if __name__ == "__main__":
    main() 
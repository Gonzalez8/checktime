import requests
from typing import Optional, Dict, Any
from ..utils.logger import bot_logger, error_logger
from ..config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

class TelegramClient:
    """Cliente para interactuar con la API de Telegram."""
    
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
        """
        Inicializa el cliente de Telegram.
        
        Args:
            token (str): Token del bot de Telegram
            chat_id (str): ID del chat donde se enviarán los mensajes
        """
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Envía un mensaje a través de Telegram.
        
        Args:
            message (str): Mensaje a enviar
            parse_mode (str): Modo de parseo del mensaje (Markdown o HTML)
        
        Returns:
            bool: True si el mensaje se envió correctamente, False en caso contrario
        """
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            bot_logger.info(f"Mensaje enviado a Telegram: {message}")
            return True
        except Exception as e:
            error_msg = f"Error enviando mensaje a Telegram: {e}"
            error_logger.error(error_msg)
            bot_logger.error(error_msg)
            return False
    
    def get_updates(self, offset: Optional[int] = None, timeout: int = 100) -> Dict[str, Any]:
        """
        Obtiene las actualizaciones del bot.
        
        Args:
            offset (Optional[int]): ID de la última actualización recibida
            timeout (int): Tiempo máximo de espera para la respuesta
        
        Returns:
            Dict[str, Any]: Respuesta de la API de Telegram
        """
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        
        try:
            response = requests.get(url, params=params, timeout=timeout + 20)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            error_msg = f"Error obteniendo actualizaciones de Telegram: {e}"
            error_logger.error(error_msg)
            bot_logger.error(error_msg)
            return {"result": []} 
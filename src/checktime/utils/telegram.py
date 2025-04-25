"""
Telegram integration for CheckTime application.
"""

import requests
import logging
from typing import Optional, Dict, Any

from checktime.shared.config import get_telegram_token, get_telegram_chat_id

# Create logger
logger = logging.getLogger(__name__)

class TelegramClient:
    """Client for interacting with the Telegram API."""
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize the Telegram client.
        
        Args:
            token (Optional[str]): Telegram bot token
            chat_id (Optional[str]): Chat ID where messages will be sent
        """
        self.token = token or get_telegram_token()
        self.chat_id = chat_id or get_telegram_chat_id()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
    
    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message via Telegram.
        
        Args:
            message (str): Message to send
            parse_mode (str): Parse mode for the message (Markdown or HTML)
        
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not configured, message not sent")
            return False
            
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            logger.info(f"Message sent to Telegram: {message[:50]}...")
            return True
        except Exception as e:
            error_msg = f"Error sending message to Telegram: {e}"
            logger.error(error_msg)
            return False
    
    def get_updates(self, offset: Optional[int] = None, timeout: int = 100) -> Dict[str, Any]:
        """
        Get updates from the bot.
        
        Args:
            offset (Optional[int]): ID of the last update received
            timeout (int): Maximum wait time for the response
        
        Returns:
            Dict[str, Any]: Response from the Telegram API
        """
        if not self.token:
            logger.warning("Telegram token not configured, cannot get updates")
            return {"result": []}
            
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        
        try:
            response = requests.get(url, params=params, timeout=timeout + 20)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            error_msg = f"Error getting updates from Telegram: {e}"
            logger.error(error_msg)
            return {"result": []} 
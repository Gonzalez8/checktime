"""
Telegram integration for CheckTime application.
"""

import requests
import logging
from typing import Optional, Dict, Any, List, Union

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
            chat_id (Optional[str]): Default chat ID where messages will be sent
        """
        self.token = token or get_telegram_token()
        self.default_chat_id = chat_id or get_telegram_chat_id()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
    
    def send_message(self, message: str, chat_id: Optional[str] = None, parse_mode: str = "Markdown") -> bool:
        """
        Send a message via Telegram to a specific chat ID or the default one.
        
        Args:
            message (str): Message to send
            chat_id (Optional[str]): Chat ID where message will be sent. If None, uses default.
            parse_mode (str): Parse mode for the message (Markdown or HTML)
        
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        # Use specified chat ID or fall back to default
        target_chat_id = chat_id or self.default_chat_id
        
        if not self.token or not target_chat_id:
            logger.warning("Telegram credentials not configured, message not sent")
            return False
            
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": target_chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            logger.info(f"Message sent to Telegram chat {target_chat_id}: {message[:50]}...")
            return True
        except Exception as e:
            error_msg = f"Error sending message to Telegram chat {target_chat_id}: {e}"
            logger.error(error_msg)
            return False
            
    def send_message_to_users(self, message: str, users: List[Dict], parse_mode: str = "Markdown") -> Dict[str, bool]:
        """
        Send a message to multiple users.
        
        Args:
            message (str): Message to send
            users (List[Dict]): List of user objects with telegram_chat_id attribute
            parse_mode (str): Parse mode for the message (Markdown or HTML)
            
        Returns:
            Dict[str, bool]: Dictionary mapping user IDs to success status
        """
        results = {}
        
        for user in users:
            if not user.get('telegram_chat_id'):
                continue
                
            user_id = user.get('id', 'unknown')
            chat_id = user.get('telegram_chat_id')
            success = self.send_message(message, chat_id, parse_mode)
            results[user_id] = success
            
        return results
    
    def send_notification(self, message: str, user=None, parse_mode: str = "Markdown") -> bool:
        """
        Send a notification to a specific user or the default chat.
        
        Args:
            message (str): Message to send
            user (Optional): User object with telegram_chat_id and telegram_notifications_enabled
            parse_mode (str): Parse mode for the message
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        # If user is provided and has Telegram configured, send to that user
        if user and hasattr(user, 'telegram_chat_id') and hasattr(user, 'telegram_notifications_enabled'):
            if user.telegram_chat_id and user.telegram_notifications_enabled:
                return self.send_message(message, user.telegram_chat_id, parse_mode)
            else:
                logger.info(f"User {getattr(user, 'username', 'unknown')} has no Telegram configured or notifications disabled")
                return False
        
        # Otherwise, send to default chat ID
        return self.send_message(message, parse_mode=parse_mode)
    
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
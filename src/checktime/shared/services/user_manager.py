"""
User management service for CheckTime application.
"""

import logging
from typing import List, Optional, Any

from checktime.shared.repository.user_repository import UserRepository
from checktime.shared.models.user import User

# Create logger
logger = logging.getLogger(__name__)

class UserManager:
    """Manager for users in the system."""
    
    def __init__(self):
        """Initialize the user manager."""
        self.repository = UserRepository()
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id (int): The user ID
            
        Returns:
            User or None: User object if found, None otherwise
        """
        try:
            user = self.repository.get_by_id(user_id)
            return user
        except Exception as e:
            error_msg = f"Error getting user by ID: {e}"
            logger.error(error_msg)
            return None
    
    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username.
        
        Args:
            username (str): The username
            
        Returns:
            User or None: User object if found, None otherwise
        """
        try:
            user = self.repository.get_by_username(username)
            return user
        except Exception as e:
            error_msg = f"Error getting user by username: {e}"
            logger.error(error_msg)
            return None
    
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email.
        
        Args:
            email (str): The email address
            
        Returns:
            User or None: User object if found, None otherwise
        """
        try:
            user = self.repository.get_by_email(email)
            return user
        except Exception as e:
            error_msg = f"Error getting user by email: {e}"
            logger.error(error_msg)
            return None
    
    def create_user(self, username: str, email: str, password: str, is_admin: bool = False) -> Optional[User]:
        """
        Create a new user.
        
        Args:
            username (str): Username for the new user
            email (str): Email for the new user
            password (str): Password for the new user
            is_admin (bool, optional): Whether the user is an admin. Defaults to False.
            
        Returns:
            User or None: Created user object if successful, None otherwise
        """
        try:
            # Check if username already exists
            existing_user = self.get_by_username(username)
            if existing_user:
                logger.warning(f"Username {username} already exists")
                return None
                
            # Check if email already exists
            existing_email = self.get_by_email(email)
            if existing_email:
                logger.warning(f"Email {email} already exists")
                return None
                
            # Create new user
            user = self.repository.create_user(username, email, password, is_admin)
            logger.info(f"Created new user: {username}")
            return user
        except Exception as e:
            error_msg = f"Error creating user: {e}"
            logger.error(error_msg)
            return None
    
    def update_user(self, user: User, username: str = None, email: str = None, 
                  password: str = None, is_admin: bool = None) -> Optional[User]:
        """
        Update an existing user.
        
        Args:
            user (User): The user to update
            username (str, optional): New username. Defaults to None.
            email (str, optional): New email. Defaults to None.
            password (str, optional): New password. Defaults to None.
            is_admin (bool, optional): Admin status. Defaults to None.
            
        Returns:
            User or None: Updated user object if successful, None otherwise
        """
        try:
            # Check if new username already exists
            if username and username != user.username:
                existing_user = self.get_by_username(username)
                if existing_user and existing_user.id != user.id:
                    logger.warning(f"Username {username} already exists")
                    return None
                    
            # Check if new email already exists
            if email and email != user.email:
                existing_email = self.get_by_email(email)
                if existing_email and existing_email.id != user.id:
                    logger.warning(f"Email {email} already exists")
                    return None
                    
            # Update user
            updated_user = self.repository.update_user(user, username, email, password, is_admin)
            logger.info(f"Updated user: {user.username}")
            return updated_user
        except Exception as e:
            error_msg = f"Error updating user: {e}"
            logger.error(error_msg)
            return None
    
    def get_all_with_checkjc_configured(self) -> List[User]:
        """
        Get all users who have CheckJC configured and enabled for automatic check-in.
        
        Returns:
            List[User]: List of users with CheckJC configured
        """
        try:
            users = self.repository.get_all_with_checkjc_configured()
            logger.info(f"Found {len(users)} users with CheckJC configured")
            return users
        except Exception as e:
            error_msg = f"Error getting users with CheckJC configured: {e}"
            logger.error(error_msg)
            return []
    
    def get_all_with_telegram_configured(self) -> List[User]:
        """
        Get all users who have Telegram notifications configured and enabled.
        
        Returns:
            List[User]: List of users with Telegram configured
        """
        try:
            users = self.repository.get_all_with_telegram_configured()
            logger.info(f"Found {len(users)} users with Telegram configured")
            return users
        except Exception as e:
            error_msg = f"Error getting users with Telegram configured: {e}"
            logger.error(error_msg)
            return []
    
    def get_user_by_chat_id(self, chat_id: str) -> Optional[User]:
        """
        Get user by Telegram chat ID.
        
        Args:
            chat_id (str): Telegram chat ID
            
        Returns:
            User or None: User object if found, None otherwise
        """
        try:
            # Get all users with Telegram configured
            users = self.get_all_with_telegram_configured()
            
            # Find the user with matching chat ID
            for user in users:
                if str(user.telegram_chat_id) == str(chat_id):
                    logger.info(f"Found user {user.username} with chat ID {chat_id}")
                    return user
            
            logger.info(f"No user found with chat ID {chat_id}")
            return None
        except Exception as e:
            error_msg = f"Error getting user by chat ID: {e}"
            logger.error(error_msg)
            return None
    
    def set_checkjc_credentials(self, user_id: int, username: str, password: str, enabled: bool = True) -> Optional[User]:
        """
        Set the CheckJC credentials for a user.
        
        Args:
            user_id (int): The ID of the user to update
            username (str): The CheckJC username
            password (str): The CheckJC password
            enabled (bool, optional): Whether auto check-in is enabled. Defaults to True.
            
        Returns:
            User or None: The updated user or None on error
        """
        try:
            user = self.repository.set_checkjc_credentials(user_id, username, password, enabled)
            if user:
                logger.info(f"Updated CheckJC credentials for user {user.username}")
            return user
        except Exception as e:
            error_msg = f"Error setting CheckJC credentials: {e}"
            logger.error(error_msg)
            return None
    
    def set_telegram_settings(self, user_id: int, chat_id: str, enabled: bool = True) -> Optional[User]:
        """
        Set the Telegram settings for a user.
        
        Args:
            user_id (int): The ID of the user to update
            chat_id (str): The Telegram chat ID
            enabled (bool, optional): Whether Telegram notifications are enabled. Defaults to True.
            
        Returns:
            User or None: The updated user or None on error
        """
        try:
            user = self.repository.set_telegram_settings(user_id, chat_id, enabled)
            if user:
                logger.info(f"Updated Telegram settings for user {user.username}")
            return user
        except Exception as e:
            error_msg = f"Error setting Telegram settings: {e}"
            logger.error(error_msg)
            return None 
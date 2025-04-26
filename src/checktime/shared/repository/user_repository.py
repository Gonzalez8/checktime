"""
Repository for user operations.
"""

from typing import List, Optional

from checktime.shared.models.user import User
from checktime.shared.repository.base_repository import BaseRepository

class UserRepository(BaseRepository[User]):
    """Repository for user operations."""
    
    def __init__(self):
        """Initialize the repository."""
        super().__init__(User)
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        return User.query.filter_by(username=username).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email."""
        return User.query.filter_by(email=email).first()
    
    def create_user(self, username: str, email: str, password: str, is_admin: bool = False) -> User:
        """Create a new user."""
        user = User(username=username, email=email, is_admin=is_admin)
        user.set_password(password)
        return super().create(user)
    
    def update_user(self, user: User, username: str = None, email: str = None, 
                   password: str = None, is_admin: bool = None) -> User:
        """Update a user."""
        if username:
            user.username = username
        if email:
            user.email = email
        if password:
            user.set_password(password)
        if is_admin is not None:
            user.is_admin = is_admin
        return super().update(user)
        
    def get_all_with_checkjc_configured(self) -> List[User]:
        """
        Get all users who have CheckJC configured and enabled for automatic check-in.
        
        Returns:
            List[User]: List of users with CheckJC configured
        """
        return User.query.filter(
            User.checkjc_username.isnot(None),
            User.checkjc_password_encrypted.isnot(None),
            User.auto_checkin_enabled == True
        ).all()
        
    def set_checkjc_credentials(self, user_id: int, username: str, password: str, 
                              enabled: bool = True) -> User:
        """
        Set the CheckJC credentials for a user.
        
        Args:
            user_id (int): The ID of the user to update
            username (str): The CheckJC username
            password (str): The CheckJC password
            enabled (bool, optional): Whether auto check-in is enabled. Defaults to True.
            
        Returns:
            User: The updated user
        """
        user = self.get_by_id(user_id)
        if not user:
            return None
            
        user.checkjc_username = username
        user.set_checkjc_password(password)
        user.auto_checkin_enabled = enabled
        
        return super().update(user)
        
    def get_all_with_telegram_configured(self) -> List[User]:
        """
        Get all users who have Telegram notifications configured and enabled.
        
        Returns:
            List[User]: List of users with Telegram configured
        """
        return User.query.filter(
            User.telegram_chat_id.isnot(None),
            User.telegram_notifications_enabled == True
        ).all()
        
    def set_telegram_settings(self, user_id: int, chat_id: str, enabled: bool = True) -> User:
        """
        Set the Telegram settings for a user.
        
        Args:
            user_id (int): The ID of the user to update
            chat_id (str): The Telegram chat ID
            enabled (bool, optional): Whether Telegram notifications are enabled. Defaults to True.
            
        Returns:
            User: The updated user
        """
        user = self.get_by_id(user_id)
        if not user:
            return None
            
        user.telegram_chat_id = chat_id
        user.telegram_notifications_enabled = enabled
        
        return super().update(user) 
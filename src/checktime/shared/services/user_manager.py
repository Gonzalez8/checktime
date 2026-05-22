"""
User management service for CheckTime application.
"""

import hashlib
import logging
import secrets
from typing import List, Optional, Tuple

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
    
    def set_checkjc_credentials(self, user_id: int, username: str, password: str, enabled: bool = True, subdomain: str = None) -> Optional[User]:
        """
        Set the CheckJC credentials for a user.
        
        Args:
            user_id (int): The ID of the user to update
            username (str): The CheckJC username
            password (str): The CheckJC password
            enabled (bool, optional): Whether auto check-in is enabled. Defaults to True.
            subdomain (str, optional): The CheckJC subdomain.
            
        Returns:
            User or None: The updated user or None on error
        """
        try:
            user = self.repository.set_checkjc_credentials(user_id, username, password, enabled, subdomain)
            if user:
                logger.info(f"Updated CheckJC credentials for user {user.username}")
            return user
        except Exception as e:
            error_msg = f"Error setting CheckJC credentials: {e}"
            logger.error(error_msg)
            return None
    
    def list_users(self) -> List[User]:
        """Return all users ordered by username."""
        try:
            return self.repository.get_all()
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []

    def list_users_by_ids(self, user_ids: List[int]) -> List[User]:
        """Return the subset of users matching the given IDs."""
        cleaned = [uid for uid in user_ids if isinstance(uid, int)]
        if not cleaned:
            return []
        try:
            return User.query.filter(User.id.in_(cleaned)).all()
        except Exception as e:
            logger.error(f"Error listing users by ids: {e}")
            return []

    def count_admins(self) -> int:
        """Return how many admin users currently exist."""
        try:
            return User.query.filter_by(is_admin=True).count()
        except Exception as e:
            logger.error(f"Error counting admins: {e}")
            return 0

    def delete_user(self, user_id: int) -> bool:
        """Delete a user by ID. Returns True on success."""
        user = self.get_by_id(user_id)
        if user is None:
            return False
        try:
            self.repository.delete(user)
            logger.info(f"Deleted user {user.username} (id={user_id})")
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    def find_by_username_or_email(self, identifier: str) -> Optional[User]:
        """Look up a user by username or email."""
        try:
            return self.repository.get_by_username_or_email(identifier)
        except Exception as e:
            logger.error(f"Error finding user by identifier: {e}")
            return None

    def create_password_reset_token(self, identifier: str) -> Tuple[Optional[User], Optional[str]]:
        """Generate a reset token for the user matching identifier.

        Returns (user, raw_token) on success or (None, None) if no user matches.
        Callers must NOT leak the difference between "not found" and "found" to
        the requester — that's handled in the view.
        """
        user = self.find_by_username_or_email(identifier)
        if user is None:
            return None, None
        try:
            raw_token = user.generate_password_reset_token()
            self.repository.update(user)
            logger.info(f"Issued password reset token for user {user.username}")
            return user, raw_token
        except Exception as e:
            logger.error(f"Error generating reset token: {e}")
            return None, None

    def verify_password_reset_token(self, raw_token: str) -> Optional[User]:
        """Return the user a non-expired token belongs to, or None."""
        if not raw_token:
            return None
        try:
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            user = self.repository.find_by_reset_token_hash(token_hash)
            if user and user.password_reset_token_matches(raw_token):
                return user
            return None
        except Exception as e:
            logger.error(f"Error verifying reset token: {e}")
            return None

    def reset_password_with_token(self, raw_token: str, new_password: str) -> Optional[User]:
        """Consume a valid token and set a new password. Returns the user or None."""
        user = self.verify_password_reset_token(raw_token)
        if user is None:
            return None
        try:
            user.set_password(new_password)
            user.clear_password_reset_token()
            self.repository.update(user)
            logger.info(f"Password reset completed for user {user.username}")
            return user
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return None

    def admin_reset_password(self, user_id: int) -> Tuple[Optional[User], Optional[str]]:
        """Set a fresh random password for the given user and return it once.

        Used by admins to hand a one-time password to a user out-of-band.
        Returns (user, temporary_password) or (None, None).
        """
        user = self.get_by_id(user_id)
        if user is None:
            return None, None
        try:
            temporary_password = secrets.token_urlsafe(12)
            user.set_password(temporary_password)
            user.clear_password_reset_token()
            self.repository.update(user)
            logger.info(f"Admin-issued temporary password for user {user.username}")
            return user, temporary_password
        except Exception as e:
            logger.error(f"Error issuing admin temporary password: {e}")
            return None, None

    def set_google_api_key(self, user_id: int, api_key: Optional[str]) -> Optional[User]:
        """Save (encrypted) or clear the user's Google Gemini API key."""
        try:
            user = self.repository.get_by_id(user_id)
            if user is None:
                return None
            user.set_google_api_key(api_key or None)
            self.repository.update(user)
            if api_key:
                logger.info(f"Stored Google API key for user {user.username}")
            else:
                logger.info(f"Cleared Google API key for user {user.username}")
            return user
        except Exception as e:
            logger.error(f"Error setting Google API key: {e}")
            return None

    def set_gemini_model(self, user_id: int, model: Optional[str]) -> Optional[User]:
        """Save the user's preferred Gemini model (or None to use default)."""
        try:
            user = self.repository.get_by_id(user_id)
            if user is None:
                return None
            user.gemini_model = (model or None) or None
            self.repository.update(user)
            logger.info(f"Set gemini_model={model!r} for user {user.username}")
            return user
        except Exception as e:
            logger.error(f"Error setting Gemini model: {e}")
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
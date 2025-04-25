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
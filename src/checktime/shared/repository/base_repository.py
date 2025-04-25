"""
Base repository interface that defines common CRUD operations.
"""

from typing import TypeVar, Generic, List, Optional, Type

from checktime.shared.db import db

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Base repository interface with common CRUD operations."""
    
    def __init__(self, model_class: Type[T]):
        """Initialize the repository with the model class."""
        self.model_class = model_class
    
    def get_all(self) -> List[T]:
        """Get all records."""
        return self.model_class.query.all()
    
    def get_by_id(self, id: int) -> Optional[T]:
        """Get a record by ID."""
        return self.model_class.query.get(id)
    
    def create(self, entity: T) -> T:
        """Create a new record."""
        db.session.add(entity)
        db.session.commit()
        return entity
    
    def update(self, entity: T) -> T:
        """Update a record."""
        db.session.commit()
        return entity
    
    def delete(self, entity: T) -> None:
        """Delete a record."""
        db.session.delete(entity)
        db.session.commit()
    
    def save(self, entity: T) -> T:
        """Create or update a record."""
        db.session.add(entity)
        db.session.commit()
        return entity
        
    def commit(self) -> None:
        """Commit changes to the database."""
        db.session.commit() 
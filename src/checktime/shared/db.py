"""
Database connection and utilities for CheckTime.
"""

import logging
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from checktime.shared.config import get_database_url

# Initialize SQLAlchemy objects
db = SQLAlchemy()
Base = declarative_base()

# Create logger
logger = logging.getLogger(__name__)

def init_db(app=None):
    """
    Initialize the database connection.
    
    Args:
        app: Flask app to initialize with (optional)
    
    Returns:
        SQLAlchemy db instance
    """
    if app:
        # Flask app integration
        db.init_app(app)
        
        # Create tables
        with app.app_context():
            db.create_all()
            logger.info("Database tables created")
        
        return db
    
    # Standalone SQLAlchemy session (for scheduler or scripts)
    engine = create_engine(get_database_url())
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    Base.query = Session.query_property()
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    return Session

def get_session():
    """
    Get a database session for standalone operations.
    
    Returns:
        SQLAlchemy session
    """
    engine = create_engine(get_database_url())
    session_factory = sessionmaker(bind=engine)
    return scoped_session(session_factory)

# Common model mixin for timestamps
class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to models."""
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now) 
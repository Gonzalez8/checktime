"""
User model for CheckTime.
"""

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from checktime.shared.db import db, TimestampMixin
from checktime.utils.crypto import encrypt_string, decrypt_string

class User(UserMixin, db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    
    # CheckJC credentials
    checkjc_username = db.Column(db.String(120), nullable=True)
    checkjc_password_encrypted = db.Column("checkjc_password", db.String(512), nullable=True)
    checkjc_subdomain = db.Column(db.String(64), nullable=False, default="")
    auto_checkin_enabled = db.Column(db.Boolean, default=True)
    
    # Telegram settings
    telegram_chat_id = db.Column(db.String(50), nullable=True)
    telegram_notifications_enabled = db.Column(db.Boolean, default=True)
    
    # Relationships
    holidays = db.relationship('Holiday', backref='user', lazy=True, cascade="all, delete-orphan")
    schedule_periods = db.relationship('SchedulePeriod', backref='user', lazy=True, cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password) 
        
    def set_checkjc_password(self, password):
        """Store the CheckJC password encrypted."""
        if password:
            self.checkjc_password_encrypted = encrypt_string(password)
        else:
            self.checkjc_password_encrypted = None
        
    @property
    def checkjc_password(self):
        """Returns the decrypted CheckJC password."""
        if self.checkjc_password_encrypted:
            return decrypt_string(self.checkjc_password_encrypted)
        return None
        
    def has_checkjc_configured(self):
        """Check if the user has CheckJC credentials configured."""
        return (
            self.checkjc_username is not None and 
            self.checkjc_password_encrypted is not None and
            self.auto_checkin_enabled
        )
        
    def has_telegram_configured(self):
        """Check if the user has Telegram notifications configured."""
        return (
            self.telegram_chat_id is not None and
            self.telegram_notifications_enabled
        ) 
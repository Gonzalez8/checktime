"""
User model for CheckTime.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from checktime.shared.db import db, TimestampMixin
from checktime.utils.crypto import encrypt_string, decrypt_string

PASSWORD_RESET_TOKEN_TTL_MINUTES = 30

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

    # Password reset
    password_reset_token_hash = db.Column(db.String(128), nullable=True)
    password_reset_token_expires_at = db.Column(db.DateTime, nullable=True)

    # Optional per-user Google Gemini API key (encrypted at rest).
    # If set, the captcha solver uses the LLM instead of asking the user
    # via Telegram. Stored encrypted via checktime.utils.crypto, same as
    # CheckJC passwords.
    google_api_key_encrypted = db.Column("google_api_key", db.String(512), nullable=True)

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

    def set_google_api_key(self, api_key):
        """Store the Google Gemini API key encrypted at rest.

        Pass an empty string / None to clear the stored key.
        """
        if api_key:
            self.google_api_key_encrypted = encrypt_string(api_key)
        else:
            self.google_api_key_encrypted = None

    @property
    def google_api_key(self):
        """Decrypted Gemini API key, or None if not configured."""
        if self.google_api_key_encrypted:
            try:
                return decrypt_string(self.google_api_key_encrypted)
            except Exception:
                return None
        return None

    def has_google_api_key(self):
        return self.google_api_key_encrypted is not None

    @staticmethod
    def _hash_reset_token(raw_token: str) -> str:
        """Return the SHA-256 hex digest used to store reset tokens."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def generate_password_reset_token(self) -> str:
        """Generate a single-use reset token, store its hash, and return the raw value."""
        raw_token = secrets.token_urlsafe(32)
        self.password_reset_token_hash = self._hash_reset_token(raw_token)
        self.password_reset_token_expires_at = (
            datetime.now() + timedelta(minutes=PASSWORD_RESET_TOKEN_TTL_MINUTES)
        )
        return raw_token

    def clear_password_reset_token(self) -> None:
        self.password_reset_token_hash = None
        self.password_reset_token_expires_at = None

    def password_reset_token_matches(self, raw_token: str) -> bool:
        """Constant-time check of a reset token against the stored hash and expiry."""
        if not raw_token or not self.password_reset_token_hash:
            return False
        if not self.password_reset_token_expires_at:
            return False
        if datetime.now() > self.password_reset_token_expires_at:
            return False
        candidate = self._hash_reset_token(raw_token)
        return secrets.compare_digest(candidate, self.password_reset_token_hash)

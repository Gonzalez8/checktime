"""
Utilities for encrypting and decrypting sensitive data.
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def get_encryption_key():
    """
    Get or generate the encryption key using environment variable.
    The key is derived using PBKDF2 from a master key.
    """
    # Get master key from environment
    master_key = os.getenv('ENCRYPTION_KEY')
    if not master_key:
        raise ValueError("ENCRYPTION_KEY environment variable must be set")

    # Use PBKDF2 to derive a key
    salt = b'checktime_salt'  # Fixed salt for consistency
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
    return key

def encrypt_string(text: str) -> str:
    """
    Encrypt a string using Fernet symmetric encryption.
    
    Args:
        text (str): Text to encrypt
        
    Returns:
        str: Encrypted text in base64 format
    """
    if not text:
        return text
        
    f = Fernet(get_encryption_key())
    encrypted_data = f.encrypt(text.encode())
    return encrypted_data.decode()

def decrypt_string(encrypted_text: str) -> str:
    """
    Decrypt a string that was encrypted using Fernet.
    
    Args:
        encrypted_text (str): Encrypted text in base64 format
        
    Returns:
        str: Decrypted text
    """
    if not encrypted_text:
        return encrypted_text
        
    f = Fernet(get_encryption_key())
    decrypted_data = f.decrypt(encrypted_text.encode())
    return decrypted_data.decode() 
"""
Fernet symmetric encryption for SMTP/IMAP passwords.
All passwords are encrypted before storing in SQLite and decrypted only at runtime.
"""

import os
from cryptography.fernet import Fernet


def get_fernet() -> Fernet:
    """Get Fernet instance using SECRET_KEY from environment."""
    key = os.environ.get("SECRET_KEY")
    if not key:
        raise RuntimeError("SECRET_KEY not set in environment. Check your .env file.")
    return Fernet(key.encode())


def encrypt_password(plain: str) -> str:
    """Encrypt a plaintext password using Fernet symmetric encryption."""
    return get_fernet().encrypt(plain.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted password string."""
    return get_fernet().decrypt(encrypted.encode()).decode()

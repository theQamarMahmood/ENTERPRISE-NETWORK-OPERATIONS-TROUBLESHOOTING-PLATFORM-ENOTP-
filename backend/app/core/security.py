import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
from cryptography.fernet import Fernet
from app.core.config import settings

# Symmetric Encryption (AES-GCM via Fernet) for SNMP/SSH credentials
fernet_cipher = Fernet(settings.ENCRYPTION_KEY.encode())

def get_password_hash(password: str) -> str:
    """Hash password using native PBKDF2-HMAC-SHA256 to ensure Windows portability."""
    salt = os.urandom(16)
    db_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return f"{salt.hex()}${db_hash.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored salt and PBKDF2 hash."""
    try:
        if not hashed_password or "$" not in hashed_password:
            return False
        salt_hex, hash_hex = hashed_password.split('$')
        salt = bytes.fromhex(salt_hex)
        db_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode(), salt, 100000)
        return db_hash.hex() == hash_hex
    except Exception:
        return False

def encrypt_credential(plain_text: str) -> str:
    """Encrypts a credential for storage in the DB."""
    if not plain_text:
        return ""
    return fernet_cipher.encrypt(plain_text.encode()).decode()

def decrypt_credential(cipher_text: str) -> str:
    """Decrypts a credential retrieved from the DB."""
    if not cipher_text:
        return ""
    return fernet_cipher.decrypt(cipher_text.encode()).decode()

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

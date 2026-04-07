from cryptography.fernet import Fernet
import base64
import hashlib
from typing import Optional
from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY.encode("utf-8")
    if len(key) < 32:
        key = hashlib.sha256(key).digest()
    else:
        key = key[:32]
    key_b64 = base64.urlsafe_b64encode(key)
    return Fernet(key_b64)


def encrypt_field(plaintext: str) -> Optional[str]:
    if not plaintext:
        return None
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_field(ciphertext: str) -> Optional[str]:
    if not ciphertext:
        return None
    fernet = _get_fernet()
    decrypted = fernet.decrypt(ciphertext.encode("utf-8"))
    return decrypted.decode("utf-8")


def mask_field(value: str, visible_chars: int = 3) -> str:
    if not value or len(value) <= visible_chars:
        return value
    return value[:visible_chars] + "*" * (len(value) - visible_chars)

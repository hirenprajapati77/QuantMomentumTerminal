import base64
import hashlib
from cryptography.fernet import Fernet
from backend.app.config.settings import settings


def _get_fernet() -> Fernet:
    """
    Derive a 32-byte Fernet key from SECRET_KEY using SHA-256.
    Fernet requires a URL-safe base64-encoded 32-byte key.
    """
    raw = settings.SECRET_KEY.encode()
    digest = hashlib.sha256(raw).digest()          # always 32 bytes
    key = base64.urlsafe_b64encode(digest)         # Fernet-compatible key
    return Fernet(key)


def encrypt_str(plaintext: str) -> str:
    """Encrypt a string and return a base64 Fernet token (str)."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_str(token: str) -> str:
    """Decrypt a Fernet token string and return the original plaintext."""
    f = _get_fernet()
    return f.decrypt(token.encode()).decode()

"""
Symmetric encryption for anything sensitive we persist — currently Gmail
OAuth access/refresh tokens (spec section 40: "Encrypt OAuth tokens").

Never log or return the plaintext token outside this module and the code
that immediately needs to call the Gmail API with it.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config.settings import get_settings


def _derive_fernet_key(secret_key: str) -> bytes:
    """Fernet needs a 32-byte urlsafe-base64 key; derive one from SECRET_KEY
    so operators only need to manage a single secret."""
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(_derive_fernet_key(settings.secret_key))


def encrypt_token(plaintext: str) -> str:
    """Returns a Fernet-encrypted, base64-encoded string safe to store in a
    text/varchar column."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Raises ValueError if the token is invalid/corrupted/from a different
    SECRET_KEY, rather than leaking a cryptography-library exception."""
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Token could not be decrypted — invalid or wrong SECRET_KEY") from exc

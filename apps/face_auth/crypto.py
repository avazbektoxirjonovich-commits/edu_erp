"""
Encrypt / decrypt face embeddings at rest.
Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
Key must be a URL-safe base64-encoded 32-byte value stored in
the FACE_ENCRYPTION_KEY environment variable.

Generate a key once with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import json
import logging
from typing import Optional

logger = logging.getLogger('apps.face_auth')


def _get_fernet():
    from cryptography.fernet import Fernet
    from django.conf import settings

    key = getattr(settings, 'FACE_ENCRYPTION_KEY', '') or ''
    if not key:
        raise ValueError(
            "FACE_ENCRYPTION_KEY muhit o'zgaruvchisi o'rnatilmagan. "
            "python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\" buyrug'i bilan kalit yarating."
        )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_embedding(embedding: list) -> str:
    """Encrypt a float list (face embedding) to a ciphertext string."""
    fernet = _get_fernet()
    raw    = json.dumps(embedding).encode('utf-8')
    return fernet.encrypt(raw).decode('utf-8')


def decrypt_embedding(ciphertext: str) -> Optional[list]:
    """Decrypt a ciphertext string back to a float list. Returns None on error."""
    try:
        from cryptography.fernet import InvalidToken
        fernet = _get_fernet()
        raw    = fernet.decrypt(ciphertext.encode('utf-8'))
        return json.loads(raw)
    except Exception as exc:
        logger.error("Embedding shifrlashni ochishda xatolik: %s", exc)
        return None

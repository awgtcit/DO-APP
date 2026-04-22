"""Helpers for encrypting/decrypting sensitive admin secrets."""

import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _resolve_key() -> bytes:
    """
    Resolve Fernet key from env.

    If EMAIL_ENCRYPTION_KEY is not present, derive a deterministic key from
    FLASK_SECRET_KEY so values are still encrypted at rest.
    """
    raw_key = os.environ.get("EMAIL_ENCRYPTION_KEY", "").strip()
    if raw_key:
        return raw_key.encode("utf-8")

    fallback = os.environ.get("FLASK_SECRET_KEY", "local-dev-fallback")
    digest = hashlib.sha256(fallback.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    cipher = Fernet(_resolve_key())
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    cipher = Fernet(_resolve_key())
    return cipher.decrypt(value.encode("utf-8")).decode("utf-8")

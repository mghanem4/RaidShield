from __future__ import annotations

import hashlib
import hmac
import unicodedata

from cryptography.fernet import Fernet

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)


def pseudonymize(platform: str, identifier: str, key: str) -> str:
    if not key:
        raise ValueError("Pseudonymization key is not configured")
    return hmac.new(key.encode(), f"{platform}:{identifier}".encode(), hashlib.sha256).hexdigest()


def display_pseudonym(digest: str) -> str:
    return f"Participant {digest[:4].upper()}"


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH).lower().split())


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()


def encrypt_text(text: str, key: str) -> str:
    return Fernet(key.encode()).encrypt(text.encode()).decode()


def decrypt_text(token: str, key: str) -> str:
    return Fernet(key.encode()).decrypt(token.encode()).decode()

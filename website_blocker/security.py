from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ITERATIONS = 310_000


def create_pin_hash(pin: str) -> tuple[str, str]:
    if len(pin) < 4:
        raise ValueError("PIN must contain at least 4 characters")
    salt = secrets.token_bytes(18)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, ITERATIONS)
    return base64.b64encode(salt).decode("ascii"), base64.b64encode(digest).decode("ascii")


def verify_pin(pin: str, salt_text: str, digest_text: str) -> bool:
    try:
        salt = base64.b64decode(salt_text.encode("ascii"), validate=True)
        expected = base64.b64decode(digest_text.encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, ITERATIONS)
    return hmac.compare_digest(actual, expected)


"""PASSWORD HASHING and JWT Helpers"""

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings
_N, _R, _P = 2**14, 8, 1

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r = _R, p = _P, dklen=32)
    return "scrypt${}${}".format(base64.b64encode(salt).decode, base64.b64encode(dk).decode())

def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, dk_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
        dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r = _R, p = _P, dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False
    
def create_access_token(user_id: int, role:str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithms= [settings.jwt_algorithm])

def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None

"""Password-based encryption for private content in the public repo / site.

Reading & writing exercises, answers and feedback are committed only as encrypted envelopes.
The site decrypts them in the browser with the same password (site/js/crypto.js — keep the
format in sync): PBKDF2-SHA256 (600k iterations) -> AES-256-GCM, base64 fields.

Security rests on the password: the ciphertext is public, so use a long, unique password.
"""

import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 600_000
PASSWORD_ENV = "WRITING_PASSWORD"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(password.encode("utf-8"))


def encrypt_json(data: dict, password: str) -> dict:
    salt, iv = os.urandom(16), os.urandom(12)
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    ciphertext = AESGCM(_derive_key(password, salt, ITERATIONS)).encrypt(iv, plaintext, None)
    return {
        "v": 1,
        "kdf": "PBKDF2-SHA256",
        "iter": ITERATIONS,
        "salt": _b64(salt),
        "iv": _b64(iv),
        "ct": _b64(ciphertext),
    }


def decrypt_json(envelope: dict, password: str) -> dict:
    key = _derive_key(password, base64.b64decode(envelope["salt"]), envelope["iter"])
    plaintext = AESGCM(key).decrypt(
        base64.b64decode(envelope["iv"]), base64.b64decode(envelope["ct"]), None
    )
    return json.loads(plaintext)


def password_from_env() -> str | None:
    password = os.environ.get(PASSWORD_ENV, "").strip()
    return password or None

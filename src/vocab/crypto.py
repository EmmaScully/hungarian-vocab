"""Password-based encryption for everything private in the public repo / site.

All data under data/ (word lists, bank, test results, writing, lessons) is committed only as
encrypted envelopes. The site decrypts them in the browser with the same password
(site/js/crypto.js — keep the format in sync): PBKDF2-SHA256 (600k iterations) ->
AES-256-GCM, base64 fields.

Files share one public salt (data/crypto.json) so the browser derives the key once per visit;
every file gets its own random IV. Security rests on the password: the ciphertext is public,
so use a long, unique password.
"""

import base64
import json
import os
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 600_000
PASSWORD_ENV = "WRITING_PASSWORD"
SALT_FILE = "crypto.json"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


@lru_cache(maxsize=16)
def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(password.encode("utf-8"))


def encrypt_json(data: dict, password: str, salt: bytes | None = None) -> dict:
    salt = salt or os.urandom(16)
    iv = os.urandom(12)
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


def load_or_create_salt(data_dir: Path) -> bytes:
    """The shared, public salt for this data directory (created on first use)."""
    path = data_dir / SALT_FILE
    if path.exists():
        return base64.b64decode(json.loads(path.read_text(encoding="utf-8"))["salt"])
    salt = os.urandom(16)
    data_dir.mkdir(parents=True, exist_ok=True)
    info = {"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITERATIONS, "salt": _b64(salt)}
    path.write_text(json.dumps(info) + "\n", encoding="utf-8")
    return salt


def password_from_env() -> str | None:
    password = os.environ.get(PASSWORD_ENV, "").strip()
    return password or None

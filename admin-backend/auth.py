"""
Administrator accounts for the relay's admin dashboard.

Accounts live in admin_credentials.json beside this file — never in the source
code, and not in sentinet.db, so flush_db does not lock the administrator out.
Passwords are stored only as a salted PBKDF2-HMAC-SHA256 hash, so the file does
not reveal them. The file is git-ignored; each relay machine creates its own.

Create or change an account from the admin-backend folder:

    python auth.py set ADM-7734-ALPHA      (prompts for the password twice)
    python auth.py list

Normally you need neither: when the relay starts it creates the account named
by ADMIN_DIGITAL_ID / ADMIN_PASSWORD in admin-backend/.env, and updates its
password if that line changes. Use `set` only if you leave ADMIN_PASSWORD empty.
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
from typing import Dict, Optional, Tuple

CREDENTIALS_PATH = os.environ.get(
    "ADMIN_CREDENTIALS_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_credentials.json"),
)

# OWASP's current guidance for PBKDF2-HMAC-SHA256.
PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 8

# After this many wrong passwords for one digital ID from one address, refuse
# further attempts from there for LOCKOUT_SECONDS.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


def _hash(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def _load() -> Dict[str, Dict[str, object]]:
    try:
        with open(CREDENTIALS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data.get("accounts", {}) if isinstance(data, dict) else {}


def _save(accounts: Dict[str, Dict[str, object]]) -> None:
    tmp = CREDENTIALS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"accounts": accounts}, f, indent=2)
    os.replace(tmp, CREDENTIALS_PATH)
    try:
        os.chmod(CREDENTIALS_PATH, 0o600)   # readable by the relay's user only
    except OSError:
        pass


def has_accounts() -> bool:
    return bool(_load())


def set_password(digital_id: str, password: str) -> None:
    """Create the account, or replace its password."""
    digital_id = digital_id.strip()
    if not digital_id:
        raise ValueError("The digital ID cannot be empty.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"The password must be at least {MIN_PASSWORD_LENGTH} characters.")
    salt = secrets.token_bytes(16)
    accounts = _load()
    accounts[digital_id] = {
        "salt": salt.hex(),
        "hash": _hash(password, salt, PBKDF2_ITERATIONS).hex(),
        "iterations": PBKDF2_ITERATIONS,
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save(accounts)


def ensure_account(digital_id: str, password: str) -> Optional[str]:
    """
    Make sure the account configured in .env exists with that password.

    Called when the relay starts. Returns a line describing what was done, or
    None if the account was already in place (or none is configured). The
    password itself is never written to the accounts file — only its hash.
    """
    digital_id = (digital_id or "").strip()
    if not digital_id or not password:
        return None
    if verify(digital_id, password):
        return None
    existed = digital_id in _load()
    try:
        set_password(digital_id, password)
    except ValueError as exc:
        return f"could not set up administrator {digital_id} from .env: {exc}"
    return (f"administrator {digital_id} "
            f"{'password updated' if existed else 'account created'} from admin-backend/.env")


# Checked against for an unknown digital ID, so a wrong ID takes as long as a
# wrong password and response times do not reveal which IDs exist.
_DUMMY_SALT = secrets.token_bytes(16)
_DUMMY_HASH = _hash("not-a-real-password", _DUMMY_SALT, PBKDF2_ITERATIONS)


def verify(digital_id: str, password: str) -> bool:
    account = _load().get((digital_id or "").strip())
    if not isinstance(account, dict):
        hmac.compare_digest(_hash(password or "", _DUMMY_SALT, PBKDF2_ITERATIONS), _DUMMY_HASH)
        return False
    try:
        salt = bytes.fromhex(str(account["salt"]))
        expected = bytes.fromhex(str(account["hash"]))
        iterations = int(account.get("iterations", PBKDF2_ITERATIONS))
    except (KeyError, ValueError, TypeError):
        return False
    return hmac.compare_digest(_hash(password or "", salt, iterations), expected)


# ─── Brute-force protection ──────────────────────────────────────────────────

_failures: Dict[Tuple[str, str], Tuple[int, float]] = {}
_failures_lock = threading.Lock()


def locked_out_for(digital_id: str, client: str) -> int:
    """Seconds until this ID may try again from this address; 0 if it may now."""
    with _failures_lock:
        count, since = _failures.get(((digital_id or "").strip().lower(), client), (0, 0.0))
    if count < MAX_FAILED_ATTEMPTS:
        return 0
    remaining = int(since + LOCKOUT_SECONDS - time.time())
    if remaining <= 0:
        with _failures_lock:
            _failures.pop(((digital_id or "").strip().lower(), client), None)
        return 0
    return remaining


def record_attempt(digital_id: str, client: str, success: bool) -> None:
    key = ((digital_id or "").strip().lower(), client)
    with _failures_lock:
        if success:
            _failures.pop(key, None)
        else:
            count, _ = _failures.get(key, (0, 0.0))
            _failures[key] = (count + 1, time.time())


# ─── Command line ────────────────────────────────────────────────────────────

def _main(argv) -> int:
    if len(argv) >= 2 and argv[1] == "list":
        accounts = _load()
        if not accounts:
            print("No administrator accounts yet.")
        for digital_id, account in accounts.items():
            print(f"{digital_id}  (password last set {account.get('updated', 'unknown')})")
        return 0

    if len(argv) >= 2 and argv[1] == "set":
        digital_id = argv[2] if len(argv) >= 3 else input("Administrator digital ID: ").strip()
        while True:
            password = getpass.getpass(f"Password for {digital_id}: ")
            if password != getpass.getpass("Repeat the password: "):
                print("The passwords did not match. Try again.")
                continue
            try:
                set_password(digital_id, password)
            except ValueError as exc:
                print(exc)
                continue
            break
        print(f"Saved. {digital_id} can now sign in to the admin dashboard.")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))

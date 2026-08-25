"""Citizen privacy and phone number hashing.

Ensures raw phone numbers from WhatsApp/Telegram never enter the database or logs.
Conforms to docs/DATA-CONTRACT.md (reporter_hash = 'sha256:...').
"""

import hashlib
import os
import re

DEFAULT_SALT = os.environ.get("PHONE_SALT", "neerdrishti-default-salt-2026")


def normalize_phone(phone: str) -> str:
    """Normalize phone number to standard digits-only format."""
    digits = re.sub(r"\D", "", phone)
    # Strip leading 91 for Indian phone numbers if 12 digits
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def hash_phone_number(phone: str, salt: str = DEFAULT_SALT) -> str:
    """Compute salted SHA-256 hash of a phone number.

    Returns:
        String prefixed with 'sha256:' followed by hex digest.
    """
    clean_phone = normalize_phone(phone)
    if not clean_phone:
        return "sha256:anonymous"

    payload = f"{clean_phone}:{salt}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest[:32]}"

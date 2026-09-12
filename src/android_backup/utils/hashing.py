"""Hashing and APK validation utilities."""

import hashlib
from pathlib import Path
from typing import Optional


def compute_sha256(file_path: Path) -> Optional[str]:
    """Compute SHA256 hash of file."""
    try:
        hasher = hashlib.sha256()
        with file_path.open('rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def is_valid_apk(file_path: Path) -> bool:
    """Check if file is a valid APK (ZIP magic bytes PK\\x03\\x04)."""
    try:
        with file_path.open('rb') as f:
            magic = f.read(4)
            return magic == b'PK\x03\x04'
    except OSError:
        return False


def validate_apk(file_path: Path) -> tuple[bool, Optional[str], int]:
    """
    Validate APK file.
    Returns: (is_valid, sha256_hash, file_size)
    """
    if not file_path.exists():
        return False, None, 0

    size = file_path.stat().st_size
    if size == 0:
        return False, None, 0

    if not is_valid_apk(file_path):
        return False, None, size

    sha256 = compute_sha256(file_path)
    return True, sha256, size

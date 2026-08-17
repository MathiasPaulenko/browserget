"""Checksum computation and verification using hashlib."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from browserget.exceptions import ChecksumMismatchError

_CHUNK_SIZE = 8192


def compute_checksum(filepath: Path, algorithm: str) -> str:
    """Compute the hex digest of a file using the specified algorithm.

    Reads the file in 8192-byte chunks to handle files larger than memory.

    Args:
        filepath: Path to the file to hash.
        algorithm: Hash algorithm name (e.g. "sha256", "sha512").

    Returns:
        The hexadecimal digest string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the algorithm is not supported by hashlib.
    """
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as exc:
        raise ValueError(f"Unsupported algorithm: {algorithm}") from exc

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_checksum(filepath: Path, expected: str, algorithm: str) -> bool:
    """Verify that a file's checksum matches the expected value.

    Args:
        filepath: Path to the file to verify.
        expected: Expected hexadecimal digest.
        algorithm: Hash algorithm name (e.g. "sha256", "sha512").

    Returns:
        True if the computed checksum matches the expected value.
    """
    actual = compute_checksum(filepath, algorithm)
    return hmac.compare_digest(actual, expected)


def verify_or_raise(filepath: Path, expected: str, algorithm: str) -> None:
    """Verify a file's checksum, raising on mismatch.

    Args:
        filepath: Path to the file to verify.
        expected: Expected hexadecimal digest.
        algorithm: Hash algorithm name (e.g. "sha256", "sha512").

    Raises:
        ChecksumMismatchError: If the computed checksum does not match.
    """
    actual = compute_checksum(filepath, algorithm)
    if not hmac.compare_digest(actual, expected):
        raise ChecksumMismatchError(
            filename=filepath.name,
            expected=expected,
            actual=actual,
        )

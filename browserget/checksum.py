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


def _normalize_expected(expected: str) -> str | None:
    """Normalize an expected checksum for comparison.

    Upstream checksum formats vary (uppercase hex, surrounding whitespace),
    so the expected value is lowercased and stripped. Non-hex or non-ASCII
    input can never match a hex digest, so it returns ``None`` instead of
    letting ``hmac.compare_digest`` raise ``TypeError``.

    Args:
        expected: Expected hexadecimal digest as provided upstream.

    Returns:
        The normalized digest, or ``None`` if it is not valid lowercase hex.
    """
    normalized = expected.strip().lower()
    if not normalized.isascii() or not all(c in "0123456789abcdef" for c in normalized):
        return None
    return normalized


def verify_checksum(filepath: Path, expected: str, algorithm: str) -> bool:
    """Verify that a file's checksum matches the expected value.

    Args:
        filepath: Path to the file to verify.
        expected: Expected hexadecimal digest (any letter case).
        algorithm: Hash algorithm name (e.g. "sha256", "sha512").

    Returns:
        True if the computed checksum matches the expected value.
    """
    actual = compute_checksum(filepath, algorithm)
    normalized = _normalize_expected(expected)
    if normalized is None:
        return False
    return hmac.compare_digest(actual, normalized)


def verify_or_raise(filepath: Path, expected: str, algorithm: str) -> None:
    """Verify a file's checksum, raising on mismatch.

    Args:
        filepath: Path to the file to verify.
        expected: Expected hexadecimal digest (any letter case).
        algorithm: Hash algorithm name (e.g. "sha256", "sha512").

    Raises:
        ChecksumMismatchError: If the computed checksum does not match.
    """
    actual = compute_checksum(filepath, algorithm)
    normalized = _normalize_expected(expected)
    if normalized is None or not hmac.compare_digest(actual, normalized):
        raise ChecksumMismatchError(
            filename=filepath.name,
            expected=expected,
            actual=actual,
        )

"""Unit tests for checksum computation and verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from browserget.checksum import compute_checksum, verify_checksum, verify_or_raise
from browserget.exceptions import ChecksumMismatchError


def _write_file(path: Path, content: bytes) -> Path:
    """Write content to a file and return the path."""
    path.write_bytes(content)
    return path


class TestComputeChecksum:
    """Tests for compute_checksum()."""

    def test_sha256_on_known_content(self, tmp_path: Path) -> None:
        """compute_checksum with sha256 should match hashlib output."""
        filepath = _write_file(tmp_path / "test.bin", b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert compute_checksum(filepath, "sha256") == expected

    def test_sha512_on_known_content(self, tmp_path: Path) -> None:
        """compute_checksum with sha512 should match hashlib output."""
        filepath = _write_file(tmp_path / "test.bin", b"hello world")
        expected = hashlib.sha512(b"hello world").hexdigest()
        assert compute_checksum(filepath, "sha512") == expected

    def test_chunked_reading_large_file(self, tmp_path: Path) -> None:
        """compute_checksum should work on files larger than the chunk size."""
        content = b"x" * (1024 * 1024)  # 1 MB
        filepath = _write_file(tmp_path / "large.bin", content)
        expected = hashlib.sha256(content).hexdigest()
        assert compute_checksum(filepath, "sha256") == expected

    def test_empty_file_valid_hash(self, tmp_path: Path) -> None:
        """compute_checksum on an empty file should produce a valid hash."""
        filepath = _write_file(tmp_path / "empty.bin", b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert compute_checksum(filepath, "sha256") == expected

    def test_unsupported_algorithm_raises_valueerror(self, tmp_path: Path) -> None:
        """compute_checksum with an unsupported algorithm should raise ValueError."""
        filepath = _write_file(tmp_path / "test.bin", b"data")
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            compute_checksum(filepath, "md999")

    def test_nonexistent_file_raises_filenotfounderror(self, tmp_path: Path) -> None:
        """compute_checksum on a non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            compute_checksum(tmp_path / "nonexistent.bin", "sha256")


class TestVerifyChecksum:
    """Tests for verify_checksum()."""

    def test_returns_true_on_match(self, tmp_path: Path) -> None:
        """verify_checksum should return True when checksums match."""
        filepath = _write_file(tmp_path / "test.bin", b"hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert verify_checksum(filepath, expected, "sha256") is True

    def test_returns_false_on_mismatch(self, tmp_path: Path) -> None:
        """verify_checksum should return False when checksums don't match."""
        filepath = _write_file(tmp_path / "test.bin", b"hello")
        assert verify_checksum(filepath, "wronghash", "sha256") is False


class TestVerifyOrRaise:
    """Tests for verify_or_raise()."""

    def test_passes_silently_on_match(self, tmp_path: Path) -> None:
        """verify_or_raise should not raise when checksums match."""
        filepath = _write_file(tmp_path / "test.bin", b"hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        verify_or_raise(filepath, expected, "sha256")  # should not raise

    def test_raises_checksum_mismatch_error_on_mismatch(self, tmp_path: Path) -> None:
        """verify_or_raise should raise ChecksumMismatchError on mismatch."""
        filepath = _write_file(tmp_path / "test.bin", b"hello")
        with pytest.raises(ChecksumMismatchError):
            verify_or_raise(filepath, "wronghash", "sha256")

    def test_error_contains_filename(self, tmp_path: Path) -> None:
        """ChecksumMismatchError should contain the filename."""
        filepath = _write_file(tmp_path / "myapp.bin", b"hello")
        with pytest.raises(ChecksumMismatchError, match="myapp.bin"):
            verify_or_raise(filepath, "wronghash", "sha256")

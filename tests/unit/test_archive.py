"""Unit tests for safe archive extraction with path-traversal protection."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from browserget.archive import extract_tar, extract_zip


class TestExtractZip:
    """Tests for safe zip extraction."""

    def test_normal_zip_extracts_correctly(self, tmp_path: Path) -> None:
        """A well-formed zip extracts all files to the destination."""
        archive = tmp_path / "test.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("hello.txt", "Hello, World!")
            zf.writestr("subdir/nested.txt", "Nested content")

        dest = tmp_path / "dest"
        extract_zip(archive, dest)

        assert (dest / "hello.txt").read_text() == "Hello, World!"
        assert (dest / "subdir" / "nested.txt").read_text() == "Nested content"

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """A zip with ../../etc/passwd is rejected."""
        archive = tmp_path / "evil.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../../evil.txt", "pwned")

        dest = tmp_path / "dest"
        with pytest.raises(ValueError, match="escapes destination"):
            extract_zip(archive, dest)

    def test_absolute_path_blocked(self, tmp_path: Path) -> None:
        """A zip with absolute paths is rejected."""
        archive = tmp_path / "abs.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("/etc/passwd", "root")

        dest = tmp_path / "dest"
        with pytest.raises(ValueError, match="escapes destination"):
            extract_zip(archive, dest)

    def test_empty_zip_extracts_nothing(self, tmp_path: Path) -> None:
        """An empty zip extracts without error."""
        archive = tmp_path / "empty.zip"
        with zipfile.ZipFile(archive, "w"):
            pass

        dest = tmp_path / "dest"
        extract_zip(archive, dest)
        assert dest.exists()
        assert list(dest.iterdir()) == []


class TestExtractTar:
    """Tests for safe tar extraction."""

    def test_normal_tar_extracts_correctly(self, tmp_path: Path) -> None:
        """A well-formed tar.gz extracts all files to the destination."""
        archive = tmp_path / "test.tar.gz"
        data = b"Hello from tar"

        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo(name="hello.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

            info2 = tarfile.TarInfo(name="subdir/nested.txt")
            info2.size = len(data)
            tf.addfile(info2, io.BytesIO(data))

        dest = tmp_path / "dest"
        extract_tar(archive, dest)

        assert (dest / "hello.txt").read_bytes() == data
        assert (dest / "subdir" / "nested.txt").read_bytes() == data

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """A tar with ../../evil.txt is rejected."""
        archive = tmp_path / "evil.tar.gz"
        data = b"pwned"

        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo(name="../../evil.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

        dest = tmp_path / "dest"
        with pytest.raises(ValueError, match="escapes destination"):
            extract_tar(archive, dest)

    def test_absolute_path_blocked(self, tmp_path: Path) -> None:
        """A tar with absolute paths is rejected."""
        archive = tmp_path / "abs.tar.gz"
        data = b"root"

        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo(name="/etc/passwd")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

        dest = tmp_path / "dest"
        with pytest.raises(ValueError, match="escapes destination"):
            extract_tar(archive, dest)

    def test_tar_bz2_auto_detected(self, tmp_path: Path) -> None:
        """A tar.bz2 archive is auto-detected and extracted."""
        archive = tmp_path / "test.tar.bz2"
        data = b"bz2 content"

        with tarfile.open(archive, "w:bz2") as tf:
            info = tarfile.TarInfo(name="hello.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

        dest = tmp_path / "dest"
        extract_tar(archive, dest)

        assert (dest / "hello.txt").read_bytes() == data

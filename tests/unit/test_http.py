"""Unit tests for the HTTP client with mocks."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browserget.exceptions import NetworkError
from browserget.http import HttpClient


def _make_response(
    data: bytes, status: int = 200, headers: dict[str, str] | None = None
) -> MagicMock:
    """Create a mock HTTP response object.

    For download tests, read() returns the full data on first call then b""
    to simulate EOF (the download loop calls read(chunk_size) repeatedly).
    """
    resp = MagicMock()
    resp.read.side_effect = [data, b""]
    resp.status = status
    resp.headers = headers or {}
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _make_http_error(
    code: int, reason: str = "Error", headers: dict[str, str] | None = None
) -> urllib.error.HTTPError:
    """Create an HTTPError for testing."""
    return urllib.error.HTTPError(
        url="https://example.com",
        code=code,
        msg=reason,
        hdrs=headers or {},
        fp=io.BytesIO(b""),
    )


class TestGetJson:
    """Tests for get_json()."""

    async def test_returns_parsed_dict_on_200(self) -> None:
        """get_json should return a parsed dict on HTTP 200."""
        client = HttpClient(max_retries=1)
        payload = json.dumps({"key": "value"}).encode()
        with patch("urllib.request.urlopen", return_value=_make_response(payload)):
            result = await client.get_json("https://example.com/api")
        assert result == {"key": "value"}

    async def test_raises_on_empty_response(self) -> None:
        """get_json should raise NetworkError on empty response."""
        client = HttpClient(max_retries=1)
        with (
            patch("urllib.request.urlopen", return_value=_make_response(b"")),
            pytest.raises(NetworkError, match="Empty response"),
        ):
            await client.get_json("https://example.com/api")

    async def test_raises_on_invalid_json(self) -> None:
        """get_json should raise NetworkError on invalid JSON."""
        client = HttpClient(max_retries=1)
        with (
            patch("urllib.request.urlopen", return_value=_make_response(b"not json")),
            pytest.raises(NetworkError, match="Invalid JSON"),
        ):
            await client.get_json("https://example.com/api")


class TestGetText:
    """Tests for get_text()."""

    async def test_returns_string_on_200(self) -> None:
        """get_text should return the response body as a string."""
        client = HttpClient(max_retries=1)
        with patch("urllib.request.urlopen", return_value=_make_response(b"hello world")):
            result = await client.get_text("https://example.com")
        assert result == "hello world"

    async def test_raises_on_empty_response(self) -> None:
        """get_text should raise NetworkError on empty response."""
        client = HttpClient(max_retries=1)
        with (
            patch("urllib.request.urlopen", return_value=_make_response(b"")),
            pytest.raises(NetworkError, match="Empty response"),
        ):
            await client.get_text("https://example.com")


class TestRetryLogic:
    """Tests for retry behavior."""

    async def test_retry_on_429_succeeds_on_second_attempt(self) -> None:
        """429 should trigger retry and succeed on the second attempt."""
        client = HttpClient(max_retries=3)
        good_response = _make_response(b"ok")
        with (
            patch("urllib.request.urlopen", side_effect=[_make_http_error(429), good_response]),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await client.get_text("https://example.com")
        assert result == "ok"

    async def test_retry_on_503_succeeds_on_third_attempt(self) -> None:
        """503 should trigger retries and succeed on the third attempt."""
        client = HttpClient(max_retries=3)
        good_response = _make_response(b"ok")
        with (
            patch(
                "urllib.request.urlopen",
                side_effect=[_make_http_error(503), _make_http_error(503), good_response],
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await client.get_text("https://example.com")
        assert result == "ok"

    async def test_no_retry_on_404_raises_immediately(self) -> None:
        """404 should not retry and should raise NetworkError immediately."""
        client = HttpClient(max_retries=3)
        with (
            patch("urllib.request.urlopen", side_effect=_make_http_error(404)),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            pytest.raises(NetworkError, match="HTTP 404"),
        ):
            await client.get_text("https://example.com")
        mock_sleep.assert_not_called()

    async def test_no_retry_on_403_raises_immediately(self) -> None:
        """403 should not retry and should raise NetworkError immediately."""
        client = HttpClient(max_retries=3)
        with (
            patch("urllib.request.urlopen", side_effect=_make_http_error(403)),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            pytest.raises(NetworkError, match="HTTP 403"),
        ):
            await client.get_text("https://example.com")
        mock_sleep.assert_not_called()

    async def test_all_retries_exhausted_raises_network_error(self) -> None:
        """All retries exhausted should raise NetworkError."""
        client = HttpClient(max_retries=2)
        with (
            patch("urllib.request.urlopen", side_effect=_make_http_error(503)),
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(NetworkError, match="HTTP 503"),
        ):
            await client.get_text("https://example.com")

    async def test_backoff_delays_are_1s_2s_4s(self) -> None:
        """Backoff delays should follow exponential pattern: 1s, 2s, 4s."""
        client = HttpClient(max_retries=4)
        with (
            patch("urllib.request.urlopen", side_effect=_make_http_error(503)),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            pytest.raises(NetworkError),
        ):
            await client.get_text("https://example.com")

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    async def test_429_respects_retry_after_header(self) -> None:
        """429 with Retry-After header should use that value instead of backoff."""
        client = HttpClient(max_retries=3)
        error = _make_http_error(429, headers={"Retry-After": "5"})
        good_response = _make_response(b"ok")
        with (
            patch("urllib.request.urlopen", side_effect=[error, good_response]),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            result = await client.get_text("https://example.com")
        assert result == "ok"
        mock_sleep.assert_called_once_with(5.0)


class TestDownload:
    """Tests for download()."""

    async def test_writes_file_content_correctly(self, tmp_path: Path) -> None:
        """download should write the response content to the destination file."""
        client = HttpClient(max_retries=1)
        content = b"file content here"
        dest = tmp_path / "output.bin"
        with patch("urllib.request.urlopen", return_value=_make_response(content)):
            await client.download("https://example.com/file", dest)
        assert dest.read_bytes() == content

    async def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """download should create missing parent directories."""
        client = HttpClient(max_retries=1)
        dest = tmp_path / "nested" / "dirs" / "output.bin"
        with patch("urllib.request.urlopen", return_value=_make_response(b"data")):
            await client.download("https://example.com/file", dest)
        assert dest.exists()
        assert dest.read_bytes() == b"data"

    async def test_cleans_up_partial_file_on_error(self, tmp_path: Path) -> None:
        """download should delete the partial file on error."""
        client = HttpClient(max_retries=1)
        dest = tmp_path / "partial.bin"
        with (
            patch("urllib.request.urlopen", side_effect=_make_http_error(404)),
            pytest.raises(NetworkError),
        ):
            await client.download("https://example.com/file", dest)
        assert not dest.exists()

    async def test_download_retries_on_503(self, tmp_path: Path) -> None:
        """download should retry on 503 and succeed."""
        client = HttpClient(max_retries=3)
        dest = tmp_path / "output.bin"
        good_response = _make_response(b"data")
        with (
            patch("urllib.request.urlopen", side_effect=[_make_http_error(503), good_response]),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await client.download("https://example.com/file", dest)
        assert dest.read_bytes() == b"data"


class TestTimeout:
    """Tests for timeout handling."""

    async def test_timeout_raises_network_error(self) -> None:
        """Timeout should raise NetworkError."""
        client = HttpClient(max_retries=1)
        with (
            patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")),
            pytest.raises(NetworkError, match="timed out"),
        ):
            await client.get_text("https://example.com")

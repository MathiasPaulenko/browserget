"""Async HTTP client with exponential backoff retry."""

from __future__ import annotations

import asyncio
import http.client
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from browserget.exceptions import NetworkError

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_CHUNK_SIZE = 8192
_USER_AGENT = "browserget/1.0"


class HttpClient:
    """Async HTTP client using ``urllib.request`` with retry and backoff.

    Attributes:
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
    """

    def __init__(self, timeout: int = 30, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries

    async def get_json(self, url: str) -> Any:
        """Fetch a URL and parse the response as JSON.

        Args:
            url: The URL to fetch.

        Returns:
            The parsed JSON response.

        Raises:
            NetworkError: If the request fails after all retries or the
                response is not valid JSON.
        """
        text = await self._fetch_text(url)
        if not text:
            raise NetworkError(url=url, reason="Empty response body")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise NetworkError(url=url, reason="Invalid JSON response") from exc

    async def get_text(self, url: str) -> str:
        """Fetch a URL and return the raw response text.

        Args:
            url: The URL to fetch.

        Returns:
            The response body as a string.

        Raises:
            NetworkError: If the request fails after all retries or the
                response body is empty.
        """
        text = await self._fetch_text(url)
        if not text:
            raise NetworkError(url=url, reason="Empty response body")
        return text

    async def download(self, url: str, dest: Path) -> None:
        """Stream a URL to a file in chunks.

        Creates parent directories if they do not exist. If the download is
        interrupted, the partial file is deleted before retrying.

        Args:
            url: The URL to download.
            dest: Destination file path.

        Raises:
            NetworkError: If the download fails after all retries.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)

        def _cleanup() -> None:
            dest.unlink(missing_ok=True)

        await self._retry_with_backoff(
            url=url,
            action=lambda: asyncio.to_thread(self._download_sync, url, dest),
            cleanup=_cleanup,
        )

    async def _fetch_text(self, url: str) -> str:
        """Fetch a URL with retry logic and return the response text.

        Args:
            url: The URL to fetch.

        Returns:
            The response body as a string.

        Raises:
            NetworkError: If the request fails after all retries.
        """
        result = await self._retry_with_backoff(
            url=url,
            action=lambda: asyncio.to_thread(self._fetch_text_sync, url),
        )
        return cast("str", result)

    async def _retry_with_backoff(
        self,
        url: str,
        action: Callable[[], Awaitable[Any]],
        cleanup: Callable[[], None] | None = None,
    ) -> Any:
        """Execute an async action with retry and exponential backoff.

        Args:
            url: The URL being requested (for logging and error messages).
            action: A callable that returns an awaitable to execute.
            cleanup: Optional cleanup callable run before retrying or
                re-raising after failure.

        Returns:
            The result of the action.

        Raises:
            NetworkError: If the action fails after all retries.
        """

        def _safe_cleanup() -> None:
            if cleanup is not None:
                try:
                    cleanup()
                except OSError:
                    logger.warning("Cleanup failed for %s", url, exc_info=True)

        max_attempts = max(self.max_retries, 1)
        for attempt in range(1, max_attempts + 1):
            logger.info("Requesting %s (attempt %d/%d)", url, attempt, max_attempts)
            try:
                return await action()
            except urllib.error.HTTPError as exc:
                if exc.code in _RETRYABLE_STATUS_CODES and attempt < max_attempts:
                    delay = self._backoff_delay(attempt, exc)
                    logger.warning(
                        "HTTP %d for %s, retry %d/%d in %.1fs",
                        exc.code,
                        url,
                        attempt,
                        max_attempts,
                        delay,
                    )
                    _safe_cleanup()
                    await asyncio.sleep(delay)
                else:
                    _safe_cleanup()
                    raise NetworkError(url=url, reason=f"HTTP {exc.code}: {exc.reason}") from exc
            except (
                urllib.error.URLError,
                ConnectionError,
                TimeoutError,
                http.client.HTTPException,
            ) as exc:
                if attempt < max_attempts:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Network error for %s, retry %d/%d in %.1fs: %s",
                        url,
                        attempt,
                        max_attempts,
                        delay,
                        exc,
                    )
                    _safe_cleanup()
                    await asyncio.sleep(delay)
                else:
                    _safe_cleanup()
                    raise NetworkError(url=url, reason=str(exc)) from exc
            except BaseException:
                _safe_cleanup()
                raise

        raise NetworkError(url=url, reason="Max retries exhausted")

    @staticmethod
    def _encode_url(url: str) -> str:
        """Encode the path component of a URL to handle spaces and special chars.

        ``urllib.request.urlopen`` raises ``http.client.InvalidURL`` when the
        URL path contains spaces or other characters that are invalid in the
        HTTP request line.  This method encodes the path using
        ``urllib.parse.quote`` while preserving ``/`` separators.

        Args:
            url: The URL to encode.

        Returns:
            The URL with the path component percent-encoded.
        """
        parts = urllib.parse.urlsplit(url)
        encoded_path = urllib.parse.quote(parts.path, safe="/%")
        return urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment)
        )

    def _fetch_text_sync(self, url: str) -> str:
        """Synchronous fetch returning response text.

        Args:
            url: The URL to fetch.

        Returns:
            The response body decoded as UTF-8 text.

        Raises:
            NetworkError: If the response cannot be decoded as UTF-8.
        """
        encoded_url = self._encode_url(url)
        req = urllib.request.Request(encoded_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data: bytes = resp.read()
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise NetworkError(url=url, reason="Response is not valid UTF-8") from exc

    def _download_sync(self, url: str, dest: Path) -> None:
        """Synchronous streaming download to a file.

        Args:
            url: The URL to download.
            dest: Destination file path.
        """
        encoded_url = self._encode_url(url)
        req = urllib.request.Request(encoded_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(_CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)

    def _backoff_delay(self, attempt: int, exc: urllib.error.HTTPError | None = None) -> float:
        """Calculate the backoff delay for a retry attempt.

        Respects the ``Retry-After`` header for HTTP 429 responses when
        available. Otherwise uses exponential backoff: 1s, 2s, 4s, ...

        Args:
            attempt: The current attempt number (1-based).
            exc: The HTTPError that triggered the retry, if any.

        Returns:
            The delay in seconds.
        """
        if exc is not None and exc.code == 429:
            retry_after = exc.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return float(2 ** (attempt - 1))

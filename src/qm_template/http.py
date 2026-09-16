import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from qm_template import PROGRAM, __version__
from qm_template.errors import QmTemplateError
from qm_template.log import log

REQUEST_TIMEOUT = 30.0
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 1.0
USER_AGENT = f"{PROGRAM}/{__version__}"
_HREF_RE = re.compile(r'href="([^"]+)"')

T = TypeVar("T")


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or exc.code == 429
    return isinstance(exc, (urllib.error.URLError, TimeoutError))


def _fetch_bytes_once(url: str, timeout: float) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(), charset


def _http_error(url: str, exc: BaseException) -> QmTemplateError:
    if isinstance(exc, urllib.error.HTTPError):
        return QmTemplateError(f"HTTP {exc.code} for {url}")
    reason = getattr(exc, "reason", exc)
    return QmTemplateError(f"failed to fetch {url}: {reason}")


def _with_retries(
    url: str,
    fetch: Callable[[], T],
    *,
    attempts: int,
    backoff: float,
    sleep: Callable[[float], None],
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return fetch()
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt >= attempts or not _retryable(exc):
                raise _http_error(url, exc) from exc
            delay = backoff * 2 ** (attempt - 1)
            log.warning(
                "Fetching %s failed (%s), retrying in %.0f s",
                url,
                exc,
                delay,
            )
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def http_get_bytes(
    url: str,
    *,
    timeout: float = REQUEST_TIMEOUT,
    attempts: int = RETRY_ATTEMPTS,
    backoff: float = RETRY_BACKOFF,
    sleep: Callable[[float], None] | None = None,
) -> bytes:
    """Fetch a URL as bytes, retrying transient network and server errors."""
    return _with_retries(
        url,
        lambda: _fetch_bytes_once(url, timeout)[0],
        attempts=attempts,
        backoff=backoff,
        sleep=sleep or time.sleep,
    )


def http_get_text(
    url: str,
    *,
    timeout: float = REQUEST_TIMEOUT,
    attempts: int = RETRY_ATTEMPTS,
    backoff: float = RETRY_BACKOFF,
    sleep: Callable[[float], None] | None = None,
) -> str:
    """Fetch a URL as text, retrying transient network and server errors."""

    def fetch() -> str:
        body, charset = _fetch_bytes_once(url, timeout)
        return body.decode(charset, errors="replace")

    return _with_retries(
        url,
        fetch,
        attempts=attempts,
        backoff=backoff,
        sleep=sleep or time.sleep,
    )


def list_directory(url: str) -> list[str]:
    names = []
    for href in _HREF_RE.findall(http_get_text(url)):
        name = urllib.parse.unquote(href)
        name = name[2:] if name.startswith("./") else name
        names.append(name.rstrip("/"))
    return names


def natural_key(text: str) -> tuple[tuple[int, Any], ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r"(\d+)", text)
    )


def latest_name(names: Iterable[str], pattern: str, *, source: str) -> str:
    regex = re.compile(pattern)
    matches = [name for name in names if regex.fullmatch(name)]
    if not matches:
        raise QmTemplateError(f"no file matching {pattern!r} found at {source}")
    return max(matches, key=natural_key)

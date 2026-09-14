import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from typing import Any

from qm_template import PROGRAM, __version__
from qm_template.errors import QmTemplateError

REQUEST_TIMEOUT = 30.0
USER_AGENT = f"{PROGRAM}/{__version__}"
_HREF_RE = re.compile(r'href="([^"]+)"')


def http_get_text(url: str, *, timeout: float = REQUEST_TIMEOUT) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise QmTemplateError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise QmTemplateError(f"failed to fetch {url}: {exc.reason}") from exc


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

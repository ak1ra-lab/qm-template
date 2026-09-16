import hashlib
import re
from pathlib import Path

from qm_template.errors import QmTemplateError
from qm_template.http import http_get_text
from qm_template.log import log
from qm_template.signature import Signature
from qm_template.signature import verify_checksum as verify_signature

_CHECKSUM_SUFFIXES = {"sha256": ".sha256", "sha512": ".sha512"}

_CHECKSUM_PATTERNS = (
    re.compile(r"^(?P<digest>[0-9a-fA-F]{32,128})[ \t]+\*?(?P<name>\S.*?)\s*$"),
    re.compile(
        r"^(?:SHA\d+|MD5)\s*\((?P<name>.+?)\)\s*=\s*(?P<digest>[0-9a-fA-F]+)\s*$"
    ),
    re.compile(r"^(?P<digest>[0-9a-fA-F]{32,128})$"),
)


def parse_checksum(text: str, filename: str) -> str:
    entries: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "-", "Hash:")):
            continue
        for pattern in _CHECKSUM_PATTERNS:
            match = pattern.match(line)
            if match:
                groups = match.groupdict()
                entries.append((groups.get("name") or "", groups["digest"].lower()))
                break
    for name, digest in entries:
        if Path(name).name == filename:
            return digest
    if len(entries) == 1:
        return entries[0][1]
    raise QmTemplateError(f"no checksum for {filename!r} in checksum file")


def fetch_checksum(
    url: str,
    filename: str,
    *,
    signature: Signature | None = None,
    verify: bool = True,
) -> str:
    log.debug("Fetching checksum from: %s", url)
    text = http_get_text(url)
    if verify and signature is not None and signature.target == "checksum":
        verify_signature(text, signature)
    return parse_checksum(text, filename)


def verify_checksum(path: Path, expected: str, algorithm: str) -> bool:
    with path.open("rb") as handle:
        actual = hashlib.file_digest(handle, algorithm).hexdigest()
    if actual != expected.lower():
        log.debug(
            "Checksum mismatch for %s: expected %s, got %s", path, expected, actual
        )
        return False
    return True


def save_checksum(path: Path, digest: str, algorithm: str) -> Path:
    """Write a sha256sum-compatible checksum file next to the image."""
    try:
        suffix = _CHECKSUM_SUFFIXES[algorithm]
    except KeyError:
        raise QmTemplateError(f"unsupported checksum algorithm: {algorithm}") from None
    target = path.with_name(path.name + suffix)
    target.write_text(f"{digest.lower()}  {path.name}\n", encoding="ascii")
    log.debug("Wrote checksum file: %s", target)
    return target

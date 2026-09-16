import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from qm_template import PROGRAM
from qm_template.errors import QmTemplateError
from qm_template.http import http_get_bytes
from qm_template.log import log
from qm_template.shell import run

SignatureKind = Literal["detached", "clearsigned"]
SignatureTarget = Literal["checksum", "image"]


@dataclass(frozen=True)
class Signature:
    """An upstream signature that authenticates a checksum file or an image."""

    url: str
    key_url: str
    kind: SignatureKind = "detached"
    target: SignatureTarget = "checksum"
    fingerprint: str | None = None


def valid_fingerprint(output: str) -> str | None:
    """Return the primary fingerprint of the first valid signature in gpg output."""
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[:2] == ["[GNUPG:]", "VALIDSIG"]:
            return fields[-1].upper()
    return None


def _gpg() -> str:
    gpg = shutil.which("gpg")
    if gpg is None:
        raise QmTemplateError(
            "gpg not found; install gnupg or set download.verify_signature = false"
        )
    return gpg


def _import_key(gpg: str, homedir: Path, key: Path) -> None:
    result = run(
        [gpg, "--homedir", str(homedir), "--batch", "--no-tty", "--import", str(key)],
        capture=True,
    )
    if result.returncode != 0:
        log.debug("gpg import output: %s", result.stderr.strip())
        raise QmTemplateError(f"failed to import the signing key from {key}")


def verify(signature: Signature, data: Path | None, signature_bytes: bytes) -> None:
    """Verify a detached signature over data, or a clearsigned payload."""
    gpg = _gpg()
    log.info("Verifying GPG signature from: %s", signature.url)
    key_bytes = http_get_bytes(signature.key_url)
    with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-signature-") as staging:
        key = Path(staging) / "key.asc"
        key.write_bytes(key_bytes)
        signed = Path(staging) / "signature.asc"
        signed.write_bytes(signature_bytes)
        with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-gnupg-") as home:
            homedir = Path(home)
            _import_key(gpg, homedir, key)
            argv = [
                gpg,
                "--homedir",
                str(homedir),
                "--batch",
                "--no-tty",
                "--status-fd",
                "1",
                "--verify",
                str(signed),
            ]
            if data is not None:
                argv.append(str(data))
            result = run(argv, capture=True)
    fingerprint = valid_fingerprint(result.stdout)
    expected = signature.fingerprint.upper() if signature.fingerprint else None
    if result.returncode != 0 or fingerprint is None:
        log.debug("gpg output: %s", result.stderr.strip())
        raise QmTemplateError(
            f"could not verify the GPG signature from {signature.url}"
        )
    if expected is not None and fingerprint != expected:
        raise QmTemplateError(
            f"GPG signature from {signature.url} was made by key {fingerprint}, "
            f"expected {expected}"
        )
    log.debug("GPG signature verified with key %s", fingerprint)


def verify_checksum(checksum_text: str, signature: Signature) -> None:
    """Verify the signature of a checksum file."""
    if signature.kind == "clearsigned":
        verify(signature, None, checksum_text.encode("utf-8"))
        return
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write(checksum_text)
        staged = Path(handle.name)
    try:
        verify(signature, staged, http_get_bytes(signature.url))
    finally:
        staged.unlink(missing_ok=True)


def verify_image(path: Path, signature: Signature) -> None:
    """Verify a detached signature of an image file."""
    verify(signature, path, http_get_bytes(signature.url))

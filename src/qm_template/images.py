import re
from pathlib import Path

from qm_template import PROGRAM
from qm_template.errors import QmTemplateError

IMAGE_SUFFIXES = {".qcow2", ".img"}


def find_images(directory: Path, pattern: str | None) -> list[Path]:
    if not directory.is_dir():
        raise QmTemplateError(
            f"images directory not found: {directory} (run `{PROGRAM} download` first)"
        )
    images = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix in IMAGE_SUFFIXES
    )
    if pattern:
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise QmTemplateError(f"invalid pattern {pattern!r}: {exc}") from exc
        images = [
            path
            for path in images
            if regex.search(path.relative_to(directory).as_posix())
        ]
    if not images:
        raise QmTemplateError(f"no cloud images found in {directory}")
    return images

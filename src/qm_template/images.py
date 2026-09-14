import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from qm_template import PROGRAM
from qm_template.errors import QmTemplateError
from qm_template.http import natural_key

IMAGE_SUFFIXES = {".qcow2", ".img"}
CHECKSUM_SUFFIXES = {".sha256", ".sha512"}
_DATED_RELEASE = re.compile(r"v?\d{8}(?:\.\d+)?")


def find_images(
    directory: Path,
    pattern: str | None,
    *,
    required: bool = True,
) -> list[Path]:
    if not directory.is_dir():
        if required:
            raise QmTemplateError(
                f"images directory not found: {directory} "
                f"(run `{PROGRAM} download` first)"
            )
        return []
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
    if not images and required:
        raise QmTemplateError(f"no cloud images found in {directory}")
    return images


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024 or unit == "PiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")  # pragma: no cover


def image_sidecars(image: Path) -> list[Path]:
    return [
        sidecar
        for suffix in sorted(CHECKSUM_SUFFIXES)
        if (sidecar := image.with_name(image.name + suffix)).is_file()
    ]


def checksum_sidecar(image: Path) -> Path | None:
    sidecars = image_sidecars(image)
    return sidecars[0] if sidecars else None


def orphaned_sidecars(directory: Path) -> list[Path]:
    known = set(find_images(directory, None, required=False))
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file()
        and path.suffix in CHECKSUM_SUFFIXES
        and path.with_name(path.name[: -len(path.suffix)]) not in known
    )


def _group_key(image: Path, directory: Path) -> tuple[str, str, str]:
    parts = image.relative_to(directory).parts
    distro = parts[0] if parts else ""
    release = (
        parts[1] if len(parts) > 2 and not _DATED_RELEASE.fullmatch(parts[1]) else ""
    )
    return distro, release, re.sub(r"\d+", "", image.stem)


def superseded_images(images: Sequence[Path], directory: Path) -> list[Path]:
    """Return older builds whose names differ only in numeric components.

    Images in the same distro/release that share the same name except for
    digits (build dates, versions, snapshot numbers) are treated as one
    family; only the newest by natural sort order is kept.
    """
    groups: dict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for image in images:
        groups[_group_key(image, directory)].append(image)
    superseded: list[Path] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        newest = max(
            group, key=lambda path: natural_key(path.relative_to(directory).as_posix())
        )
        superseded.extend(path for path in group if path != newest)
    return sorted(superseded)

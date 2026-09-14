import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from qm_template.distros import RemoteImage
from qm_template.errors import QmTemplateError
from qm_template.log import log
from qm_template.shell import CommandGroups, flatten


class Downloader(ABC):
    """Wraps an external download command with resume support."""

    name: ClassVar[str]

    def __init__(self, connections: int = 1) -> None:
        self.connections = connections

    @classmethod
    def available(cls) -> bool:
        return shutil.which(cls.name) is not None

    @abstractmethod
    def build_command(self, url: str, destination: Path) -> CommandGroups: ...


class Aria2c(Downloader):
    name = "aria2c"

    def build_command(self, url: str, destination: Path) -> CommandGroups:
        return [
            [self.name],
            ["--continue=true"],
            ["--auto-file-renaming=false"],
            ["--allow-overwrite=true"],
            ["--file-allocation=none"],
            ["--console-log-level=warn"],
            ["--summary-interval=0"],
            [f"--max-connection-per-server={self.connections}"],
            [f"--split={self.connections}"],
            [f"--dir={destination.parent}"],
            [f"--out={destination.name}"],
            [url],
        ]


class Axel(Downloader):
    name = "axel"

    def build_command(self, url: str, destination: Path) -> CommandGroups:
        return [
            [self.name],
            [f"--num-connections={self.connections}"],
            [f"--output={destination}"],
            [url],
        ]


class Wget(Downloader):
    name = "wget"

    def build_command(self, url: str, destination: Path) -> CommandGroups:
        return [
            [self.name],
            ["--continue"],
            ["--quiet"],
            ["--show-progress"],
            [f"--output-document={destination}"],
            [url],
        ]


class Curl(Downloader):
    name = "curl"

    def build_command(self, url: str, destination: Path) -> CommandGroups:
        return [
            [self.name],
            ["--location"],
            ["--fail"],
            ["--continue-at", "-"],
            ["--retry", "5"],
            ["--retry-delay", "2"],
            ["--output", str(destination)],
            [url],
        ]


DOWNLOADERS: dict[str, type[Downloader]] = {
    downloader.name: downloader for downloader in (Aria2c, Axel, Wget, Curl)
}


def select_downloaders(
    preferred: Sequence[str], connections: int = 1
) -> list[Downloader]:
    selected = []
    for name in preferred:
        downloader_class = DOWNLOADERS.get(name)
        if downloader_class is None:
            log.warning("Unknown downloader %r in configuration", name)
            continue
        if downloader_class.available():
            selected.append(downloader_class(connections))
        else:
            log.debug("%s is not installed", name)
    if not selected:
        raise QmTemplateError(
            "none of the preferred downloaders are available: " + ", ".join(preferred)
        )
    return selected


def part_path(destination: Path) -> Path:
    return destination.with_name(destination.name + ".part")


def _run_downloaders(url: str, part: Path, downloaders: Sequence[Downloader]) -> bool:
    for downloader in downloaders:
        argv = flatten(downloader.build_command(url, part))
        log.info("Downloading %s with %s", part.name, downloader.name)
        log.debug("Running: %s", shlex.join(argv))
        try:
            result = subprocess.run(argv)
        except OSError as exc:
            log.warning("could not run %s: %s", downloader.name, exc)
            continue
        if result.returncode == 0 and part.is_file() and part.stat().st_size > 0:
            return True
        log.warning("%s failed with exit status %d", downloader.name, result.returncode)
    return False


def download_image(
    image: RemoteImage,
    destination: Path,
    downloaders: Sequence[Downloader],
) -> Path:
    part = part_path(destination)
    if part.is_file():
        log.info("Found a partial download, attempting to resume")
    if _run_downloaders(image.url, part, downloaders):
        return part
    if part.is_file():
        log.warning("Removing partial download and retrying from scratch")
        part.unlink()
        if _run_downloaders(image.url, part, downloaders):
            return part
    raise QmTemplateError(f"failed to download {image.url}")

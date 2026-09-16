import shutil
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from qm_template.errors import QmTemplateError
from qm_template.log import log
from qm_template.shell import CommandGroups, flatten, run

QEMU_IMG = "qemu-img"
SEED_LABEL = "cidata"
DEFAULT_FORMAT = "vdi"
DISK_FORMATS: dict[str, str] = {
    "vdi": ".vdi",
    "vmdk": ".vmdk",
    "qcow2": ".qcow2",
    "raw": ".raw",
    "vhdx": ".vhdx",
}


def require_tool(name: str, *, package: str) -> None:
    if shutil.which(name) is None:
        raise QmTemplateError(
            f"{name} not found; install {package} for the prepare command"
        )


class IsoBuilder(ABC):
    """Packs the NoCloud seed files into a CIDATA-labelled ISO."""

    name: ClassVar[str]

    @abstractmethod
    def build_command(
        self, destination: Path, sources: Sequence[Path]
    ) -> CommandGroups: ...


class MkisofsBuilder(IsoBuilder):
    """genisoimage, mkisofs and xorriso share the mkisofs command line."""

    prefix: ClassVar[tuple[str, ...]] = ()

    def build_command(
        self, destination: Path, sources: Sequence[Path]
    ) -> CommandGroups:
        prefix: CommandGroups = [list(self.prefix)] if self.prefix else []
        return [
            [self.name],
            *prefix,
            ["-output", str(destination)],
            ["-volid", SEED_LABEL],
            ["-joliet"],
            ["-rock"],
            *([str(source)] for source in sources),
        ]


class Genisoimage(MkisofsBuilder):
    name = "genisoimage"


class Xorriso(MkisofsBuilder):
    name = "xorriso"
    prefix = ("-as", "mkisofs")


class Mkisofs(MkisofsBuilder):
    name = "mkisofs"


ISO_BUILDERS: dict[str, type[IsoBuilder]] = {
    builder.name: builder for builder in (Genisoimage, Xorriso, Mkisofs)
}


def select_iso_builder(preferred: Sequence[str]) -> IsoBuilder:
    """Return the first available ISO builder from the preference order."""
    for name in preferred:
        builder_class = ISO_BUILDERS.get(name)
        if builder_class is None:
            log.warning("Unknown ISO tool %r in configuration", name)
            continue
        if shutil.which(builder_class.name) is not None:
            return builder_class()
        log.debug("%s is not installed", name)
    raise QmTemplateError(
        "none of the preferred ISO tools are available: " + ", ".join(preferred)
    )


def convert_command(image: Path, destination: Path, format: str) -> CommandGroups:
    return [[QEMU_IMG], ["convert"], ["-O", format], [str(image)], [str(destination)]]


def run_tool(command: CommandGroups) -> None:
    argv = flatten(command)
    result = run(argv)
    if result.returncode != 0:
        raise QmTemplateError(f"{argv[0]} failed with exit status {result.returncode}")

import shutil
from collections.abc import Sequence
from pathlib import Path

from qm_template.errors import QmTemplateError
from qm_template.shell import CommandGroups, flatten, run

QEMU_IMG = "qemu-img"
GENISOIMAGE = "genisoimage"
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


def convert_command(image: Path, destination: Path, format: str) -> CommandGroups:
    return [[QEMU_IMG], ["convert"], ["-O", format], [str(image)], [str(destination)]]


def seed_iso_command(destination: Path, sources: Sequence[Path]) -> CommandGroups:
    return [
        [GENISOIMAGE],
        ["-output", str(destination)],
        ["-volid", SEED_LABEL],
        ["-joliet"],
        ["-rock"],
        *([str(source)] for source in sources),
    ]


def run_tool(command: CommandGroups) -> None:
    argv = flatten(command)
    result = run(argv)
    if result.returncode != 0:
        raise QmTemplateError(f"{argv[0]} failed with exit status {result.returncode}")

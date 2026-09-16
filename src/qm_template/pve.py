import os
import re
import shutil
import sys
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Literal

from qm_template.config import CloudInitSettings, CreateSettings
from qm_template.errors import QmTemplateError, UserCancelled
from qm_template.log import log
from qm_template.shell import CommandGroups, flatten, run

PVE_VM_DIR = Path("/etc/pve/qemu-server")
MIN_VM_ID = 100


def prompt(message: str) -> str:
    print(message, end="", file=sys.stderr, flush=True)
    line = sys.stdin.readline()
    if not line:
        raise QmTemplateError("interactive input required but stdin is not available")
    return line.strip()


def vm_config_path(vm_id: int) -> Path:
    return PVE_VM_DIR / f"{vm_id}.conf"


def _parse_vm_list(text: str) -> set[int]:
    ids: set[int] = set()
    for line in text.splitlines()[1:]:
        fields = line.split()
        if fields and fields[0].isdigit():
            ids.add(int(fields[0]))
    return ids


def _config_vm_ids() -> set[int]:
    return {int(path.stem) for path in PVE_VM_DIR.glob("*.conf") if path.stem.isdigit()}


def used_vm_ids() -> set[int]:
    """Collect VM IDs from `qm list`, combined with the config directory."""
    ids: set[int] = set()
    qm = shutil.which("qm")
    if qm is not None:
        try:
            result = run([qm, "list"], capture=True)
        except QmTemplateError as exc:
            log.debug("%s", exc)
        else:
            if result.returncode == 0:
                ids.update(_parse_vm_list(result.stdout))
            else:
                log.debug("qm list failed with exit status %d", result.returncode)
    return ids | _config_vm_ids()


def next_vm_id(used: Collection[int], start: int, step: int = 1) -> int:
    if step < 1:
        raise QmTemplateError("step must be a positive integer")
    candidate = start
    while candidate in used:
        candidate += step
    return candidate


def choose_image(images: Sequence[Path], directory: Path) -> Path:
    log.info("Available images:")
    for index, image in enumerate(images):
        print(f"{index:3d} | {image.relative_to(directory)}", file=sys.stderr)
    while True:
        answer = prompt(f"Select image (0-{len(images) - 1}, q to quit): ")
        if answer in {"q", "quit"}:
            raise UserCancelled
        if answer.isdigit() and 0 <= int(answer) < len(images):
            return images[int(answer)]
        log.warning("Invalid selection, please try again")


def default_vm_name(image: Path) -> str:
    name = re.sub(r"[._]+", "-", image.stem).strip("-")
    return (name or image.stem)[:63].rstrip("-")


def check_storage(storage: str) -> None:
    pvesm = shutil.which("pvesm")
    if pvesm is None:
        log.warning("pvesm not found, skipping storage validation")
        return
    status = None
    try:
        status = run([pvesm, "status"], capture=True)
    except QmTemplateError as exc:
        log.debug("%s", exc)
    if status is None or status.returncode != 0:
        log.warning("pvesm status failed, skipping storage validation")
        return
    names = [
        fields[0] for line in status.stdout.splitlines()[1:] if (fields := line.split())
    ]
    if storage not in names:
        raise QmTemplateError(
            f"storage {storage!r} not found in Proxmox (available: {', '.join(names)})"
        )


ResolvedFirmware = Literal["bios", "uefi"]


def detect_firmware(image: Path) -> ResolvedFirmware:
    """Guess the firmware an image needs from its filename."""
    return "uefi" if "uefi" in image.name.lower() else "bios"


def build_qm_create(
    vm_id: int,
    vm_name: str,
    image: Path,
    sshkeys: Path,
    settings: CreateSettings,
    cloudinit: CloudInitSettings,
    *,
    firmware: ResolvedFirmware = "bios",
) -> CommandGroups:
    storage = settings.storage
    firmware_args: CommandGroups = []
    if firmware == "uefi":
        firmware_args = [
            ["--bios", "ovmf"],
            ["--efidisk0", f"{storage}:1,pre-enrolled-keys=0"],
        ]
    metadata_args: CommandGroups = []
    if settings.tags:
        metadata_args.append(["--tags", ";".join(settings.tags)])
    if settings.pool:
        metadata_args.append(["--pool", settings.pool])
    if settings.onboot:
        metadata_args.append(["--onboot", "1"])
    if settings.description:
        metadata_args.append(["--description", settings.description])
    return [
        ["qm", "create", str(vm_id)],
        ["--name", vm_name],
        *metadata_args,
        ["--cpu", f"cputype={settings.cpu}"],
        ["--cores", str(settings.cores)],
        ["--balloon", str(settings.memory)],
        ["--memory", str(settings.memory)],
        ["--net0", f"model=virtio,firewall=1,bridge={settings.bridge}"],
        ["--scsihw", "virtio-scsi-single"],
        ["--agent", "type=virtio,enabled=1"],
        ["--machine", "q35"],
        *firmware_args,
        ["--ostype", "l26"],
        ["--serial0", "socket"],
        ["--vga", "serial0"],
        ["--scsi0", f"{storage}:0,import-from={image}"],
        ["--scsi1", f"{storage}:cloudinit"],
        ["--boot", "order=scsi0"],
        ["--ipconfig0", "ip=dhcp"],
        ["--ciupgrade", "0"],
        ["--ciuser", cloudinit.user],
        ["--cipassword", cloudinit.password],
        ["--sshkeys", str(sshkeys)],
        ["--template", "1"],
    ]


def run_qm(command: CommandGroups) -> None:
    argv = flatten(command)
    qm = shutil.which("qm")
    if qm is None:
        raise QmTemplateError("qm command not found; run this on a Proxmox VE node")
    if os.geteuid() != 0:
        log.warning("qm usually requires root privileges")
    label = " ".join(argv[:2])
    result = run([qm, *argv[1:]])
    if result.returncode != 0:
        raise QmTemplateError(f"{label} failed with exit status {result.returncode}")

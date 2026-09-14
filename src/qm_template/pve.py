import contextlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Generator, Sequence
from pathlib import Path

from qm_template import PROGRAM
from qm_template.config import (
    SSH_KEY_TYPE_PREFIXES,
    CreateSettings,
    ssh_key_fingerprint,
)
from qm_template.errors import QmTemplateError, UserCancelled
from qm_template.log import log
from qm_template.shell import CommandGroups, flatten

PVE_VM_DIR = Path("/etc/pve/qemu-server")
IMAGE_SUFFIXES = {".qcow2", ".img"}


def prompt(message: str) -> str:
    print(message, end="", file=sys.stderr, flush=True)
    line = sys.stdin.readline()
    if not line:
        raise QmTemplateError("interactive input required but stdin is not available")
    return line.strip()


def vm_config_path(vm_id: int) -> Path:
    return PVE_VM_DIR / f"{vm_id}.conf"


def choose_vm_id() -> int:
    while True:
        answer = prompt("Enter VM ID (q to quit): ")
        if answer in {"q", "quit"}:
            raise UserCancelled
        if not answer.isdigit() or int(answer) <= 0:
            log.warning("VM ID must be a positive integer")
            continue
        vm_id = int(answer)
        if vm_config_path(vm_id).exists():
            log.warning("VM ID %d is already in use", vm_id)
            continue
        return vm_id


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
    result = subprocess.run([pvesm, "status"], capture_output=True, text=True)
    if result.returncode != 0:
        log.warning("pvesm status failed, skipping storage validation")
        return
    names = [
        fields[0] for line in result.stdout.splitlines()[1:] if (fields := line.split())
    ]
    if storage not in names:
        raise QmTemplateError(
            f"storage {storage!r} not found in Proxmox (available: {', '.join(names)})"
        )


def _write_keys_file(content: str) -> Path:
    with tempfile.NamedTemporaryFile(
        "w", prefix=f"{PROGRAM}-sshkeys-", delete=False
    ) as handle:
        handle.write(content)
        return Path(handle.name)


def _collect_ssh_keys(settings: CreateSettings) -> str | None:
    keys: list[str] = []
    seen: set[str] = set()

    def add(value: str, *, strict: bool) -> None:
        line = value.strip()
        if not line or line.startswith("#"):
            return
        fingerprint = ssh_key_fingerprint(line)
        if not line.startswith(SSH_KEY_TYPE_PREFIXES) or fingerprint is None:
            if strict:
                raise QmTemplateError(f"{line!r} does not look like an SSH public key")
            log.warning("Skipping invalid SSH key line: %r", line)
            return
        if fingerprint not in seen:
            seen.add(fingerprint)
            keys.append(line)

    for value in settings.sshkeys:
        add(value, strict=True)
    for configured in settings.sshkeys_files:
        path = Path(os.path.expandvars(configured)).expanduser()
        if not path.is_file() or not os.access(path, os.R_OK):
            log.warning("SSH keys file is not readable: %s", path)
            continue
        for line in path.read_text().splitlines():
            add(line, strict=False)
    return "\n".join(keys) + "\n" if keys else None


@contextlib.contextmanager
def sshkeys_file(settings: CreateSettings) -> Generator[Path, None, None]:
    content = _collect_ssh_keys(settings)
    if content is None:
        raise QmTemplateError(
            "no SSH keys configured; set create.sshkeys or create.sshkeys_files"
        )
    temporary = _write_keys_file(content)
    try:
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


def build_qm_create(
    vm_id: int,
    vm_name: str,
    image: Path,
    sshkeys: Path,
    settings: CreateSettings,
) -> CommandGroups:
    storage = settings.storage
    return [
        ["qm", "create", str(vm_id)],
        ["--name", vm_name],
        ["--cpu", "cputype=host"],
        ["--cores", str(settings.cores)],
        ["--balloon", str(settings.memory)],
        ["--memory", str(settings.memory)],
        ["--net0", f"model=virtio,firewall=1,bridge={settings.bridge}"],
        ["--scsihw", "virtio-scsi-single"],
        ["--agent", "type=virtio,enabled=1"],
        ["--machine", "q35"],
        ["--ostype", "l26"],
        ["--serial0", "socket"],
        ["--vga", "serial0"],
        ["--scsi0", f"{storage}:0,import-from={image}"],
        ["--scsi1", f"{storage}:cloudinit"],
        ["--boot", "order=scsi0"],
        ["--ipconfig0", "ip=dhcp"],
        ["--ciupgrade", "0"],
        ["--ciuser", settings.ciuser],
        ["--cipassword", settings.cipassword],
        ["--sshkeys", str(sshkeys)],
        ["--template", "1"],
    ]


def run_qm(command: CommandGroups) -> None:
    argv = flatten(command)
    if shutil.which("qm") is None:
        raise QmTemplateError("qm command not found; run this on a Proxmox VE node")
    if os.geteuid() != 0:
        log.warning("qm usually requires root privileges")
    log.debug("Running: %s", shlex.join(argv))
    result = subprocess.run(argv)
    if result.returncode != 0:
        raise QmTemplateError(f"qm create failed with exit status {result.returncode}")

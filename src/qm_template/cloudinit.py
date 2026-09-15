import contextlib
import os
import tempfile
from collections.abc import Generator
from pathlib import Path

from qm_template import PROGRAM
from qm_template.config import (
    SSH_KEY_TYPE_PREFIXES,
    CloudInitSettings,
    ssh_key_fingerprint,
)
from qm_template.errors import QmTemplateError
from qm_template.log import log


def collect_ssh_keys(settings: CloudInitSettings) -> tuple[str, ...]:
    """Merge inline keys and key files, deduplicated by fingerprint."""
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
    return tuple(keys)


@contextlib.contextmanager
def sshkeys_file(settings: CloudInitSettings) -> Generator[Path, None, None]:
    keys = collect_ssh_keys(settings)
    if not keys:
        raise QmTemplateError(
            "no SSH keys configured; set cloudinit.sshkeys or cloudinit.sshkeys_files"
        )
    with tempfile.NamedTemporaryFile(
        "w", prefix=f"{PROGRAM}-sshkeys-", delete=False
    ) as handle:
        handle.write("\n".join(keys) + "\n")
        temporary = Path(handle.name)
    try:
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


def _yaml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def user_data(settings: CloudInitSettings, vm_name: str) -> str:
    """Render a NoCloud user-data document configuring the cloud user."""
    keys = collect_ssh_keys(settings)
    if not keys:
        raise QmTemplateError(
            "no SSH keys configured; set cloudinit.sshkeys or cloudinit.sshkeys_files"
        )
    lines = [
        "#cloud-config",
        f"hostname: {_yaml_string(vm_name)}",
        "users:",
        f"  - name: {_yaml_string(settings.user)}",
        "    shell: /bin/bash",
        "    lock_passwd: false",
        "    sudo: ALL=(ALL) NOPASSWD:ALL",
        "    ssh_authorized_keys:",
    ]
    lines.extend(f"      - {_yaml_string(key)}" for key in keys)
    lines.extend(
        [
            "chpasswd:",
            "  expire: false",
            "  users:",
            f"    - name: {_yaml_string(settings.user)}",
            f"      password: {_yaml_string(settings.password)}",
            "      type: text",
            "ssh_pwauth: true",
        ]
    )
    return "\n".join(lines) + "\n"


def meta_data(vm_name: str) -> str:
    """Render the NoCloud meta-data document for a local instance."""
    return (
        f"instance-id: {_yaml_string(f'iid-{vm_name}')}\n"
        f"local-hostname: {_yaml_string(vm_name)}\n"
    )


def network_config() -> str:
    """Render a version 2 network-config that DHCPs the first Ethernet NIC.

    Debian cloud images do not fall back to a generated network
    configuration, so without this file no netplan config is written and no
    interface is configured. The name globs mirror cloud-init's own known-good
    snapd configuration.
    """
    return (
        "version: 2\n"
        "ethernets:\n"
        "  all-en:\n"
        "    match:\n"
        '      name: "en*"\n'
        "    dhcp4: true\n"
        "  all-eth:\n"
        "    match:\n"
        '      name: "eth*"\n'
        "    dhcp4: true\n"
    )

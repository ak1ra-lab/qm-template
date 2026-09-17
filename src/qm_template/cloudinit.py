import contextlib
import os
import tempfile
from collections.abc import Generator, Sequence
from pathlib import Path

from qm_template import PROGRAM
from qm_template.config import CloudInitSettings, ssh_key_fingerprint
from qm_template.distros import DISTROS
from qm_template.errors import QmTemplateError
from qm_template.log import log

DEFAULT_USER = "admin"


def resolve_user(user: str, image: Path, images_dir: Path) -> str:
    """Return the configured Cloud-Init user or the image's distro default."""
    if user:
        return user
    try:
        distro = image.resolve().relative_to(images_dir.resolve()).parts[0]
    except (ValueError, IndexError):
        return DEFAULT_USER
    return DISTROS[distro].cloud_user if distro in DISTROS else DEFAULT_USER


def collect_ssh_keys(settings: CloudInitSettings) -> tuple[str, ...]:
    """Merge inline keys and key files, deduplicated by fingerprint."""
    keys: list[str] = []
    seen: set[str] = set()

    def add(value: str, *, strict: bool) -> None:
        line = value.strip()
        if not line or line.startswith("#"):
            return
        fingerprint = ssh_key_fingerprint(line)
        if fingerprint is None:
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
def sshkeys_file(keys: Sequence[str]) -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-sshkeys-") as staging:
        path = Path(staging) / "authorized_keys"
        path.write_text("\n".join(keys) + "\n", encoding="utf-8")
        yield path


def require_credentials(settings: CloudInitSettings) -> tuple[str, ...]:
    """Collect SSH keys, requiring at least one login method to be configured."""
    keys = collect_ssh_keys(settings)
    if not keys and not settings.password.get_secret_value():
        raise QmTemplateError(
            "no login method configured; set cloudinit.password, "
            "cloudinit.sshkeys or cloudinit.sshkeys_files"
        )
    return keys


def _yaml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def user_data(settings: CloudInitSettings, vm_name: str) -> str:
    """Render a NoCloud user-data document configuring the cloud user."""
    keys = collect_ssh_keys(settings)
    password = settings.password.get_secret_value()
    if not keys:
        log.warning(
            "No SSH keys configured; the guest will only allow password login"
            if password
            else "No SSH keys or password configured; the guest will not allow login"
        )
    lines = [
        "#cloud-config",
        f"hostname: {_yaml_string(vm_name)}",
        "users:",
        f"  - name: {_yaml_string(settings.user)}",
    ]
    if settings.shell:
        lines.append(f"    shell: {_yaml_string(settings.shell)}")
    lines.extend(
        [
            f"    lock_passwd: {'false' if password else 'true'}",
            "    sudo: ALL=(ALL) NOPASSWD:ALL",
        ]
    )
    if keys:
        lines.append("    ssh_authorized_keys:")
        lines.extend(f"      - {_yaml_string(key)}" for key in keys)
    if password:
        lines.extend(
            [
                "chpasswd:",
                "  expire: false",
                "  users:",
                f"    - name: {_yaml_string(settings.user)}",
                f"      password: {_yaml_string(password)}",
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

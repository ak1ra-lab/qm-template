import re
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, TypeVar
from urllib.parse import quote

from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from proxmoxer.tools import Tasks
from requests.exceptions import RequestException

from qm_template import PROGRAM
from qm_template.config import CreateSettings, PveHostSettings
from qm_template.errors import QmTemplateError
from qm_template.log import log
from qm_template.pve import VmSpec

MIN_VERSION = (8, 4)
QCOW2_MAGIC = b"QFI\xfb"
MAX_NAME_LENGTH = 240
_VERSION_RE = re.compile(r"\d+")
_UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._+=-]+")
T = TypeVar("T")


def parse_version(release: str) -> tuple[int, ...]:
    parts = _VERSION_RE.findall(release)
    if not parts:
        raise QmTemplateError(f"cannot parse the Proxmox VE version {release!r}")
    return tuple(int(part) for part in parts[:3])


def image_magic(image: Path) -> bytes:
    try:
        with image.open("rb") as handle:
            return handle.read(len(QCOW2_MAGIC))
    except OSError as exc:
        raise QmTemplateError(f"cannot read image {image}: {exc}") from exc


def import_name(image: Path, root: Path) -> str:
    """Return the flat, PVE-safe import filename for a local image.

    Import content only accepts .qcow2, .raw and .vmdk extensions, so the
    format is taken from the image itself rather than from its suffix.
    """
    suffix = "qcow2" if image_magic(image) == QCOW2_MAGIC else "raw"
    try:
        relative = image.resolve().relative_to(root.resolve())
    except ValueError:
        relative = Path(image.name)
    stem = "-".join(relative.with_suffix("").parts)
    safe = _UNSAFE_NAME_RE.sub("-", stem).strip("-.") or "image"
    return f"{safe[:MAX_NAME_LENGTH]}.{suffix}"


def build_create_params(spec: VmSpec, source: str) -> dict[str, Any]:
    create = spec.create
    params: dict[str, Any] = {
        "vmid": spec.vm_id,
        "name": spec.name,
        "cpu": f"cputype={create.cpu}",
        "cores": create.cores,
        "balloon": create.memory,
        "memory": create.memory,
        "net0": f"model=virtio,firewall=1,bridge={create.bridge}",
        "scsihw": "virtio-scsi-single",
        "agent": "type=virtio,enabled=1",
        "machine": "q35",
        "ostype": "l26",
        "serial0": "socket",
        "vga": "serial0",
        "scsi0": f"{create.storage}:0,import-from={source}",
        "scsi1": f"{create.storage}:cloudinit",
        "boot": "order=scsi0",
        "ipconfig0": "ip=dhcp",
        "ciupgrade": 0,
        "ciuser": spec.cloudinit.user,
        "cipassword": spec.cloudinit.password,
        "sshkeys": quote("\n".join(spec.sshkeys), safe=""),
        "template": 1,
    }
    if create.tags:
        params["tags"] = ";".join(create.tags)
    if create.pool:
        params["pool"] = create.pool
    if create.onboot:
        params["onboot"] = 1
    if create.description:
        params["description"] = create.description
    if spec.firmware == "uefi":
        params["bios"] = "ovmf"
        params["efidisk0"] = f"{create.storage}:1,pre-enrolled-keys=0"
    return params


@contextmanager
def _upload_handle(image: Path, name: str) -> Iterator[BinaryIO]:
    """Open an image under the import name PVE expects to receive."""
    if image.name == name:
        with image.open("rb") as handle:
            yield handle
        return
    with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-upload-") as directory:
        link = Path(directory) / name
        link.symlink_to(image.resolve())
        with link.open("rb") as handle:
            yield handle


class ApiPveTarget:
    """Create templates on a remote Proxmox VE host through its API."""

    def __init__(
        self,
        name: str,
        settings: PveHostSettings,
        images_dir: Path,
        *,
        client: ProxmoxAPI | None = None,
    ) -> None:
        self._name = name
        self._settings = settings
        self._images_dir = images_dir
        self._node: str | None = None
        self._client = client or ProxmoxAPI(
            settings.host,
            port=settings.port,
            user=settings.user,
            token_name=settings.token_name,
            token_value=settings.token_secret.get_secret_value(),
            verify_ssl=settings.verify_ssl,
            timeout=settings.timeout,
        )

    @property
    def node(self) -> str:
        if self._node is None:
            self._node = self._resolve_node()
        return self._node

    def next_vm_id(self, start: int, step: int) -> int:
        if step < 1:
            raise QmTemplateError("step must be a positive integer")
        candidate = start
        while not self._vm_id_free(candidate):
            candidate += step
        return candidate

    def assert_vm_id_free(self, vm_id: int) -> None:
        if not self._vm_id_free(vm_id):
            raise QmTemplateError(f"VM ID {vm_id} is already in use")

    def validate(self, create: CreateSettings) -> None:
        self._check_version()
        storages = self._storages()
        self._require_storage(storages, create.storage, "images", "VM disks")
        self._require_storage(
            storages,
            self._import_storage(),
            "import",
            "imported images",
            hint=(
                "; enable the 'import' content type for that storage in the "
                "Proxmox VE web interface"
            ),
        )

    def source_for(self, image: Path) -> str:
        return f"{self._import_storage()}:import/{import_name(image, self._images_dir)}"

    def ensure_source(self, source: str, image: Path) -> None:
        if self._uploaded(source, image):
            log.info("Using existing upload: %s", source)
            return
        storage, _, name = source.partition(":")
        log.info("Uploading %s to %s", image, source)
        with _upload_handle(image, name.removeprefix("import/")) as handle:
            task = self._call(
                f"upload {image.name}",
                lambda: (
                    self._client.nodes(self.node)
                    .storage(storage)
                    .upload.post(content="import", filename=handle)
                ),
            )
        self._wait(task, f"upload {image.name}")

    def preview(self, spec: VmSpec, source: str) -> str:
        lines = [
            f"# upload {spec.image} -> {source} (skipped when already present)",
            f"POST /api2/json/nodes/{self.node}/qemu",
        ]
        lines.extend(
            f"    {key}={value}"
            for key, value in build_create_params(spec, source).items()
        )
        return "\n".join(lines)

    def create_template(self, spec: VmSpec, source: str) -> None:
        params = build_create_params(spec, source)
        task = self._call(
            f"create VM {spec.vm_id}",
            lambda: self._client.nodes(self.node).qemu.post(**params),
        )
        self._wait(task, f"create VM {spec.vm_id}")

    def abort(self, vm_id: int) -> None:
        try:
            self._client.nodes(self.node).qemu(vm_id).status.current.get()
        except ResourceException:
            return
        log.warning("Removing incomplete VM %d on %r", vm_id, self.node)
        try:
            task = self._client.nodes(self.node).qemu(vm_id).delete()
            self._wait(task, f"remove VM {vm_id}")
        except QmTemplateError as exc:
            log.warning(
                "Could not remove VM %d: %s; remove it with: qm destroy %d",
                vm_id,
                exc,
                vm_id,
            )

    def _check_version(self) -> None:
        data = self._call(
            "fetch the Proxmox VE version", lambda: self._client.version.get()
        )
        release = str(data.get("release") or data.get("version") or "")
        current = parse_version(release)
        if current[:2] < MIN_VERSION:
            raise QmTemplateError(
                f"Proxmox VE {release} does not support API mode: version "
                f"{MIN_VERSION[0]}.{MIN_VERSION[1]} or newer is required "
                "(upgrade the host or omit --pve to use local mode)"
            )

    def _resolve_node(self) -> str:
        nodes = self._call("list nodes", lambda: self._client.nodes.get())
        names = [str(entry["node"]) for entry in nodes]
        configured = self._settings.node
        if configured:
            if configured not in names:
                raise QmTemplateError(
                    f"node {configured!r} not found on {self._settings.host} "
                    f"(available: {', '.join(names)})"
                )
            return configured
        if len(names) == 1:
            return names[0]
        raise QmTemplateError(
            f"{self._settings.host} is a cluster with multiple nodes "
            f"({', '.join(names)}); set pve.{self._name}.node to select one"
        )

    def _storages(self) -> dict[str, dict[str, Any]]:
        entries = self._call(
            f"list storages on node {self.node!r}",
            lambda: self._client.nodes(self.node).storage.get(),
        )
        return {str(entry["storage"]): entry for entry in entries}

    def _require_storage(
        self,
        storages: dict[str, dict[str, Any]],
        name: str,
        content: str,
        purpose: str,
        *,
        hint: str = "",
    ) -> None:
        where = f"node {self.node!r}"
        entry = storages.get(name)
        if entry is None:
            available = ", ".join(sorted(storages)) or "none"
            raise QmTemplateError(
                f"storage {name!r} is not available on {where} "
                f"(available: {available}){hint}"
            )
        if not entry.get("active"):
            raise QmTemplateError(f"storage {name!r} is not active on {where}{hint}")
        contents = {part.strip() for part in str(entry.get("content", "")).split(",")}
        if content not in contents:
            available = ", ".join(sorted(contents)) or "none"
            raise QmTemplateError(
                f"storage {name!r} cannot hold {purpose} on {where}: content "
                f"type {content!r} is not enabled (enabled: {available}){hint}"
            )

    def _import_storage(self) -> str:
        storage = self._settings.import_storage
        if not storage:
            raise QmTemplateError(
                f"[pve.{self._name}].import_storage is not configured; set it to "
                "a file-based storage with the 'import' content type enabled"
            )
        return storage

    def _uploaded(self, source: str, image: Path) -> bool:
        storage = source.partition(":")[0]
        contents = self._call(
            f"list images on storage {storage!r}",
            lambda: (
                self._client.nodes(self.node)
                .storage(storage)
                .content.get(content="import")
            ),
        )
        size = image.stat().st_size
        return any(
            item.get("volid") == source and int(item.get("size", -1)) == size
            for item in contents
        )

    def _vm_id_free(self, vm_id: int) -> bool:
        try:
            self._client.cluster.nextid.get(vmid=vm_id)
        except ResourceException as exc:
            if exc.status_code == 400:
                return False
            raise QmTemplateError(f"could not check VM ID {vm_id}: {exc}") from exc
        except RequestException as exc:
            raise QmTemplateError(f"could not check VM ID {vm_id}: {exc}") from exc
        return True

    def _wait(self, task: str, description: str) -> None:
        timeout = self._settings.task_timeout
        try:
            status = Tasks.blocking_status(self._client, task, timeout=timeout)
        except RequestException as exc:
            raise QmTemplateError(f"{description} failed: {exc}") from exc
        if status is None:
            raise QmTemplateError(
                f"{description} did not finish within {timeout}s (task {task})"
            )
        exitstatus = status.get("exitstatus")
        if exitstatus != "OK":
            raise QmTemplateError(
                f"{description} failed: {exitstatus or 'no task status reported'}"
            )

    def _call(self, description: str, call: Callable[[], T]) -> T:
        try:
            return call()
        except (RequestException, ResourceException) as exc:
            raise QmTemplateError(f"{description} failed: {exc}") from exc

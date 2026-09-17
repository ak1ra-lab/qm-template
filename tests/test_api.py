from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import pytest
import requests
from proxmoxer.core import ResourceException

from qm_template.api import (
    QCOW2_MAGIC,
    ApiPveTarget,
    build_create_params,
    image_magic,
    import_name,
    parse_version,
)
from qm_template.cli import main
from qm_template.commands import _complete_pve_names
from qm_template.config import CloudInitSettings, CreateSettings, PveHostSettings
from qm_template.errors import QmTemplateError
from qm_template.pve import VmSpec
from qm_template.shell import MASK

TASK = "UPID:pve1:00001234:00000000:00000000:qmcreate:9000:root@pam:test"


def make_host(**overrides: Any) -> PveHostSettings:
    values: dict[str, Any] = {
        "host": "pve.example.com",
        "node": "pve1",
        "user": "qm-template@pve",
        "token_name": "automation",
        "token_secret": "secret",
        "import_storage": "local",
    }
    values.update(overrides)
    return PveHostSettings(**values)


def make_spec(**overrides: Any) -> VmSpec:
    values: dict[str, Any] = {
        "vm_id": 9000,
        "name": "debian-template",
        "image": Path("/images/x.qcow2"),
        "firmware": "bios",
        "create": CreateSettings(),
        "cloudinit": CloudInitSettings(),
        "sshkeys": ("ssh-ed25519 AAAA",),
    }
    values.update(overrides)
    return VmSpec(**values)


class FakeResource:
    def __init__(self, api: "FakeApi", path: tuple[str, ...]) -> None:
        self._api = api
        self._path = path

    def __getattr__(self, item: str) -> "FakeResource":
        if item.startswith("_"):
            raise AttributeError(item)
        return FakeResource(self._api, (*self._path, item))

    def __call__(self, *args: Any) -> "FakeResource":
        return FakeResource(self._api, (*self._path, *[str(arg) for arg in args]))

    def get(self, **params: Any) -> Any:
        return self._api.handle("GET", self._path, params)

    def post(self, **data: Any) -> Any:
        return self._api.handle("POST", self._path, data)

    def delete(self, **params: Any) -> Any:
        return self._api.handle("DELETE", self._path, params)


class FakeApi:
    """A minimal stand-in for proxmoxer's dynamically built client."""

    def __init__(
        self,
        *,
        release: str = "9.0",
        nodes: tuple[str, ...] = ("pve1",),
        storages: list[dict[str, Any]] | None = None,
        used: tuple[int, ...] = (),
        task_status: dict[str, Any] | None = None,
    ) -> None:
        self.release = release
        self.node_names = list(nodes)
        self.storages = (
            storages
            if storages is not None
            else [
                {
                    "storage": "local",
                    "active": 1,
                    "content": "iso,vztmpl,backup,images,import",
                },
                {"storage": "local-lvm", "active": 1, "content": "images,rootdir"},
                {"storage": "local-zfs", "active": 1, "content": "images"},
            ]
        )
        self.used = set(used)
        self.task_status = task_status or {"status": "stopped", "exitstatus": "OK"}
        self.calls: list[tuple[str, tuple[str, ...], dict[str, Any]]] = []
        self.content: list[dict[str, Any]] = []
        self.uploads: list[dict[str, Any]] = []
        self.created: dict[str, Any] = {}
        self.deleted: list[int] = []
        self.existing_vms: set[int] = set()

    def __getattr__(self, item: str) -> FakeResource:
        if item.startswith("_"):
            raise AttributeError(item)
        return FakeResource(self, (item,))

    def handle(self, method: str, path: tuple[str, ...], params: dict[str, Any]) -> Any:
        self.calls.append((method, path, params))
        if path == ("version",):
            return {"release": self.release, "version": f"{self.release}.0"}
        if path == ("nodes",):
            return [{"node": name} for name in self.node_names]
        if path == ("cluster", "nextid"):
            vmid = int(params["vmid"])
            if vmid in self.used:
                raise ResourceException(400, "Bad Request", f"VM {vmid} exists")
            return vmid
        if len(path) == 3 and path[0] == "nodes" and path[2] == "storage":
            return self.storages
        if len(path) == 5 and path[2] == "storage" and path[4] == "content":
            return self.content
        if len(path) == 5 and path[2] == "storage" and path[4] == "upload":
            self.uploads.append(params)
            return TASK
        if len(path) == 3 and path[2] == "qemu" and method == "POST":
            self.created = params
            return TASK
        if len(path) == 6 and path[2] == "qemu" and path[4] == "status":
            if int(path[3]) in self.existing_vms:
                return {"status": "stopped"}
            raise ResourceException(500, "Internal Server Error", "no such VM")
        if len(path) == 4 and path[2] == "qemu" and method == "DELETE":
            self.deleted.append(int(path[3]))
            return TASK
        if len(path) == 5 and path[2] == "tasks" and path[4] == "status":
            return self.task_status
        raise AssertionError(f"unexpected API call: {method} {path}")


def make_target(
    api: FakeApi, *, images_dir: Path | None = None, **host_overrides: Any
) -> ApiPveTarget:
    return ApiPveTarget(
        "home",
        make_host(**host_overrides),
        images_dir or Path("/images"),
        client=api,
    )


def write_image(tmp_path: Path, name: str = "debian-13.qcow2") -> Path:
    image = tmp_path / "images" / "debian" / "13" / name
    image.parent.mkdir(parents=True)
    image.write_bytes(QCOW2_MAGIC + b"\x00" * 8)
    return image


def test_parse_version_extracts_numbers():
    assert parse_version("9.0") == (9, 0)
    assert parse_version("8.4.1") == (8, 4, 1)
    with pytest.raises(QmTemplateError):
        parse_version("unknown")


def test_image_magic_reports_the_qcow2_format(tmp_path: Path):
    image = write_image(tmp_path)
    assert image_magic(image) == QCOW2_MAGIC
    raw = tmp_path / "raw.img"
    raw.write_bytes(b"not a qcow2")
    assert image_magic(raw) != QCOW2_MAGIC


def test_image_magic_reports_unreadable_files(tmp_path: Path):
    with pytest.raises(QmTemplateError, match="cannot read image"):
        image_magic(tmp_path / "missing.qcow2")


def test_import_name_flattens_the_relative_path(tmp_path: Path):
    root = tmp_path / "images"
    image = write_image(tmp_path)
    assert import_name(image, root) == "debian-13-debian-13.qcow2"


def test_import_name_uses_raw_for_other_formats(tmp_path: Path):
    root = tmp_path / "images"
    image = root / "ubuntu" / "noble.img"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"raw image")
    assert import_name(image, root) == "ubuntu-noble.raw"


def test_import_name_sanitizes_unsafe_characters(tmp_path: Path):
    root = tmp_path / "images"
    image = root / "my distro" / "weird name!.img"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"raw image")
    assert import_name(image, root) == "my-distro-weird-name.raw"


def test_import_name_falls_back_to_the_basename_outside_the_root(tmp_path: Path):
    image = tmp_path / "elsewhere" / "debian-13.qcow2"
    image.parent.mkdir()
    image.write_bytes(QCOW2_MAGIC)
    root = tmp_path / "images"
    root.mkdir()
    assert import_name(image, root) == "debian-13.qcow2"


def test_build_create_params_maps_the_spec():
    spec = make_spec(
        create=CreateSettings(
            storage="local-zfs",
            cores=4,
            memory=4096,
            cpu="x86-64-v2-AES",
            bridge="vmbr1",
            tags=("template", "cloud"),
            pool="templates",
            onboot=True,
            description="Debian 13 cloud template",
        ),
        cloudinit=CloudInitSettings(user="admin", password="secret"),
    )
    params = build_create_params(spec, "local:import/debian-13.qcow2")
    assert params["vmid"] == 9000
    assert params["name"] == "debian-template"
    assert params["cpu"] == "cputype=x86-64-v2-AES"
    assert params["cores"] == 4
    assert params["memory"] == 4096
    assert params["scsi0"] == ("local-zfs:0,import-from=local:import/debian-13.qcow2")
    assert params["scsi1"] == "local-zfs:cloudinit"
    assert params["boot"] == "order=scsi0"
    assert params["ciuser"] == "admin"
    assert params["cipassword"] == "secret"
    assert params["sshkeys"] == quote("ssh-ed25519 AAAA", safe="")
    assert params["tags"] == "template;cloud"
    assert params["pool"] == "templates"
    assert params["onboot"] == 1
    assert params["template"] == 1
    assert "bios" not in params
    assert "description" in params


def test_build_create_params_adds_uefi_and_omits_metadata_by_default():
    params = build_create_params(
        make_spec(firmware="uefi", create=CreateSettings(storage="local-zfs")),
        "local:import/x.qcow2",
    )
    assert params["bios"] == "ovmf"
    assert params["efidisk0"] == "local-zfs:1,pre-enrolled-keys=0"
    for key in ("tags", "pool", "onboot", "description"):
        assert key not in params


def test_build_create_params_omits_empty_credentials():
    params = build_create_params(
        make_spec(cloudinit=CloudInitSettings(), sshkeys=()),
        "local:import/x.qcow2",
    )
    assert "cipassword" not in params
    assert "sshkeys" not in params


def test_preview_masks_credentials():
    spec = make_spec(cloudinit=CloudInitSettings(user="admin", password="secret"))
    preview = make_target(FakeApi()).preview(spec, "local:import/x.qcow2")
    assert "secret" not in preview
    assert f"    cipassword={MASK}" in preview
    assert f"    sshkeys={MASK}" in preview
    assert "ssh-ed25519" not in preview


def test_validate_accepts_a_supported_host(tmp_path: Path):
    api = FakeApi()
    make_target(api).validate(CreateSettings(storage="local-lvm"))
    assert ("version",) in [call[1] for call in api.calls]


def test_validate_rejects_an_old_host():
    api = FakeApi(release="8.0")
    with pytest.raises(QmTemplateError, match="8.4"):
        make_target(api).validate(CreateSettings())


def test_validate_requires_an_import_storage():
    api = FakeApi()
    with pytest.raises(QmTemplateError, match="import_storage"):
        make_target(api, import_storage=None).validate(CreateSettings())


def test_validate_rejects_a_missing_storage():
    api = FakeApi()
    with pytest.raises(QmTemplateError, match="not available"):
        make_target(api).validate(CreateSettings(storage="missing"))


def test_validate_rejects_an_inactive_storage():
    api = FakeApi(storages=[{"storage": "local-lvm", "active": 0, "content": "images"}])
    with pytest.raises(QmTemplateError, match="not active"):
        make_target(api).validate(CreateSettings(storage="local-lvm"))


def test_validate_rejects_a_storage_without_import_content():
    api = FakeApi(
        storages=[
            {"storage": "local", "active": 1, "content": "iso,images"},
            {"storage": "local-lvm", "active": 1, "content": "images"},
        ]
    )
    with pytest.raises(QmTemplateError, match="'import' is not enabled"):
        make_target(api).validate(CreateSettings())


def test_validate_wraps_api_errors():
    class FailingApi(FakeApi):
        def handle(self, method: str, path: tuple[str, ...], params: Any) -> Any:
            if path == ("nodes",):
                raise ResourceException(401, "Unauthorized", "no ticket")
            return super().handle(method, path, params)

    with pytest.raises(QmTemplateError, match="list nodes failed"):
        make_target(FailingApi()).validate(CreateSettings())


def test_validate_wraps_connection_errors():
    class UnreachableApi(FakeApi):
        def handle(self, method: str, path: tuple[str, ...], params: Any) -> Any:
            if path == ("version",):
                raise requests.ConnectionError("connection refused")
            return super().handle(method, path, params)

    with pytest.raises(QmTemplateError, match="fetch the Proxmox VE version failed"):
        make_target(UnreachableApi()).validate(CreateSettings())


def test_single_node_is_selected_automatically():
    api = FakeApi(nodes=("pve1",))
    assert make_target(api, node=None).node == "pve1"


def test_multiple_nodes_require_a_configured_node():
    api = FakeApi(nodes=("alpha", "beta"))
    with pytest.raises(QmTemplateError, match="multiple nodes"):
        make_target(api, node=None).node
    assert make_target(api, node="beta").node == "beta"


def test_configured_node_must_exist():
    api = FakeApi(nodes=("alpha",))
    with pytest.raises(QmTemplateError, match="not found"):
        make_target(api, node="beta").node


def test_next_vm_id_skips_taken_ids():
    api = FakeApi(used=(9000, 9005))
    assert make_target(api).next_vm_id(9000, 5) == 9010


def test_next_vm_id_rejects_a_non_positive_step():
    with pytest.raises(QmTemplateError, match="positive integer"):
        make_target(FakeApi()).next_vm_id(9000, 0)


def test_assert_vm_id_free_rejects_used_ids():
    target = make_target(FakeApi(used=(9000,)))
    with pytest.raises(QmTemplateError, match="already in use"):
        target.assert_vm_id_free(9000)
    target.assert_vm_id_free(9001)


def test_next_vm_id_wraps_other_api_errors():
    class FailingApi(FakeApi):
        def handle(self, method: str, path: tuple[str, ...], params: Any) -> Any:
            if path == ("cluster", "nextid"):
                raise ResourceException(401, "Unauthorized", "no ticket")
            return super().handle(method, path, params)

    with pytest.raises(QmTemplateError, match="could not check VM ID"):
        make_target(FailingApi()).next_vm_id(9000, 1)


def test_next_vm_id_wraps_connection_errors():
    class UnreachableApi(FakeApi):
        def handle(self, method: str, path: tuple[str, ...], params: Any) -> Any:
            if path == ("cluster", "nextid"):
                raise requests.ConnectionError("connection refused")
            return super().handle(method, path, params)

    with pytest.raises(QmTemplateError, match="could not check VM ID"):
        make_target(UnreachableApi()).next_vm_id(9000, 1)


def test_source_for_uses_the_import_storage(tmp_path: Path):
    image = write_image(tmp_path)
    target = make_target(FakeApi(), images_dir=tmp_path / "images")
    assert target.source_for(image) == "local:import/debian-13-debian-13.qcow2"


def test_ensure_source_reuses_a_matching_upload(tmp_path: Path):
    image = write_image(tmp_path)
    api = FakeApi()
    target = make_target(api, images_dir=tmp_path / "images")
    source = target.source_for(image)
    api.content = [{"volid": source, "size": image.stat().st_size}]
    target.ensure_source(source, image)
    assert api.uploads == []


def test_ensure_source_uploads_a_missing_image(tmp_path: Path):
    image = write_image(tmp_path)
    api = FakeApi()
    target = make_target(api, images_dir=tmp_path / "images")
    source = target.source_for(image)
    target.ensure_source(source, image)
    assert len(api.uploads) == 1
    upload = api.uploads[0]
    assert upload["content"] == "import"
    assert str(upload["filename"].name).endswith("debian-13-debian-13.qcow2")


def test_ensure_source_uploads_raw_images_under_a_raw_name(tmp_path: Path):
    image = tmp_path / "images" / "ubuntu" / "noble.img"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"raw image")
    api = FakeApi()
    target = make_target(api, images_dir=tmp_path / "images")
    source = target.source_for(image)
    assert source == "local:import/ubuntu-noble.raw"
    target.ensure_source(source, image)
    assert str(api.uploads[0]["filename"].name).endswith("ubuntu-noble.raw")


def test_ensure_source_opens_images_with_a_matching_name_directly(tmp_path: Path):
    root = tmp_path / "images"
    root.mkdir()
    image = root / "debian-13.qcow2"
    image.write_bytes(QCOW2_MAGIC)
    api = FakeApi()
    target = make_target(api, images_dir=root)
    source = target.source_for(image)
    target.ensure_source(source, image)
    assert Path(api.uploads[0]["filename"].name).name == "debian-13.qcow2"


def test_create_template_posts_the_request_and_waits():
    api = FakeApi()
    target = make_target(api)
    spec = make_spec(create=CreateSettings(storage="local-lvm"))
    target.create_template(spec, "local:import/x.qcow2")
    assert api.created["vmid"] == 9000
    assert api.created["scsi0"] == ("local-lvm:0,import-from=local:import/x.qcow2")
    assert api.created["template"] == 1


def test_create_template_wraps_api_errors():
    class FailingApi(FakeApi):
        def handle(self, method: str, path: tuple[str, ...], params: Any) -> Any:
            if len(path) == 3 and path[2] == "qemu":
                raise ResourceException(403, "Forbidden", "permission check failed")
            return super().handle(method, path, params)

    with pytest.raises(QmTemplateError, match="403"):
        make_target(FailingApi()).create_template(make_spec(), "local:import/x.qcow2")


def test_task_failure_is_reported():
    api = FakeApi(task_status={"status": "stopped", "exitstatus": "some error"})
    target = make_target(api)
    with pytest.raises(QmTemplateError, match="some error"):
        target.create_template(make_spec(), "local:import/x.qcow2")


def test_abort_removes_an_incomplete_vm():
    api = FakeApi()
    api.existing_vms = {9000}
    make_target(api).abort(9000)
    assert api.deleted == [9000]


def test_abort_leaves_missing_vms_alone():
    api = FakeApi()
    make_target(api).abort(9000)
    assert api.deleted == []


def test_abort_reports_a_failed_cleanup(caplog: pytest.LogCaptureFixture):
    api = FakeApi(task_status={"status": "stopped", "exitstatus": "failed"})
    api.existing_vms = {9000}
    make_target(api).abort(9000)
    assert "Could not remove VM 9000" in caplog.text


def test_task_timeout_is_reported(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "qm_template.api.Tasks.blocking_status", lambda *args, **kw: None
    )
    with pytest.raises(QmTemplateError, match="did not finish"):
        make_target(FakeApi()).create_template(make_spec(), "local:import/x.qcow2")


def test_task_polling_wraps_connection_errors(monkeypatch: pytest.MonkeyPatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr("qm_template.api.Tasks.blocking_status", fail)
    with pytest.raises(QmTemplateError, match="create VM 9000 failed"):
        make_target(FakeApi()).create_template(make_spec(), "local:import/x.qcow2")


def test_preview_lists_the_request():
    api = FakeApi()
    preview = make_target(api).preview(make_spec(), "local:import/x.qcow2")
    assert "POST /api2/json/nodes/pve1/qemu" in preview
    assert "    vmid=9000" in preview
    assert "scsi0=local-lvm:0,import-from=local:import/x.qcow2" in preview


def write_config(tmp_path: Path, images: Path) -> Path:
    config = tmp_path / "config.toml"
    config.write_text(
        f'[paths]\nimages_dir = "{images}"\n'
        '[cloudinit]\nsshkeys = ["ssh-ed25519 AAAA"]\n'
        '[pve.home]\nhost = "pve.example.com"\n'
        'user = "qm-template@pve"\ntoken_name = "automation"\n'
        'token_secret = "secret"\nimport_storage = "local"\n'
        '[pve.home.create]\nstorage = "local-zfs"\n'
        "[pve.home.vmid]\nstart = 9100\nstep = 5\n"
    )
    return config


def test_create_with_pve_dry_run_prints_api_requests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    images = tmp_path / "images"
    (images / "debian" / "13").mkdir(parents=True)
    image = images / "debian" / "13" / "debian-13-genericcloud-amd64.qcow2"
    image.write_bytes(QCOW2_MAGIC)
    config = write_config(tmp_path, images)
    api = FakeApi()

    def fake_target(_name, host, images_dir):
        return ApiPveTarget(_name, host, images_dir, client=api)

    monkeypatch.setattr("qm_template.commands.ApiPveTarget", fake_target)
    assert main(["create", "--pve", "home", "--dry-run", "-c", str(config)]) == 0
    output = capsys.readouterr().out
    assert "POST /api2/json/nodes/pve1/qemu" in output
    assert (
        "local-zfs:0,import-from=local:import/debian-13-debian-13-genericcloud-amd64.qcow2"
        in output
    )
    assert api.created == {}


def test_create_with_pve_uses_host_overrides(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(QCOW2_MAGIC)
    config = write_config(tmp_path, images)
    api = FakeApi(used=(9100,))

    def fake_target(_name, host, images_dir):
        return ApiPveTarget(_name, host, images_dir, client=api)

    monkeypatch.setattr("qm_template.commands.ApiPveTarget", fake_target)
    assert main(["create", "--pve", "home", "--dry-run", "-c", str(config)]) == 0
    output = capsys.readouterr().out
    assert "vmid=9105" in output
    assert "scsi0=local-zfs:0,import-from=local:import/" in output


def test_create_with_pve_rejects_an_unknown_host(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    config = write_config(tmp_path, images)
    assert main(["create", "--pve", "missing", "-c", str(config)]) == 1
    assert "unknown PVE host 'missing'" in capsys.readouterr().err


def test_complete_pve_names_reads_the_configuration(tmp_path: Path):
    images = tmp_path / "images"
    images.mkdir()
    config = write_config(tmp_path, images)
    args = SimpleNamespace(config=str(config))
    assert _complete_pve_names("", args) == ["home"]
    assert _complete_pve_names("ho", args) == ["home"]
    assert _complete_pve_names("x", args) == []


def test_complete_pve_names_ignores_broken_configuration(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text("[paths\n")
    assert _complete_pve_names("", SimpleNamespace(config=str(config))) == []

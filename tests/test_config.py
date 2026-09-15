from pathlib import Path

import pytest
from pydantic import ValidationError

from qm_template.config import (
    CloudInitSettings,
    default_config_path,
    default_images_dir,
    load_settings,
    packaged_config_text,
    parse_settings,
    resolve_config_path,
    ssh_key_fingerprint,
)
from qm_template.errors import QmTemplateError


def test_builtin_defaults(tmp_path):
    settings = load_settings(tmp_path / "missing.toml", explicit=False)
    assert settings.images_dir == Path("/var/lib/qm-template")
    assert settings.download.default_distro == "debian"
    assert settings.download.preferred == ("axel", "aria2c", "wget", "curl")
    assert settings.download.connections == 8
    assert settings.download.quiet is False
    assert settings.distro == {}
    assert settings.create.storage == "local-lvm"
    assert settings.create.cores == 1
    assert settings.create.memory == 1024
    assert settings.create.cpu == "host"
    assert settings.vmid.start == 9000
    assert settings.vmid.step == 1
    assert settings.cloudinit.user == "debian"
    assert settings.cloudinit.password == "debian"
    assert settings.cloudinit.sshkeys == ()
    assert settings.cloudinit.sshkeys_files == ()


def test_default_config_path():
    assert default_config_path() == Path("/etc/qm-template/config.toml")


def test_explicit_missing_file_raises(tmp_path):
    with pytest.raises(QmTemplateError):
        load_settings(tmp_path / "missing.toml", explicit=True)


def test_parse_overrides():
    settings = parse_settings(
        {
            "paths": {"images_dir": "~/images"},
            "download": {
                "default_distro": "rocky",
                "preferred": ["wget"],
                "connections": 4,
                "quiet": True,
            },
            "distro": {"rocky": {"release": 10}},
            "cloudinit": {
                "user": "admin",
                "password": "secret",
                "sshkeys": ["ssh-ed25519 AAAA"],
                "sshkeys_files": ["~/.ssh/id_ed25519.pub", "/etc/keys.pub"],
            },
            "create": {
                "storage": "local-zfs",
                "cores": 4,
                "memory": 4096,
                "cpu": "x86-64-v2-AES",
            },
            "vmid": {"start": 9000, "step": 10},
        },
        source=Path("config.toml"),
    )
    assert settings.images_dir == Path.home() / "images"
    assert settings.download.default_distro == "rocky"
    assert settings.download.preferred == ("wget",)
    assert settings.download.connections == 4
    assert settings.download.quiet is True
    assert settings.distro["rocky"].release == "10"
    assert settings.distro_overrides("rocky") == {"release": "10"}
    assert settings.create.storage == "local-zfs"
    assert settings.create.cores == 4
    assert settings.create.cpu == "x86-64-v2-AES"
    assert settings.vmid.start == 9000
    assert settings.vmid.step == 10
    assert settings.cloudinit.user == "admin"
    assert settings.cloudinit.password == "secret"
    assert settings.cloudinit.sshkeys == ("ssh-ed25519 AAAA",)
    assert settings.cloudinit.sshkeys_files == (
        "~/.ssh/id_ed25519.pub",
        "/etc/keys.pub",
    )


def test_packaged_config_text_loads_with_builtin_values(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(packaged_config_text())
    settings = load_settings(path, explicit=True)
    assert settings.download.default_distro == "debian"
    assert settings.download.quiet is False
    assert settings.create.cpu == "host"
    assert settings.vmid.start == 9000
    assert settings.vmid.step == 1
    assert settings.cloudinit.sshkeys_files == ()


def test_unknown_distro_section_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"distro": {"mint": {"release": "22"}}}, source=Path("config.toml")
        )


def test_unknown_keys_raise():
    for data in (
        {"creat": {}},
        {"paths": {"image_dir": "/tmp"}},
        {"download": {"prefered": ["wget"]}},
        {"cloudinit": {"sshkeys_file": ["~/.ssh/id_ed25519.pub"]}},
        {"create": {"user": "admin"}},
        {"create": {"start_id": 9000}},
    ):
        with pytest.raises(QmTemplateError):
            parse_settings(data, source=Path("config.toml"))


def test_distro_base_url_override():
    settings = parse_settings(
        {"distro": {"debian": {"base_url": "https://mirror.example/debian"}}},
        source=Path("config.toml"),
    )
    assert (
        settings.distro_overrides("debian")["base_url"]
        == "https://mirror.example/debian"
    )


def test_unknown_distro_parameter_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"distro": {"debian": {"typo": "x"}}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings({"distro": {"rocky": {"tag": "1"}}}, source=Path("config.toml"))


def test_invalid_distro_choice_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"distro": {"debian": {"variant": "desktop"}}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"distro": {"debian": {"release": "etch"}}}, source=Path("config.toml")
        )
    parse_settings(
        {"distro": {"debian": {"release": "bookworm-backports"}}},
        source=Path("config.toml"),
    )


def test_moved_keys_get_a_hint():
    cases = (
        ({"create": {"start_id": 9000}}, "[vmid].start"),
        ({"create": {"step": 1}}, "[vmid].step"),
        ({"download": {"debian": {"release": "trixie"}}}, "[distro.debian]"),
    )
    for data, hint in cases:
        with pytest.raises(QmTemplateError, match=hint.replace("[", r"\[")):
            parse_settings(data, source=Path("config.toml"))


def test_unknown_default_distro_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"default_distro": "mint"}}, source=Path("config.toml")
        )


def test_invalid_types_raise():
    with pytest.raises(QmTemplateError):
        parse_settings({"create": {"cores": "many"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"create": {"cpu": 4}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"vmid": {"start": "many"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"vmid": {"step": "many"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"download": {"preferred": "wget"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"connections": "many"}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings({"download": {"quiet": "maybe"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"cloudinit": {"sshkeys": "ssh-ed25519 AAAA"}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"cloudinit": {"sshkeys_files": "~/.ssh/id_ed25519.pub"}},
            source=Path("config.toml"),
        )


def test_invalid_sshkey_entry_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"cloudinit": {"sshkeys": ["ssh-ed25519 AAAA", "AAAA not-a-key"]}},
            source=Path("config.toml"),
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"cloudinit": {"sshkeys": ["ssh-ed25519 !!!invalid!!!"]}},
            source=Path("config.toml"),
        )
    with pytest.raises(ValidationError):
        CloudInitSettings(sshkeys=("not-a-key",))


def test_sshkey_entries_are_stripped():
    settings = parse_settings(
        {"cloudinit": {"sshkeys": ["  ssh-ed25519 AAAA  "]}},
        source=Path("config.toml"),
    )
    assert settings.cloudinit.sshkeys == ("ssh-ed25519 AAAA",)


def test_non_positive_connections_raise():
    with pytest.raises(QmTemplateError):
        parse_settings({"download": {"connections": 0}}, source=Path("config.toml"))


def test_invalid_vmid_constraints_raise():
    with pytest.raises(QmTemplateError):
        parse_settings({"vmid": {"start": 50}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"vmid": {"step": 0}}, source=Path("config.toml"))


def test_resolve_config_path_prefers_cli_then_env(monkeypatch, tmp_path):
    assert resolve_config_path(str(tmp_path / "cli.toml")) == (
        tmp_path / "cli.toml",
        True,
    )
    monkeypatch.setenv("QM_TEMPLATE_CONFIG", str(tmp_path / "env.toml"))
    assert resolve_config_path(None) == (tmp_path / "env.toml", True)
    monkeypatch.delenv("QM_TEMPLATE_CONFIG")
    assert resolve_config_path(None) == (default_config_path(), False)


def test_non_table_sections_raise():
    with pytest.raises(QmTemplateError):
        parse_settings({"paths": "x"}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"distro": {"debian": "x"}}, source=Path("config.toml"))


def test_download_parameter_types_raise():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"distro": {"debian": {"release": True}}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"distro": {"debian": {"release": 1.5}}}, source=Path("config.toml")
        )


def test_invalid_toml_raises(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[paths\n")
    with pytest.raises(QmTemplateError):
        load_settings(path, explicit=True)


def test_toml_is_overridden_by_the_environment(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[download]\nconnections = 4\n")
    monkeypatch.setenv("QM_TEMPLATE_DOWNLOAD__CONNECTIONS", "3")
    settings = load_settings(path, explicit=True)
    assert settings.download.connections == 3


def test_environment_overrides_builtin_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("QM_TEMPLATE_VMID__START", "9100")
    monkeypatch.setenv("QM_TEMPLATE_DOWNLOAD__QUIET", "true")
    settings = load_settings(tmp_path / "missing.toml", explicit=False)
    assert settings.vmid.start == 9100
    assert settings.download.quiet is True


def test_explicit_config_with_unknown_key_raises(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('images_dir = "x"\n')
    with pytest.raises(QmTemplateError):
        load_settings(path, explicit=True)


def test_environment_overrides_are_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("QM_TEMPLATE_TEST_DIR", str(tmp_path))
    settings = parse_settings(
        {"paths": {"images_dir": "$QM_TEMPLATE_TEST_DIR/images"}},
        source=Path("config.toml"),
    )
    assert settings.images_dir == tmp_path / "images"


def test_default_images_dir():
    assert default_images_dir() == Path("/var/lib/qm-template")


def test_ssh_key_fingerprint_ignores_short_lines():
    assert ssh_key_fingerprint("ssh-ed25519") is None
    assert ssh_key_fingerprint("") is None

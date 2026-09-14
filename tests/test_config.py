from pathlib import Path

import pytest

from qm_template.config import default_config_path, load_settings, parse_settings
from qm_template.errors import QmTemplateError


def test_builtin_defaults(tmp_path):
    settings = load_settings(tmp_path / "missing.toml", explicit=False)
    assert settings.images_dir == Path("/var/lib/qm-template")
    assert settings.download.default_distro == "debian"
    assert settings.download.preferred == ("axel", "aria2c", "wget", "curl")
    assert settings.download.connections == 8
    assert settings.create.storage == "local-lvm"
    assert settings.create.cores == 1
    assert settings.create.memory == 1024
    assert settings.create.sshkeys == ()
    assert settings.create.sshkeys_file == ("~/.ssh/id_ed25519.pub",)


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
                "rocky": {"release": 10},
            },
            "create": {
                "storage": "local-zfs",
                "cores": 4,
                "memory": 4096,
                "sshkeys": ["ssh-ed25519 AAAA"],
                "sshkeys_file": ["~/.ssh/id_ed25519.pub", "/etc/keys.pub"],
            },
        },
        source=Path("config.toml"),
    )
    assert settings.images_dir == Path.home() / "images"
    assert settings.download.default_distro == "rocky"
    assert settings.download.preferred == ("wget",)
    assert settings.download.connections == 4
    assert settings.download.defaults["rocky"]["release"] == "10"
    assert settings.create.storage == "local-zfs"
    assert settings.create.cores == 4
    assert settings.create.sshkeys == ("ssh-ed25519 AAAA",)
    assert settings.create.sshkeys_file == (
        "~/.ssh/id_ed25519.pub",
        "/etc/keys.pub",
    )


def test_unknown_distro_section_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"mint": {"release": "22"}}}, source=Path("config.toml")
        )


def test_unknown_distro_parameter_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"debian": {"typo": "x"}}}, source=Path("config.toml")
        )


def test_invalid_types_raise():
    with pytest.raises(QmTemplateError):
        parse_settings({"create": {"cores": "many"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"download": {"preferred": "wget"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"connections": "many"}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"create": {"sshkeys": "ssh-ed25519 AAAA"}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"create": {"sshkeys_file": "~/.ssh/id_ed25519.pub"}},
            source=Path("config.toml"),
        )


def test_invalid_sshkey_entry_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"create": {"sshkeys": ["ssh-ed25519 AAAA", "AAAA not-a-key"]}},
            source=Path("config.toml"),
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"create": {"sshkeys": ["ssh-ed25519 !!!invalid!!!"]}},
            source=Path("config.toml"),
        )


def test_sshkey_entries_are_stripped():
    settings = parse_settings(
        {"create": {"sshkeys": ["  ssh-ed25519 AAAA  "]}},
        source=Path("config.toml"),
    )
    assert settings.create.sshkeys == ("ssh-ed25519 AAAA",)


def test_non_positive_connections_raise():
    with pytest.raises(QmTemplateError):
        parse_settings({"download": {"connections": 0}}, source=Path("config.toml"))

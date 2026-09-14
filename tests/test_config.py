from pathlib import Path

import pytest

from qm_template.config import (
    default_config_path,
    default_images_dir,
    load_settings,
    parse_settings,
    resolve_config_path,
    ssh_key_fingerprint,
    write_default_config,
)
from qm_template.errors import QmTemplateError


def test_builtin_defaults(tmp_path):
    settings = load_settings(tmp_path / "missing.toml", explicit=False)
    assert settings.images_dir == Path("/var/lib/qm-template")
    assert settings.download.default_distro == "debian"
    assert settings.download.preferred == ("axel", "aria2c", "wget", "curl")
    assert settings.download.connections == 8
    assert settings.download.quiet is False
    assert settings.create.storage == "local-lvm"
    assert settings.create.cores == 1
    assert settings.create.memory == 1024
    assert settings.create.cpu == "host"
    assert settings.create.start_id == 9000
    assert settings.create.step == 1
    assert settings.create.sshkeys == ()
    assert settings.create.sshkeys_files == ()


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
                "rocky": {"release": 10},
            },
            "create": {
                "storage": "local-zfs",
                "cores": 4,
                "memory": 4096,
                "cpu": "x86-64-v2-AES",
                "start_id": 9000,
                "step": 10,
                "sshkeys": ["ssh-ed25519 AAAA"],
                "sshkeys_files": ["~/.ssh/id_ed25519.pub", "/etc/keys.pub"],
            },
        },
        source=Path("config.toml"),
    )
    assert settings.images_dir == Path.home() / "images"
    assert settings.download.default_distro == "rocky"
    assert settings.download.preferred == ("wget",)
    assert settings.download.connections == 4
    assert settings.download.quiet is True
    assert settings.download.defaults["rocky"]["release"] == "10"
    assert settings.create.storage == "local-zfs"
    assert settings.create.cores == 4
    assert settings.create.cpu == "x86-64-v2-AES"
    assert settings.create.start_id == 9000
    assert settings.create.step == 10
    assert settings.create.sshkeys == ("ssh-ed25519 AAAA",)
    assert settings.create.sshkeys_files == (
        "~/.ssh/id_ed25519.pub",
        "/etc/keys.pub",
    )


def test_write_default_config_creates_file(tmp_path):
    path = tmp_path / "etc" / "config.toml"
    assert write_default_config(path) is True
    settings = load_settings(path, explicit=True)
    assert settings.download.default_distro == "debian"
    assert settings.download.quiet is False
    assert settings.create.cpu == "host"
    assert settings.create.start_id == 9000
    assert settings.create.step == 1
    assert settings.create.sshkeys_files == ()


def test_write_default_config_keeps_existing_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("# keep me\n")
    assert write_default_config(path) is False
    assert path.read_text() == "# keep me\n"


def test_unknown_distro_section_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"mint": {"release": "22"}}}, source=Path("config.toml")
        )


def test_unknown_keys_raise():
    for data in (
        {"creat": {}},
        {"paths": {"image_dir": "/tmp"}},
        {"download": {"prefered": ["wget"]}},
        {"create": {"sshkeys_file": ["~/.ssh/id_ed25519.pub"]}},
    ):
        with pytest.raises(QmTemplateError):
            parse_settings(data, source=Path("config.toml"))


def test_unknown_distro_parameter_raises():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"debian": {"typo": "x"}}}, source=Path("config.toml")
        )


def test_invalid_types_raise():
    with pytest.raises(QmTemplateError):
        parse_settings({"create": {"cores": "many"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"create": {"cpu": 4}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"create": {"start_id": "many"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"create": {"step": "many"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"download": {"preferred": "wget"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"connections": "many"}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings({"download": {"quiet": "yes"}}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"create": {"sshkeys": "ssh-ed25519 AAAA"}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"create": {"sshkeys_files": "~/.ssh/id_ed25519.pub"}},
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


def test_resolve_config_path_prefers_cli_then_env(monkeypatch, tmp_path):
    assert resolve_config_path(str(tmp_path / "cli.toml")) == (
        tmp_path / "cli.toml",
        True,
    )
    monkeypatch.setenv("QM_TEMPLATE_CONFIG", str(tmp_path / "env.toml"))
    assert resolve_config_path(None) == (tmp_path / "env.toml", True)
    monkeypatch.delenv("QM_TEMPLATE_CONFIG")
    assert resolve_config_path(None) == (default_config_path(), False)


def test_write_default_config_ignores_write_errors(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("")
    assert write_default_config(blocker / "config.toml") is False


def test_non_table_sections_raise():
    with pytest.raises(QmTemplateError):
        parse_settings({"paths": "x"}, source=Path("config.toml"))
    with pytest.raises(QmTemplateError):
        parse_settings({"download": {"debian": "x"}}, source=Path("config.toml"))


def test_download_parameter_types_raise():
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"debian": {"release": True}}}, source=Path("config.toml")
        )
    with pytest.raises(QmTemplateError):
        parse_settings(
            {"download": {"debian": {"release": 1.5}}}, source=Path("config.toml")
        )


def test_invalid_toml_raises(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[paths\n")
    with pytest.raises(QmTemplateError):
        load_settings(path, explicit=True)


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

import pytest
from pydantic import ValidationError

from qm_template.cloudinit import (
    DEFAULT_USER,
    collect_ssh_keys,
    meta_data,
    network_config,
    require_credentials,
    resolve_user,
    sshkeys_file,
    user_data,
)
from qm_template.config import CloudInitSettings
from qm_template.errors import QmTemplateError


def test_collect_ssh_keys_merges_and_dedupes_inline_and_files(tmp_path):
    keys = tmp_path / "id_ed25519.pub"
    keys.write_text(
        "ssh-ed25519 CCCC\n# comment\n\nssh-ed25519 AAAA alt-comment\n"
        "ssh-rsa not@base64@\n"
    )
    settings = CloudInitSettings(
        sshkeys=("ssh-ed25519 AAAA", "ssh-ed25519 BBBB"),
        sshkeys_files=(str(keys), str(tmp_path / "missing.pub")),
    )
    assert collect_ssh_keys(settings) == (
        "ssh-ed25519 AAAA",
        "ssh-ed25519 BBBB",
        "ssh-ed25519 CCCC",
    )


def test_collect_ssh_keys_without_inline_uses_file(tmp_path):
    keys = tmp_path / "id_ed25519.pub"
    keys.write_text("ssh-ed25519 CCCC\n")
    settings = CloudInitSettings(sshkeys_files=(str(keys),))
    assert collect_ssh_keys(settings) == ("ssh-ed25519 CCCC",)


def test_cloudinit_settings_reject_invalid_inline_entry():
    with pytest.raises(ValidationError):
        CloudInitSettings(sshkeys=("not-a-key",))


def test_sshkeys_file_writes_and_removes_temporary_file(tmp_path):
    keys = tmp_path / "id_ed25519.pub"
    keys.write_text("ssh-ed25519 CCCC\ngarbage line\n")
    collected = collect_ssh_keys(CloudInitSettings(sshkeys_files=(str(keys),)))
    with sshkeys_file(collected) as path:
        assert path.read_text() == "ssh-ed25519 CCCC\n"
    assert not path.exists()


def test_require_credentials_requires_a_login_method():
    with pytest.raises(QmTemplateError, match="no login method"):
        require_credentials(CloudInitSettings())


def test_require_credentials_accepts_a_password_without_keys():
    assert require_credentials(CloudInitSettings(password="secret")) == ()


def test_require_credentials_accepts_keys_without_a_password():
    settings = CloudInitSettings(sshkeys=("ssh-ed25519 AAAA",))
    assert require_credentials(settings) == ("ssh-ed25519 AAAA",)


def test_resolve_user_prefers_the_configured_user(tmp_path):
    images = tmp_path / "images"
    image = images / "debian" / "13" / "debian-13.qcow2"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"")
    assert resolve_user("admin", image, images) == "admin"


def test_resolve_user_uses_the_distro_default(tmp_path):
    images = tmp_path / "images"
    image = images / "freebsd" / "15.1" / "freebsd.qcow2"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"")
    assert resolve_user("", image, images) == "freebsd"


def test_resolve_user_uses_the_declared_default_user(tmp_path):
    images = tmp_path / "images"
    image = images / "amazonlinux" / "2023" / "al2023.qcow2"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"")
    assert resolve_user("", image, images) == "ec2-user"


def test_resolve_user_falls_back_outside_known_distros(tmp_path):
    images = tmp_path / "images"
    image = images / "debian-13-genericcloud-amd64.qcow2"
    images.mkdir()
    image.write_bytes(b"")
    assert resolve_user("", image, images) == DEFAULT_USER
    other = tmp_path / "elsewhere" / "debian-13.qcow2"
    other.parent.mkdir()
    other.write_bytes(b"")
    assert resolve_user("", other, images) == DEFAULT_USER


def test_user_data_configures_the_cloud_user():
    settings = CloudInitSettings(
        user="admin",
        password="pa:ss",
        sshkeys=("ssh-ed25519 AAAA",),
    )
    document = user_data(settings, "debian-13")
    assert document.startswith("#cloud-config\n")
    assert 'hostname: "debian-13"' in document
    assert '- name: "admin"' in document
    assert '      - "ssh-ed25519 AAAA"' in document
    assert 'password: "pa:ss"' in document
    assert "ssh_pwauth: true" in document
    assert "    lock_passwd: false" in document
    assert 'shell: "/bin/bash"' in document


def test_user_data_without_a_password_locks_it(caplog):
    settings = CloudInitSettings(user="admin", sshkeys=("ssh-ed25519 AAAA",))
    document = user_data(settings, "vm")
    assert '- name: "admin"' in document
    assert "    lock_passwd: true" in document
    assert "chpasswd:" not in document
    assert "ssh_pwauth" not in document
    assert "No SSH keys" not in caplog.text


def test_user_data_password_login_without_keys(caplog):
    document = user_data(CloudInitSettings(user="admin", password="secret"), "vm")
    assert 'password: "secret"' in document
    assert "ssh_pwauth: true" in document
    assert "only allow password login" in caplog.text


def test_user_data_can_omit_the_shell():
    settings = CloudInitSettings(shell="", sshkeys=("ssh-ed25519 AAAA",))
    document = user_data(settings, "vm")
    assert "shell:" not in document


def test_user_data_escapes_special_characters():
    settings = CloudInitSettings(
        password='quote" back\\slash\nnewline',
        sshkeys=("ssh-ed25519 AAAA",),
    )
    document = user_data(settings, "vm")
    assert 'password: "quote\\" back\\\\slash\\nnewline"' in document


def test_user_data_without_credentials_warns(caplog):
    document = user_data(CloudInitSettings(), "vm")
    assert "ssh_authorized_keys" not in document
    assert "chpasswd:" not in document
    assert "No SSH keys or password configured" in caplog.text


def test_meta_data_sets_instance_id_and_hostname():
    document = meta_data("debian-13")
    assert 'instance-id: "iid-debian-13"' in document
    assert 'local-hostname: "debian-13"' in document


def test_network_config_dhcps_en_and_eth_interfaces():
    document = network_config()
    assert document.startswith("version: 2\n")
    assert 'name: "en*"' in document
    assert 'name: "eth*"' in document
    assert document.count("dhcp4: true") == 2

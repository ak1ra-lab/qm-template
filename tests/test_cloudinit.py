import pytest

from qm_template.cloudinit import collect_ssh_keys, meta_data, sshkeys_file, user_data
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


def test_collect_ssh_keys_rejects_invalid_inline_entry():
    with pytest.raises(QmTemplateError):
        collect_ssh_keys(CloudInitSettings(sshkeys=("not-a-key",)))


def test_sshkeys_file_writes_and_removes_temporary_file(tmp_path):
    keys = tmp_path / "id_ed25519.pub"
    keys.write_text("ssh-ed25519 CCCC\ngarbage line\n")
    settings = CloudInitSettings(sshkeys_files=(str(keys),))
    with sshkeys_file(settings) as path:
        assert path.read_text() == "ssh-ed25519 CCCC\n"
    assert not path.exists()


def test_sshkeys_file_requires_keys():
    with pytest.raises(QmTemplateError):
        with sshkeys_file(CloudInitSettings()):
            pass


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


def test_user_data_escapes_special_characters():
    settings = CloudInitSettings(
        password='quote" back\\slash\nnewline',
        sshkeys=("ssh-ed25519 AAAA",),
    )
    document = user_data(settings, "vm")
    assert 'password: "quote\\" back\\\\slash\\nnewline"' in document


def test_user_data_requires_keys():
    with pytest.raises(QmTemplateError):
        user_data(CloudInitSettings(), "vm")


def test_meta_data_sets_instance_id_and_hostname():
    document = meta_data("debian-13")
    assert 'instance-id: "iid-debian-13"' in document
    assert 'local-hostname: "debian-13"' in document

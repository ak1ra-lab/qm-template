import pytest

from qm_template.errors import QmTemplateError
from qm_template.http import latest_name, natural_key


def test_natural_key_orders_versions_numerically():
    names = [
        "Rocky-9-GenericCloud-Base-9.9-20250101.0.x86_64.qcow2",
        "Rocky-9-GenericCloud-Base-9.10-20250101.0.x86_64.qcow2",
    ]
    assert max(names, key=natural_key) == names[1]


def test_latest_name_picks_latest_match():
    names = ["20260101-1", "20260102-2", "README"]
    assert latest_name(names, r"\d{8}-\d+", source="test") == "20260102-2"


def test_latest_name_raises_without_match():
    with pytest.raises(QmTemplateError):
        latest_name(["README"], r"\d+", source="test")

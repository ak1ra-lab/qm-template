import argparse

from qm_template.cli import create_parser


def test_version_flag() -> None:
    parser = create_parser()
    assert any(
        isinstance(a, argparse._VersionAction) and a.option_strings == ["--version"]
        for a in parser._actions
    )

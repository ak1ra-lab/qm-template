# PYTHON_ARGCOMPLETE_OK

import argparse
from typing import Sequence

import argcomplete

from qm_template import __version__


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Proxmox VE template helper scripts",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = create_parser()
    argcomplete.autocomplete(parser)
    parser.parse_args(argv)

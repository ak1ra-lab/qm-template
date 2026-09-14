import logging
import sys

from qm_template import PROGRAM

log = logging.getLogger(PROGRAM)


def setup_logging() -> None:
    """Configure the root logger to write to stderr."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

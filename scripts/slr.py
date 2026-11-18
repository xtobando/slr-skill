# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "PyYAML>=6,<7",
#     "rich>=13,<15",
#     "pypdf>=6,<7",
#     "PyMuPDF>=1.24.10,<2",
# ]
# ///

"""Run bundled SLR operations directly from any working directory."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
if sys.version_info < (3, 11):  # noqa: UP036 - give old interpreters a clear setup error
    raise SystemExit("This skill requires Python 3.11 or newer.")

# Prefer the bundled implementation even if another workbench is installed.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from slr_workbench.cli import app
except ModuleNotFoundError as error:
    if error.name in {"yaml", "rich"}:
        raise SystemExit(
            "Missing core Python libraries. Follow references/setup.md in the skill folder."
        ) from None
    raise

if __name__ == "__main__":
    app()

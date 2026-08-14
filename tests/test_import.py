"""Smoke tests: the package imports and exposes a version and a CLI."""

import wattwarden
from wattwarden.cli import main


def test_version_present():
    assert wattwarden.__version__


def test_cli_main_runs():
    # Explicit empty argv: main() with None would inherit the test
    # runner's own sys.argv (this exact bug shipped once).
    assert main([]) == 0

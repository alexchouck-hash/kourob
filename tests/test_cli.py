"""M0 acceptance: `kourob --help` lists every top-level command, and stubs are honest.

Brief section 12, M0: "uv run kourob --help lists all top-level commands as stubs."
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from kourob import __version__
from kourob.cli import app

runner = CliRunner()

#: Every top-level command named in the brief. Adding a command to the CLI without adding
#: it here is a test failure, and so is the reverse.
EXPECTED_COMMANDS = {
    "init",
    "ingest",
    "query",
    "serve",
    "attach",
    "pack",
    "trace",
    "publish",
    "doctor",
    "version",
    "run",
    "train",
    "tend",
    "rollback",
    "cell",
    "ledger",
    "meter",
    "schema",
    "routes",
    "tools",
    "keys",
    "loop",
    "distill",
    "scope",
}


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_help_lists_every_expected_command() -> None:
    result = runner.invoke(app, ["--help"])
    # Typer wraps the help table, so match on command names, not on layout.
    listed = {name for name in EXPECTED_COMMANDS if name in result.output}
    assert listed == EXPECTED_COMMANDS, f"missing from --help: {EXPECTED_COMMANDS - listed}"


def test_no_undeclared_commands() -> None:
    """The CLI must not grow commands that this test does not know about."""
    import typer.main

    command = typer.main.get_command(app)
    actual = set(command.commands)  # type: ignore[attr-defined]
    assert actual == EXPECTED_COMMANDS, f"undeclared: {actual - EXPECTED_COMMANDS}"


def test_version_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


@pytest.mark.parametrize(
    "argv",
    [
        ["init", "demo"],
        ["ingest", "events.jsonl"],
        ["query", "what is a bridge"],
        ["trace", "rcpt_01J"],
        ["ledger", "verify"],
        ["meter", "report"],
        ["schema", "list"],
        ["routes", "list"],
        ["keys", "show"],
        ["loop", "run", "lint"],
        ["scope", "check", "anything"],
        ["tend"],
        ["rollback", "evt_01J"],
        ["cell", "size"],
    ],
)
def test_stubs_exit_two_and_name_their_milestone(argv: list[str]) -> None:
    """An unimplemented command says so, names its milestone, and exits 2.

    Exit 2 rather than 0 so a script that calls a stub fails loudly.
    """
    result = runner.invoke(app, argv)
    assert result.exit_code == 2, f"{argv} exited {result.exit_code}"
    assert "not implemented yet" in result.output
    assert "milestone M" in result.output

import json

import pytest

from finplan.cli import main


@pytest.fixture
def run_cli(capsys):
    """Run the CLI and return (exit_code, stdout, stderr)."""

    def _run(*argv):
        try:
            code = main(list(argv))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if isinstance(exc.code, str):
                print(exc.code)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


@pytest.fixture
def run_json(run_cli):
    """Run the CLI with --json and return the parsed 'results' block."""

    def _run(*argv):
        code, out, err = run_cli(*argv, "--json")
        assert code == 0, f"command failed: {err or out}"
        return json.loads(out)["results"]

    return _run

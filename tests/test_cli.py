"""Tests for kovnet.cli using Click's CliRunner."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from kovnet.cli import cli

runner = CliRunner()


class TestMainHelp:
    def test_help_shows_all_commands(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        expected_commands = [
            "login",
            "logout",
            "children",
            "contracts",
            "invoices",
            "holidays",
            "open",
            "explore",
            "completion",
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in help output"

    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        import re

        assert re.search(r"\d+\.\d+\.\d+", result.output)


class TestLoginCommand:
    def test_help(self):
        result = runner.invoke(cli, ["login", "--help"])
        assert result.exit_code == 0
        assert "--username" in result.output or "-u" in result.output
        assert "--password" in result.output or "-p" in result.output
        assert "--store" in result.output
        assert "--location" in result.output
        assert "--code" in result.output

    def test_store_saves_env_file(self, tmp_path):
        """--store should write credentials to ~/.config/kovnet/.env."""
        env_file = tmp_path / ".env"
        fake_session = {
            "cookies": {"_session": "tok123"},
            "location_id": "7043",
            "username": "user@test.nl",
        }

        with (
            patch("kovnet.cli.KovNetAuth.login", return_value=fake_session),
            patch("kovnet.client.SESSION_PATH", tmp_path / "session.json"),
        ):
            from kovnet import client as client_mod

            original = client_mod.SESSION_PATH
            client_mod.SESSION_PATH = tmp_path / "session.json"
            try:
                result = runner.invoke(
                    cli,
                    [
                        "login",
                        "-u",
                        "user@test.nl",
                        "-p",
                        "secret",
                        "--store",
                    ],
                )
            finally:
                client_mod.SESSION_PATH = original

        assert result.exit_code == 0
        assert env_file.exists()
        content = env_file.read_text()
        assert "KOVNET_USERNAME=user@test.nl" in content
        assert "KOVNET_PASSWORD=secret" in content
        mode = env_file.stat().st_mode & 0o777
        assert mode == 0o600


class TestLogoutCommand:
    def test_help(self):
        result = runner.invoke(cli, ["logout", "--help"])
        assert result.exit_code == 0

    def test_not_logged_in(self):
        """Logout when no session file exists should print a message."""
        import os
        import tempfile

        from kovnet.client import SESSION_PATH

        fake_path = os.path.join(tempfile.gettempdir(), "kovnet-test-nonexistent-session.json")
        with patch("kovnet.client.SESSION_PATH", new=type(SESSION_PATH)(fake_path)):
            result = runner.invoke(cli, ["logout"])
            assert result.exit_code == 0
            assert "uitgelogd" in result.output.lower()


class TestChildrenCommand:
    def test_help(self):
        result = runner.invoke(cli, ["children", "--help"])
        assert result.exit_code == 0


class TestContractsCommand:
    def test_help(self):
        result = runner.invoke(cli, ["contracts", "--help"])
        assert result.exit_code == 0


class TestInvoicesCommand:
    def test_help(self):
        result = runner.invoke(cli, ["invoices", "--help"])
        assert result.exit_code == 0
        assert "--contract" in result.output


class TestHolidaysCommand:
    def test_help(self):
        result = runner.invoke(cli, ["holidays", "--help"])
        assert result.exit_code == 0
        assert "--contract" in result.output


class TestOpenCommand:
    def test_help(self):
        result = runner.invoke(cli, ["open", "--help"])
        assert result.exit_code == 0
        assert "REF" in result.output

    def test_invalid_number_no_cache(self):
        """Opening a non-existent invoice number should fail."""
        from kovnet import cli as cli_mod

        cli_mod._last_invoice_refs.clear()
        result = runner.invoke(cli, ["open", "999"])
        assert result.exit_code != 0


class TestExploreCommand:
    def test_help(self):
        result = runner.invoke(cli, ["explore", "--help"])
        assert result.exit_code == 0
        assert "URL" in result.output


class TestCompletionCommand:
    def test_help(self):
        result = runner.invoke(cli, ["completion", "--help"])
        assert result.exit_code == 0
        assert "bash" in result.output.lower()
        assert "zsh" in result.output.lower()
        assert "fish" in result.output.lower()

    def test_invalid_shell(self):
        result = runner.invoke(cli, ["completion", "powershell"])
        assert result.exit_code != 0

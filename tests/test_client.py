"""Tests for kovnet.client."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from kovnet.client import KovNetClient, _load_session, _save_session


class TestSaveLoadSession:
    def test_round_trip(self, tmp_path):
        session_file = tmp_path / "session.json"
        session = {"cookies": {"_session": "abc123"}, "location_id": "7043"}

        with patch("kovnet.client.SESSION_PATH", session_file):
            _save_session(session)
            loaded = _load_session()

        assert loaded == session

    def test_load_nonexistent_returns_none(self, tmp_path):
        session_file = tmp_path / "nonexistent" / "session.json"
        with patch("kovnet.client.SESSION_PATH", session_file):
            assert _load_session() is None

    def test_load_invalid_json_returns_none(self, tmp_path):
        session_file = tmp_path / "session.json"
        session_file.write_text("not valid json {{{")
        with patch("kovnet.client.SESSION_PATH", session_file):
            assert _load_session() is None

    def test_save_creates_parent_dirs(self, tmp_path):
        session_file = tmp_path / "deep" / "nested" / "session.json"
        session = {"cookies": {"_session": "test"}}

        with patch("kovnet.client.SESSION_PATH", session_file):
            _save_session(session)

        assert session_file.exists()
        assert json.loads(session_file.read_text()) == session

    def test_file_permissions(self, tmp_path):
        session_file = tmp_path / "session.json"
        session = {"cookies": {"_session": "secret"}}

        with patch("kovnet.client.SESSION_PATH", session_file):
            _save_session(session)

        mode = session_file.stat().st_mode & 0o777
        assert mode == 0o600


class TestKovNetClientNotAuthenticated:
    def test_raises_when_no_session(self):
        with (
            patch("kovnet.client.KovNetAuth.get_session", return_value=None),
            pytest.raises(RuntimeError, match="Niet ingelogd"),
            KovNetClient(),
        ):
            pass

    def test_raises_with_message_about_login(self):
        with (
            patch("kovnet.client.KovNetAuth.get_session", return_value=None),
            pytest.raises(RuntimeError, match="kovnet login"),
            KovNetClient(),
        ):
            pass


class TestKovNetClientLocationId:
    def test_location_id_from_session(self):
        client = KovNetClient.__new__(KovNetClient)
        client.session = {"cookies": {}, "location_id": "7043"}
        assert client.location_id == "7043"

    def test_location_id_none_when_no_session(self):
        client = KovNetClient.__new__(KovNetClient)
        client.session = None
        assert client.location_id is None

    def test_location_id_none_when_missing(self):
        client = KovNetClient.__new__(KovNetClient)
        client.session = {"cookies": {}}
        assert client.location_id is None

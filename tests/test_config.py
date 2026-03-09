import os
import pytest
from unittest.mock import patch
from config import load_config, _env


class TestEnv:
    def test_strips_double_quotes(self, monkeypatch):
        monkeypatch.setenv('FOO', '"bar"')
        assert _env('FOO') == 'bar'

    def test_strips_single_quotes(self, monkeypatch):
        monkeypatch.setenv('FOO', "'bar'")
        assert _env('FOO') == 'bar'

    def test_returns_plain_value(self, monkeypatch):
        monkeypatch.setenv('FOO', 'bar')
        assert _env('FOO') == 'bar'

    def test_returns_default(self):
        assert _env('NONEXISTENT_KEY_12345', 'default') == 'default'

    def test_returns_none_without_default(self):
        assert _env('NONEXISTENT_KEY_12345') is None


@patch('config.load_dotenv')
class TestLoadConfig:
    def test_loads_required_vars(self, mock_dotenv, monkeypatch):
        monkeypatch.setenv('GDRIVE_REMOTE', 'gdrive:Test/Vault')
        monkeypatch.delenv('POLL_INTERVAL_SECONDS', raising=False)
        cfg = load_config()
        assert cfg['gdrive_remote'] == 'gdrive:Test/Vault'
        assert cfg['poll_interval'] == 300

    def test_custom_poll_interval(self, mock_dotenv, monkeypatch):
        monkeypatch.setenv('GDRIVE_REMOTE', 'gdrive:Test/Vault')
        monkeypatch.setenv('POLL_INTERVAL_SECONDS', '60')
        cfg = load_config()
        assert cfg['poll_interval'] == 60

    def test_missing_gdrive_remote_raises(self, mock_dotenv, monkeypatch):
        monkeypatch.delenv('GDRIVE_REMOTE', raising=False)
        with pytest.raises(ValueError, match='GDRIVE_REMOTE'):
            load_config()

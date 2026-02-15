"""Tests for configuration and settings."""

from pathlib import Path

from tradingbot.config.loader import deep_merge, load_config, load_toml
from tradingbot.config.settings import AppSettings


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99, "z": 100}}
        result = deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}

    def test_does_not_mutate_base(self):
        base = {"a": 1}
        override = {"a": 2}
        deep_merge(base, override)
        assert base == {"a": 1}


class TestLoadToml:
    def test_load_default_config(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "default.toml"
        if config_path.exists():
            config = load_toml(config_path)
            assert "bot" in config
            assert config["bot"]["name"] == "tradingbot"

    def test_load_missing_file_in_load_config(self):
        config = load_config(Path("/nonexistent/file.toml"))
        assert config == {}


class TestAppSettings:
    def test_defaults(self, monkeypatch):
        # Clear env vars that might interfere
        for key in ["CCXT_API_KEY", "ALPACA_API_KEY", "POLYMARKET_PRIVATE_KEY"]:
            monkeypatch.delenv(key, raising=False)

        settings = AppSettings()
        assert settings.log_level == "INFO"
        assert settings.dry_run is True
        assert "ccxt" in settings.enabled_connectors

    def test_ccxt_defaults(self, monkeypatch):
        monkeypatch.delenv("CCXT_EXCHANGE", raising=False)
        monkeypatch.delenv("CCXT_API_KEY", raising=False)
        settings = AppSettings()
        assert settings.ccxt.exchange == "binance"
        assert settings.ccxt.testnet is True
        assert settings.ccxt.api_key == ""

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CCXT_API_KEY", "test_key_123")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        settings = AppSettings()
        assert settings.ccxt.api_key == "test_key_123"
        assert settings.log_level == "DEBUG"

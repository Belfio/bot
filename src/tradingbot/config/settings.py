"""Application settings loaded from environment variables."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class CCXTSettings(BaseSettings):
    model_config = {"env_prefix": "CCXT_"}

    exchange: str = "binance"
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True


class AlpacaSettings(BaseSettings):
    model_config = {"env_prefix": "ALPACA_"}

    api_key: str = ""
    api_secret: str = ""
    paper: bool = True


class PolymarketSettings(BaseSettings):
    model_config = {"env_prefix": "POLYMARKET_"}

    private_key: str = ""
    chain_id: int = 137
    host: str = "https://clob.polymarket.com"


class AppSettings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    log_level: str = "INFO"
    enabled_connectors: list[str] = Field(default=["ccxt", "alpaca", "polymarket"])

    @field_validator("enabled_connectors", mode="before")
    @classmethod
    def parse_connectors(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    web_host: str = "127.0.0.1"
    web_port: int = 8000
    dry_run: bool = True

    ccxt: CCXTSettings = Field(default_factory=CCXTSettings)
    alpaca: AlpacaSettings = Field(default_factory=AlpacaSettings)
    polymarket: PolymarketSettings = Field(default_factory=PolymarketSettings)

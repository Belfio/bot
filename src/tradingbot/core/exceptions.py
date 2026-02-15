"""Custom exceptions for the trading bot."""


class TradingBotError(Exception):
    """Base exception for all trading bot errors."""


class ConnectorError(TradingBotError):
    """Raised when a connector encounters an error communicating with an exchange."""

    def __init__(self, connector_name: str, message: str) -> None:
        self.connector_name = connector_name
        super().__init__(f"[{connector_name}] {message}")


class OrderError(TradingBotError):
    """Raised when an order operation fails."""

    def __init__(self, message: str, order_id: str | None = None) -> None:
        self.order_id = order_id
        super().__init__(message)


class ConfigError(TradingBotError):
    """Raised when there is a configuration error."""

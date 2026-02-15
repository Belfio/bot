"""Protocol definitions for connectors and strategies."""

from typing import Protocol, runtime_checkable

from tradingbot.core.models import (
    Balance,
    Market,
    Order,
    OrderBook,
    OrderSide,
    OrderType,
    Position,
    Signal,
    Ticker,
)


@runtime_checkable
class BaseConnector(Protocol):
    """Async interface that all exchange connectors must implement."""

    name: str

    async def initialize(self) -> None: ...

    async def get_balance(self) -> list[Balance]: ...

    async def get_positions(self) -> list[Position]: ...

    async def get_markets(self) -> list[Market]: ...

    async def get_ticker(self, symbol: str) -> Ticker: ...

    async def get_orderbook(self, symbol: str) -> OrderBook: ...

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float | str,
        price: float | str | None = None,
    ) -> Order: ...

    async def cancel_order(self, order_id: str, symbol: str | None = None) -> bool: ...

    async def get_order(self, order_id: str, symbol: str | None = None) -> Order: ...

    async def get_order_history(self, symbol: str | None = None) -> list[Order]: ...

    async def close(self) -> None: ...


@runtime_checkable
class BaseStrategy(Protocol):
    """Async interface for trading strategies."""

    name: str

    async def initialize(self, connectors: dict[str, BaseConnector]) -> None: ...

    async def on_tick(self) -> None: ...

    async def on_order_fill(self, order: Order) -> None: ...

    async def on_position_change(self, position: Position) -> None: ...

    async def evaluate(self) -> list[Signal]: ...

    async def stop(self) -> None: ...

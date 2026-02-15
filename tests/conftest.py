"""Shared test fixtures."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from tradingbot.core.models import (
    Balance,
    Market,
    Order,
    OrderBook,
    OrderBookEntry,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Ticker,
)


@pytest.fixture
def sample_balance():
    return Balance(currency="BTC", free=Decimal("1.5"), used=Decimal("0.5"), total=Decimal("2.0"))


@pytest.fixture
def sample_position():
    return Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.5"),
        entry_price=Decimal("50000"),
        current_price=Decimal("55000"),
        unrealized_pnl=Decimal("2500"),
        side=OrderSide.BUY,
        connector_name="ccxt",
    )


@pytest.fixture
def sample_order():
    return Order(
        order_id="test-123",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        quantity=Decimal("0.5"),
        price=Decimal("50000"),
        filled_quantity=Decimal("0.25"),
        status=OrderStatus.PARTIALLY_FILLED,
        connector_name="ccxt",
    )


@pytest.fixture
def sample_market():
    return Market(
        symbol="BTC/USDT",
        base_currency="BTC",
        quote_currency="USDT",
        min_order_size=Decimal("0.001"),
        precision=8,
        active=True,
    )


@pytest.fixture
def sample_ticker():
    return Ticker(
        symbol="BTC/USDT",
        bid=Decimal("54990"),
        ask=Decimal("55010"),
        last=Decimal("55000"),
        volume_24h=Decimal("1000000"),
    )


@pytest.fixture
def sample_orderbook():
    return OrderBook(
        symbol="BTC/USDT",
        bids=[OrderBookEntry(price=Decimal("54990"), quantity=Decimal("1.5"))],
        asks=[OrderBookEntry(price=Decimal("55010"), quantity=Decimal("2.0"))],
    )


@pytest.fixture
def mock_connector():
    """A mock connector that implements BaseConnector interface."""
    mock = AsyncMock()
    mock.name = "mock_exchange"
    mock.initialize = AsyncMock()
    mock.get_balance = AsyncMock(return_value=[
        Balance(currency="USD", free=Decimal("10000"), used=Decimal("0"), total=Decimal("10000"))
    ])
    mock.get_positions = AsyncMock(return_value=[])
    mock.get_markets = AsyncMock(return_value=[])
    mock.get_ticker = AsyncMock(return_value=Ticker(symbol="TEST/USD"))
    mock.get_orderbook = AsyncMock(return_value=OrderBook(symbol="TEST/USD"))
    mock.place_order = AsyncMock(return_value=Order(
        order_id="mock-001",
        symbol="TEST/USD",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        quantity=Decimal("1"),
        status=OrderStatus.FILLED,
        connector_name="mock_exchange",
    ))
    mock.cancel_order = AsyncMock(return_value=True)
    mock.get_order = AsyncMock()
    mock.get_order_history = AsyncMock(return_value=[])
    mock.close = AsyncMock()
    return mock

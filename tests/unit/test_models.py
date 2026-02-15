"""Tests for core data models."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

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
    Signal,
    Ticker,
)


class TestEnums:
    def test_order_side_values(self):
        assert OrderSide.BUY == "buy"
        assert OrderSide.SELL == "sell"

    def test_order_type_values(self):
        assert OrderType.MARKET == "market"
        assert OrderType.LIMIT == "limit"

    def test_order_status_values(self):
        assert OrderStatus.FILLED == "filled"
        assert OrderStatus.CANCELLED == "cancelled"


class TestBalance:
    def test_create(self, sample_balance):
        assert sample_balance.currency == "BTC"
        assert sample_balance.free == Decimal("1.5")
        assert sample_balance.total == Decimal("2.0")

    def test_defaults(self):
        b = Balance(currency="ETH")
        assert b.free == Decimal(0)
        assert b.used == Decimal(0)
        assert b.total == Decimal(0)

    def test_decimal_precision(self):
        b = Balance(currency="BTC", free=Decimal("0.00000001"), total=Decimal("0.00000001"))
        assert b.free == Decimal("0.00000001")


class TestPosition:
    def test_create(self, sample_position):
        assert sample_position.symbol == "BTC/USDT"
        assert sample_position.side == OrderSide.BUY
        assert sample_position.unrealized_pnl == Decimal("2500")

    def test_json_serialization(self, sample_position):
        data = sample_position.model_dump(mode="json")
        assert data["symbol"] == "BTC/USDT"
        assert data["side"] == "buy"


class TestOrder:
    def test_create(self, sample_order):
        assert sample_order.order_id == "test-123"
        assert sample_order.status == OrderStatus.PARTIALLY_FILLED
        assert sample_order.filled_quantity == Decimal("0.25")

    def test_defaults(self):
        o = Order(
            order_id="x",
            symbol="ETH/USDT",
            side=OrderSide.SELL,
            type=OrderType.MARKET,
            quantity=Decimal("1"),
        )
        assert o.status == OrderStatus.PENDING
        assert o.filled_quantity == Decimal(0)
        assert o.price is None
        assert o.raw_data is None

    def test_json_round_trip(self, sample_order):
        data = sample_order.model_dump(mode="json")
        restored = Order.model_validate(data)
        assert restored.order_id == sample_order.order_id
        assert restored.quantity == sample_order.quantity


class TestMarket:
    def test_create(self, sample_market):
        assert sample_market.base_currency == "BTC"
        assert sample_market.active is True

    def test_defaults(self):
        m = Market(symbol="X/Y", base_currency="X", quote_currency="Y")
        assert m.min_order_size == Decimal(0)
        assert m.precision == 8


class TestTicker:
    def test_create(self, sample_ticker):
        assert sample_ticker.bid == Decimal("54990")

    def test_nullable_fields(self):
        t = Ticker(symbol="X/Y")
        assert t.bid is None
        assert t.ask is None


class TestOrderBook:
    def test_create(self, sample_orderbook):
        assert len(sample_orderbook.bids) == 1
        assert sample_orderbook.asks[0].price == Decimal("55010")

    def test_empty(self):
        ob = OrderBook(symbol="X/Y")
        assert ob.bids == []
        assert ob.asks == []


class TestSignal:
    def test_create(self):
        s = Signal(
            strategy_name="momentum",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            confidence=0.85,
        )
        assert s.confidence == 0.85
        assert s.order_type == OrderType.MARKET

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            Signal(
                strategy_name="x",
                symbol="X/Y",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                confidence=1.5,
            )

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValidationError):
            Signal(
                strategy_name="x",
                symbol="X/Y",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                confidence=-0.1,
            )

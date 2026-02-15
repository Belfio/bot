"""Mock-based tests for connectors."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradingbot.connectors.ccxt_connector import CCXTConnector
from tradingbot.core.exceptions import ConnectorError, OrderError
from tradingbot.core.models import OrderSide, OrderStatus, OrderType


class TestCCXTConnector:
    @pytest.fixture
    def connector(self):
        return CCXTConnector(
            exchange_id="binance",
            api_key="test_key",
            api_secret="test_secret",
            testnet=True,
        )

    def test_name(self, connector):
        assert connector.name == "ccxt"

    def test_exchange_not_initialized(self, connector):
        with pytest.raises(ConnectorError, match="not initialized"):
            _ = connector.exchange

    @pytest.mark.asyncio
    async def test_initialize_unknown_exchange(self):
        conn = CCXTConnector(exchange_id="nonexistent_exchange_xyz")
        with pytest.raises(ConnectorError, match="Unknown exchange"):
            await conn.initialize()

    @pytest.mark.asyncio
    async def test_get_balance(self, connector):
        mock_exchange = AsyncMock()
        mock_exchange.fetch_balance = AsyncMock(return_value={
            "total": {"BTC": 1.5, "USDT": 10000},
            "free": {"BTC": 1.0, "USDT": 8000},
            "used": {"BTC": 0.5, "USDT": 2000},
        })
        connector._exchange = mock_exchange

        balances = await connector.get_balance()
        assert len(balances) == 2
        btc = next(b for b in balances if b.currency == "BTC")
        assert btc.free == Decimal("1.0")
        assert btc.total == Decimal("1.5")

    @pytest.mark.asyncio
    async def test_get_balance_error(self, connector):
        import ccxt.async_support as ccxt_async
        mock_exchange = AsyncMock()
        mock_exchange.fetch_balance = AsyncMock(side_effect=ccxt_async.BaseError("API Error"))
        connector._exchange = mock_exchange

        with pytest.raises(ConnectorError, match="Failed to fetch balance"):
            await connector.get_balance()

    @pytest.mark.asyncio
    async def test_place_order(self, connector):
        mock_exchange = AsyncMock()
        mock_exchange.create_order = AsyncMock(return_value={
            "id": "order-1",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "amount": 0.5,
            "price": 50000,
            "filled": 0,
            "status": "open",
        })
        connector._exchange = mock_exchange

        order = await connector.place_order("BTC/USDT", OrderSide.BUY, OrderType.LIMIT, 0.5, 50000)
        assert order.order_id == "order-1"
        assert order.status == OrderStatus.OPEN
        assert order.side == OrderSide.BUY

    @pytest.mark.asyncio
    async def test_cancel_order(self, connector):
        mock_exchange = AsyncMock()
        mock_exchange.cancel_order = AsyncMock(return_value={"id": "order-1"})
        connector._exchange = mock_exchange

        result = await connector.cancel_order("order-1", "BTC/USDT")
        assert result is True

    @pytest.mark.asyncio
    async def test_map_partially_filled(self, connector):
        order_data = {
            "id": "order-2",
            "symbol": "ETH/USDT",
            "side": "sell",
            "type": "limit",
            "amount": 10,
            "price": 3000,
            "filled": 5,
            "status": "open",
        }
        order = connector._map_order(order_data)
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_quantity == Decimal("5")

    @pytest.mark.asyncio
    async def test_get_markets(self, connector):
        mock_exchange = AsyncMock()
        mock_exchange.markets = {
            "BTC/USDT": {
                "base": "BTC",
                "quote": "USDT",
                "limits": {"amount": {"min": 0.001}},
                "precision": {"amount": 8},
                "active": True,
            }
        }
        connector._exchange = mock_exchange

        markets = await connector.get_markets()
        assert len(markets) == 1
        assert markets[0].symbol == "BTC/USDT"
        assert markets[0].min_order_size == Decimal("0.001")

    @pytest.mark.asyncio
    async def test_close(self, connector):
        mock_exchange = AsyncMock()
        connector._exchange = mock_exchange

        await connector.close()
        mock_exchange.close.assert_called_once()
        assert connector._exchange is None

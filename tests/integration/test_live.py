"""Integration tests that require real API credentials.

These tests are skipped unless the relevant environment variables are set.
Run with: pytest tests/integration -v
"""

import os

import pytest

from tradingbot.config.settings import AppSettings

# Skip entire module if no credentials are configured
pytestmark = pytest.mark.skipif(
    not any([
        os.getenv("CCXT_API_KEY"),
        os.getenv("ALPACA_API_KEY"),
        os.getenv("POLYMARKET_PRIVATE_KEY"),
    ]),
    reason="No API credentials configured",
)


@pytest.fixture
def settings():
    return AppSettings()


@pytest.mark.skipif(not os.getenv("CCXT_API_KEY"), reason="CCXT_API_KEY not set")
class TestCCXTLive:
    @pytest.mark.asyncio
    async def test_initialize_and_balance(self, settings):
        from tradingbot.connectors.ccxt_connector import CCXTConnector

        conn = CCXTConnector(
            exchange_id=settings.ccxt.exchange,
            api_key=settings.ccxt.api_key,
            api_secret=settings.ccxt.api_secret,
            testnet=settings.ccxt.testnet,
        )
        await conn.initialize()
        balances = await conn.get_balance()
        assert isinstance(balances, list)
        await conn.close()


@pytest.mark.skipif(not os.getenv("ALPACA_API_KEY"), reason="ALPACA_API_KEY not set")
class TestAlpacaLive:
    @pytest.mark.asyncio
    async def test_initialize_and_balance(self, settings):
        from tradingbot.connectors.alpaca_connector import AlpacaConnector

        conn = AlpacaConnector(
            api_key=settings.alpaca.api_key,
            api_secret=settings.alpaca.api_secret,
            paper=settings.alpaca.paper,
        )
        await conn.initialize()
        balances = await conn.get_balance()
        assert len(balances) == 1
        assert balances[0].currency == "USD"
        await conn.close()


@pytest.mark.skipif(not os.getenv("POLYMARKET_PRIVATE_KEY"), reason="POLYMARKET_PRIVATE_KEY not set")
class TestPolymarketLive:
    @pytest.mark.asyncio
    async def test_initialize_and_balance(self, settings):
        from tradingbot.connectors.polymarket_connector import PolymarketConnector

        conn = PolymarketConnector(
            private_key=settings.polymarket.private_key,
            chain_id=settings.polymarket.chain_id,
            host=settings.polymarket.host,
        )
        await conn.initialize()
        balances = await conn.get_balance()
        assert isinstance(balances, list)
        await conn.close()

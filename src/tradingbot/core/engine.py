"""Trading engine — orchestrates connectors and strategies."""

import asyncio
import logging

from tradingbot.config.settings import AppSettings
from tradingbot.connectors.alpaca_connector import AlpacaConnector
from tradingbot.connectors.ccxt_connector import CCXTConnector
from tradingbot.connectors.polymarket_connector import PolymarketConnector
from tradingbot.core.base import BaseConnector, BaseStrategy
from tradingbot.core.exceptions import ConnectorError
from tradingbot.core.models import Balance, Position

logger = logging.getLogger(__name__)


class TradingEngine:
    """Central engine that manages connectors, strategies, and the main loop."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self.connectors: dict[str, BaseConnector] = {}
        self.strategies: list[BaseStrategy] = []
        self._tasks: list[asyncio.Task] = []  # type: ignore[type-arg]
        self._running = False

    async def initialize(self) -> None:
        """Create and initialize all enabled connectors."""
        s = self.settings

        if "ccxt" in s.enabled_connectors and s.ccxt.api_key:
            conn = CCXTConnector(
                exchange_id=s.ccxt.exchange,
                api_key=s.ccxt.api_key,
                api_secret=s.ccxt.api_secret,
                testnet=s.ccxt.testnet,
            )
            await self._init_connector(conn)

        if "alpaca" in s.enabled_connectors and s.alpaca.api_key:
            conn = AlpacaConnector(
                api_key=s.alpaca.api_key,
                api_secret=s.alpaca.api_secret,
                paper=s.alpaca.paper,
            )
            await self._init_connector(conn)

        if "polymarket" in s.enabled_connectors and s.polymarket.private_key:
            conn = PolymarketConnector(
                private_key=s.polymarket.private_key,
                chain_id=s.polymarket.chain_id,
                host=s.polymarket.host,
            )
            await self._init_connector(conn)

        logger.info("Engine initialized with connectors: %s", list(self.connectors.keys()))

    async def _init_connector(self, connector: BaseConnector) -> None:
        try:
            await connector.initialize()
            self.connectors[connector.name] = connector
        except ConnectorError as e:
            logger.error("Failed to initialize connector %s: %s", connector.name, e)

    def register_strategy(self, strategy: BaseStrategy) -> None:
        self.strategies.append(strategy)

    async def start(self) -> None:
        """Start the engine: initialize strategies and launch evaluation loops."""
        self._running = True

        for strategy in self.strategies:
            await strategy.initialize(self.connectors)
            task = asyncio.create_task(self._strategy_loop(strategy))
            self._tasks.append(task)

        logger.info("Engine started with %d strategies", len(self.strategies))

    async def _strategy_loop(self, strategy: BaseStrategy) -> None:
        """Run a strategy's evaluate() in a loop."""
        while self._running:
            try:
                signals = await strategy.evaluate()
                for signal in signals:
                    connector = self.connectors.get(signal.strategy_name)
                    if connector and not self.settings.dry_run:
                        await connector.place_order(
                            symbol=signal.symbol,
                            side=signal.side,
                            order_type=signal.order_type,
                            quantity=str(signal.quantity),
                            price=str(signal.price) if signal.price else None,
                        )
                        logger.info("Executed signal: %s %s %s", signal.side, signal.quantity, signal.symbol)
                    elif self.settings.dry_run and signals:
                        logger.info("[DRY RUN] Signal: %s %s %s", signal.side, signal.quantity, signal.symbol)
            except Exception:
                logger.exception("Error in strategy %s", strategy.name)
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop all strategies and close all connectors."""
        self._running = False

        for task in self._tasks:
            task.cancel()

        for strategy in self.strategies:
            try:
                await strategy.stop()
            except Exception:
                logger.exception("Error stopping strategy %s", strategy.name)

        for name, connector in self.connectors.items():
            try:
                await connector.close()
            except Exception:
                logger.exception("Error closing connector %s", name)

        self._tasks.clear()
        logger.info("Engine stopped")

    async def get_all_balances(self) -> dict[str, list[Balance]]:
        """Fetch balances from all connected exchanges."""
        result: dict[str, list[Balance]] = {}
        for name, connector in self.connectors.items():
            try:
                result[name] = await connector.get_balance()
            except ConnectorError as e:
                logger.error("Failed to get balance from %s: %s", name, e)
                result[name] = []
        return result

    async def get_all_positions(self) -> dict[str, list[Position]]:
        """Fetch positions from all connected exchanges."""
        result: dict[str, list[Position]] = {}
        for name, connector in self.connectors.items():
            try:
                result[name] = await connector.get_positions()
            except ConnectorError as e:
                logger.error("Failed to get positions from %s: %s", name, e)
                result[name] = []
        return result

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def connected_exchanges(self) -> list[str]:
        return list(self.connectors.keys())

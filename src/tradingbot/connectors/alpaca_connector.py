"""Alpaca connector for stock trading (sync client wrapped as async)."""

import logging
from decimal import Decimal

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import OrderStatus as AlpacaOrderStatus
from alpaca.trading.enums import TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from tradingbot.core.exceptions import ConnectorError, OrderError
from tradingbot.core.models import (
    Balance,
    Market,
    Order,
    OrderBook,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Ticker,
)
from tradingbot.utils.async_helpers import run_in_executor

logger = logging.getLogger(__name__)

_ALPACA_STATUS_MAP: dict[str, OrderStatus] = {
    "new": OrderStatus.OPEN,
    "accepted": OrderStatus.OPEN,
    "pending_new": OrderStatus.PENDING,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED,
    "done_for_day": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
    "replaced": OrderStatus.CANCELLED,
}


class AlpacaConnector:
    """Connector for Alpaca stock trading API."""

    name: str = "alpaca"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        paper: bool = True,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._paper = paper
        self._client: TradingClient | None = None

    @property
    def client(self) -> TradingClient:
        if self._client is None:
            raise ConnectorError(self.name, "Connector not initialized. Call initialize() first.")
        return self._client

    async def initialize(self) -> None:
        try:
            self._client = await run_in_executor(
                TradingClient, self._api_key, self._api_secret, paper=self._paper
            )
            logger.info("Alpaca connector initialized (paper=%s)", self._paper)
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to initialize: {e}") from e

    async def get_balance(self) -> list[Balance]:
        try:
            account = await run_in_executor(self.client.get_account)
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to fetch account: {e}") from e

        return [
            Balance(
                currency="USD",
                free=Decimal(str(account.cash)),
                used=Decimal(str(account.portfolio_value)) - Decimal(str(account.cash)),
                total=Decimal(str(account.portfolio_value)),
            )
        ]

    async def get_positions(self) -> list[Position]:
        try:
            positions = await run_in_executor(self.client.get_all_positions)
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to fetch positions: {e}") from e

        return [
            Position(
                symbol=p.symbol,
                quantity=Decimal(str(abs(float(p.qty)))),
                entry_price=Decimal(str(p.avg_entry_price)),
                current_price=Decimal(str(p.current_price)),
                unrealized_pnl=Decimal(str(p.unrealized_pl)),
                side=OrderSide.BUY if p.side == "long" else OrderSide.SELL,
                connector_name=self.name,
            )
            for p in positions
        ]

    async def get_markets(self) -> list[Market]:
        # Alpaca doesn't have a simple market listing — return empty for now.
        # A full implementation would use the assets API.
        return []

    async def get_ticker(self, symbol: str) -> Ticker:
        # Alpaca's market data requires a separate data client.
        # Return a basic ticker for now.
        return Ticker(symbol=symbol)

    async def get_orderbook(self, symbol: str) -> OrderBook:
        return OrderBook(symbol=symbol)

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float | str,
        price: float | str | None = None,
    ) -> Order:
        alpaca_side = AlpacaOrderSide.BUY if side == OrderSide.BUY else AlpacaOrderSide.SELL

        try:
            if order_type == OrderType.LIMIT:
                if price is None:
                    raise OrderError("Limit orders require a price")
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=float(quantity),
                    side=alpaca_side,
                    time_in_force=TimeInForce.GTC,
                    limit_price=float(price),
                )
            else:
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=float(quantity),
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )

            result = await run_in_executor(self.client.submit_order, request)
        except OrderError:
            raise
        except Exception as e:
            raise OrderError(f"Failed to place order on {self.name}: {e}") from e

        return self._map_order(result)

    async def cancel_order(self, order_id: str, symbol: str | None = None) -> bool:
        try:
            await run_in_executor(self.client.cancel_order_by_id, order_id)
            return True
        except Exception as e:
            raise OrderError(f"Failed to cancel order {order_id}: {e}", order_id=order_id) from e

    async def get_order(self, order_id: str, symbol: str | None = None) -> Order:
        try:
            result = await run_in_executor(self.client.get_order_by_id, order_id)
        except Exception as e:
            raise OrderError(f"Failed to fetch order {order_id}: {e}", order_id=order_id) from e
        return self._map_order(result)

    async def get_order_history(self, symbol: str | None = None) -> list[Order]:
        try:
            orders = await run_in_executor(self.client.get_orders)
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to fetch order history: {e}") from e
        return [self._map_order(o) for o in orders]

    async def close(self) -> None:
        self._client = None
        logger.info("Alpaca connector closed")

    def _map_order(self, order: object) -> Order:
        status_str = str(getattr(order, "status", "new")).lower()
        # Handle AlpacaOrderStatus enum
        if isinstance(order, object) and hasattr(order, "status"):
            if isinstance(order.status, AlpacaOrderStatus):
                status_str = order.status.value

        return Order(
            order_id=str(order.id),  # type: ignore[union-attr]
            symbol=str(order.symbol),  # type: ignore[union-attr]
            side=OrderSide.BUY if str(order.side).lower() == "buy" else OrderSide.SELL,  # type: ignore[union-attr]
            type=OrderType.LIMIT if str(order.type).lower() == "limit" else OrderType.MARKET,  # type: ignore[union-attr]
            quantity=Decimal(str(order.qty)),  # type: ignore[union-attr]
            price=Decimal(str(order.limit_price)) if getattr(order, "limit_price", None) else None,  # type: ignore[union-attr]
            filled_quantity=Decimal(str(order.filled_qty or 0)),  # type: ignore[union-attr]
            status=_ALPACA_STATUS_MAP.get(status_str, OrderStatus.OPEN),
            connector_name=self.name,
        )

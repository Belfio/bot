"""Polymarket connector for prediction markets (sync client wrapped as async)."""

import logging
from decimal import Decimal

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType as ClobOrderType

from tradingbot.core.exceptions import ConnectorError, OrderError
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
from tradingbot.utils.async_helpers import run_in_executor

logger = logging.getLogger(__name__)


class PolymarketConnector:
    """Connector for Polymarket prediction markets via CLOB API."""

    name: str = "polymarket"

    def __init__(
        self,
        private_key: str = "",
        chain_id: int = 137,
        host: str = "https://clob.polymarket.com",
    ) -> None:
        self._private_key = private_key
        self._chain_id = chain_id
        self._host = host
        self._client: ClobClient | None = None

    @property
    def client(self) -> ClobClient:
        if self._client is None:
            raise ConnectorError(self.name, "Connector not initialized. Call initialize() first.")
        return self._client

    async def initialize(self) -> None:
        try:
            self._client = ClobClient(
                self._host,
                key=self._private_key,
                chain_id=self._chain_id,
            )
            # Derive API credentials from the private key
            await run_in_executor(self._client.set_api_creds, self._client.create_or_derive_api_creds())
            logger.info("Polymarket connector initialized (chain_id=%d)", self._chain_id)
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to initialize: {e}") from e

    async def get_balance(self) -> list[Balance]:
        # Polymarket uses USDC on Polygon — balance is fetched from the CLOB API
        try:
            balance_data = await run_in_executor(self.client.get_balance_allowance)
            usdc_balance = Decimal(str(balance_data.get("balance", 0)))
            return [
                Balance(
                    currency="USDC",
                    free=usdc_balance,
                    used=Decimal(0),
                    total=usdc_balance,
                )
            ]
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to fetch balance: {e}") from e

    async def get_positions(self) -> list[Position]:
        # Polymarket positions are token holdings for specific market outcomes
        return []

    async def get_markets(self) -> list[Market]:
        try:
            markets_data = await run_in_executor(self.client.get_markets)
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to fetch markets: {e}") from e

        markets: list[Market] = []
        for m in markets_data:
            condition_id = m.get("condition_id", "")
            question = m.get("question", condition_id)
            markets.append(
                Market(
                    symbol=condition_id,
                    base_currency=question,
                    quote_currency="USDC",
                    min_order_size=Decimal("1"),
                    precision=2,
                    active=m.get("active", True),
                )
            )
        return markets

    async def get_ticker(self, symbol: str) -> Ticker:
        try:
            book = await run_in_executor(self.client.get_order_book, symbol)
            best_bid = Decimal(str(book.bids[0].price)) if book.bids else None
            best_ask = Decimal(str(book.asks[0].price)) if book.asks else None
            return Ticker(
                symbol=symbol,
                bid=best_bid,
                ask=best_ask,
                last=best_bid,  # CLOB doesn't provide a last price; use bid as proxy
            )
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to fetch ticker for {symbol}: {e}") from e

    async def get_orderbook(self, symbol: str) -> OrderBook:
        try:
            book = await run_in_executor(self.client.get_order_book, symbol)
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to fetch order book for {symbol}: {e}") from e

        return OrderBook(
            symbol=symbol,
            bids=[OrderBookEntry(price=Decimal(str(b.price)), quantity=Decimal(str(b.size))) for b in book.bids],
            asks=[OrderBookEntry(price=Decimal(str(a.price)), quantity=Decimal(str(a.size))) for a in book.asks],
        )

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float | str,
        price: float | str | None = None,
    ) -> Order:
        if price is None:
            raise OrderError("Polymarket requires a price for all orders")

        try:
            order_args = OrderArgs(
                price=float(price),
                size=float(quantity),
                side="BUY" if side == OrderSide.BUY else "SELL",
                token_id=symbol,
            )

            clob_type = ClobOrderType.GTC if order_type == OrderType.LIMIT else ClobOrderType.FOK
            signed_order = await run_in_executor(self.client.create_order, order_args, clob_type)
            result = await run_in_executor(self.client.post_order, signed_order)
        except OrderError:
            raise
        except Exception as e:
            raise OrderError(f"Failed to place order on {self.name}: {e}") from e

        order_id = result.get("orderID", result.get("id", "unknown"))
        return Order(
            order_id=str(order_id),
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(price)),
            status=OrderStatus.OPEN,
            connector_name=self.name,
            raw_data=result,
        )

    async def cancel_order(self, order_id: str, symbol: str | None = None) -> bool:
        try:
            await run_in_executor(self.client.cancel, order_id)
            return True
        except Exception as e:
            raise OrderError(f"Failed to cancel order {order_id}: {e}", order_id=order_id) from e

    async def get_order(self, order_id: str, symbol: str | None = None) -> Order:
        try:
            result = await run_in_executor(self.client.get_order, order_id)
        except Exception as e:
            raise OrderError(f"Failed to fetch order {order_id}: {e}", order_id=order_id) from e

        return Order(
            order_id=str(result.get("id", order_id)),
            symbol=result.get("asset_id", symbol or ""),
            side=OrderSide.BUY if result.get("side", "").upper() == "BUY" else OrderSide.SELL,
            type=OrderType.LIMIT,
            quantity=Decimal(str(result.get("original_size", 0))),
            price=Decimal(str(result.get("price", 0))),
            filled_quantity=Decimal(str(result.get("size_matched", 0))),
            status=OrderStatus.OPEN if result.get("status") == "live" else OrderStatus.FILLED,
            connector_name=self.name,
            raw_data=result,
        )

    async def get_order_history(self, symbol: str | None = None) -> list[Order]:
        try:
            orders = await run_in_executor(self.client.get_orders)
        except Exception as e:
            raise ConnectorError(self.name, f"Failed to fetch order history: {e}") from e
        return [
            Order(
                order_id=str(o.get("id", "")),
                symbol=o.get("asset_id", ""),
                side=OrderSide.BUY if o.get("side", "").upper() == "BUY" else OrderSide.SELL,
                type=OrderType.LIMIT,
                quantity=Decimal(str(o.get("original_size", 0))),
                price=Decimal(str(o.get("price", 0))),
                filled_quantity=Decimal(str(o.get("size_matched", 0))),
                status=OrderStatus.OPEN if o.get("status") == "live" else OrderStatus.FILLED,
                connector_name=self.name,
                raw_data=o,
            )
            for o in orders
        ]

    async def close(self) -> None:
        self._client = None
        logger.info("Polymarket connector closed")

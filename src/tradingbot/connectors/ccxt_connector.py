"""CCXT connector for cryptocurrency exchanges (native async)."""

import logging
from decimal import Decimal

import ccxt.async_support as ccxt_async

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

logger = logging.getLogger(__name__)

_CCXT_STATUS_MAP: dict[str, OrderStatus] = {
    "open": OrderStatus.OPEN,
    "closed": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "cancelled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
}


class CCXTConnector:
    """Connector for crypto exchanges via the ccxt async API."""

    name: str = "ccxt"

    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
    ) -> None:
        self._exchange_id = exchange_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._testnet = testnet
        self._exchange: ccxt_async.Exchange | None = None

    @property
    def exchange(self) -> ccxt_async.Exchange:
        if self._exchange is None:
            raise ConnectorError(self.name, "Connector not initialized. Call initialize() first.")
        return self._exchange

    async def initialize(self) -> None:
        exchange_class = getattr(ccxt_async, self._exchange_id, None)
        if exchange_class is None:
            raise ConnectorError(self.name, f"Unknown exchange: {self._exchange_id}")

        config: dict = {"enableRateLimit": True}
        if self._api_key:
            config["apiKey"] = self._api_key
            config["secret"] = self._api_secret

        self._exchange = exchange_class(config)

        if self._testnet and hasattr(self._exchange, "set_sandbox_mode"):
            self._exchange.set_sandbox_mode(True)

        try:
            await self._exchange.load_markets()
            logger.info("CCXT connector initialized: %s (testnet=%s)", self._exchange_id, self._testnet)
        except ccxt_async.BaseError as e:
            raise ConnectorError(self.name, f"Failed to load markets: {e}") from e

    async def get_balance(self) -> list[Balance]:
        try:
            data = await self.exchange.fetch_balance()
        except ccxt_async.BaseError as e:
            raise ConnectorError(self.name, f"Failed to fetch balance: {e}") from e

        balances: list[Balance] = []
        for currency, info in data.get("total", {}).items():
            if info and float(info) > 0:
                free = data.get("free", {}).get(currency, 0)
                used = data.get("used", {}).get(currency, 0)
                balances.append(
                    Balance(
                        currency=currency,
                        free=Decimal(str(free or 0)),
                        used=Decimal(str(used or 0)),
                        total=Decimal(str(info)),
                    )
                )
        return balances

    async def get_positions(self) -> list[Position]:
        try:
            positions_data = await self.exchange.fetch_positions()
        except (ccxt_async.BaseError, NotImplementedError):
            return []

        positions: list[Position] = []
        for p in positions_data:
            contracts = float(p.get("contracts", 0) or 0)
            if contracts == 0:
                continue
            positions.append(
                Position(
                    symbol=p["symbol"],
                    quantity=Decimal(str(abs(contracts))),
                    entry_price=Decimal(str(p.get("entryPrice", 0) or 0)),
                    current_price=Decimal(str(p.get("markPrice", 0) or 0)),
                    unrealized_pnl=Decimal(str(p.get("unrealizedPnl", 0) or 0)),
                    side=OrderSide.BUY if p.get("side") == "long" else OrderSide.SELL,
                    connector_name=self.name,
                )
            )
        return positions

    async def get_markets(self) -> list[Market]:
        markets: list[Market] = []
        for symbol, m in self.exchange.markets.items():
            markets.append(
                Market(
                    symbol=symbol,
                    base_currency=m.get("base", ""),
                    quote_currency=m.get("quote", ""),
                    min_order_size=Decimal(str(m.get("limits", {}).get("amount", {}).get("min", 0) or 0)),
                    precision=m.get("precision", {}).get("amount", 8) or 8,
                    active=m.get("active", True),
                )
            )
        return markets

    async def get_ticker(self, symbol: str) -> Ticker:
        try:
            data = await self.exchange.fetch_ticker(symbol)
        except ccxt_async.BaseError as e:
            raise ConnectorError(self.name, f"Failed to fetch ticker for {symbol}: {e}") from e

        return Ticker(
            symbol=symbol,
            bid=Decimal(str(data["bid"])) if data.get("bid") else None,
            ask=Decimal(str(data["ask"])) if data.get("ask") else None,
            last=Decimal(str(data["last"])) if data.get("last") else None,
            volume_24h=Decimal(str(data["quoteVolume"])) if data.get("quoteVolume") else None,
        )

    async def get_orderbook(self, symbol: str) -> OrderBook:
        try:
            data = await self.exchange.fetch_order_book(symbol)
        except ccxt_async.BaseError as e:
            raise ConnectorError(self.name, f"Failed to fetch order book for {symbol}: {e}") from e

        return OrderBook(
            symbol=symbol,
            bids=[OrderBookEntry(price=Decimal(str(p)), quantity=Decimal(str(q))) for p, q in data.get("bids", [])],
            asks=[OrderBookEntry(price=Decimal(str(p)), quantity=Decimal(str(q))) for p, q in data.get("asks", [])],
        )

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float | str,
        price: float | str | None = None,
    ) -> Order:
        try:
            result = await self.exchange.create_order(
                symbol=symbol,
                type=str(order_type),
                side=str(side),
                amount=float(quantity),
                price=float(price) if price is not None else None,
            )
        except ccxt_async.BaseError as e:
            raise OrderError(f"Failed to place order on {self.name}: {e}") from e

        return self._map_order(result)

    async def cancel_order(self, order_id: str, symbol: str | None = None) -> bool:
        try:
            await self.exchange.cancel_order(order_id, symbol)
            return True
        except ccxt_async.BaseError as e:
            raise OrderError(f"Failed to cancel order {order_id}: {e}", order_id=order_id) from e

    async def get_order(self, order_id: str, symbol: str | None = None) -> Order:
        try:
            result = await self.exchange.fetch_order(order_id, symbol)
        except ccxt_async.BaseError as e:
            raise OrderError(f"Failed to fetch order {order_id}: {e}", order_id=order_id) from e
        return self._map_order(result)

    async def get_order_history(self, symbol: str | None = None) -> list[Order]:
        try:
            orders = await self.exchange.fetch_orders(symbol)
        except ccxt_async.BaseError as e:
            raise ConnectorError(self.name, f"Failed to fetch order history: {e}") from e
        return [self._map_order(o) for o in orders]

    async def close(self) -> None:
        if self._exchange is not None:
            await self._exchange.close()
            self._exchange = None
            logger.info("CCXT connector closed")

    def _map_order(self, data: dict) -> Order:
        status_str = data.get("status", "open")
        filled = float(data.get("filled", 0) or 0)
        amount = float(data.get("amount", 0) or 0)

        if status_str == "open" and filled > 0 and filled < amount:
            status = OrderStatus.PARTIALLY_FILLED
        else:
            status = _CCXT_STATUS_MAP.get(status_str, OrderStatus.OPEN)

        return Order(
            order_id=str(data["id"]),
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            type=OrderType(data["type"]) if data.get("type") in ("market", "limit") else OrderType.MARKET,
            quantity=Decimal(str(amount)),
            price=Decimal(str(data["price"])) if data.get("price") else None,
            filled_quantity=Decimal(str(filled)),
            status=status,
            connector_name=self.name,
            raw_data=data,
        )

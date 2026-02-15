"""Core data models for the trading bot."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Balance(BaseModel):
    currency: str
    free: Decimal = Decimal(0)
    used: Decimal = Decimal(0)
    total: Decimal = Decimal(0)


class Position(BaseModel):
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)
    side: OrderSide
    connector_name: str = ""


class Order(BaseModel):
    order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    filled_quantity: Decimal = Decimal(0)
    status: OrderStatus = OrderStatus.PENDING
    connector_name: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_data: dict | None = None


class Market(BaseModel):
    symbol: str
    base_currency: str
    quote_currency: str
    min_order_size: Decimal = Decimal(0)
    precision: int = 8
    active: bool = True


class Ticker(BaseModel):
    symbol: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal | None = None
    volume_24h: Decimal | None = None


class OrderBookEntry(BaseModel):
    price: Decimal
    quantity: Decimal


class OrderBook(BaseModel):
    symbol: str
    bids: list[OrderBookEntry] = []
    asks: list[OrderBookEntry] = []


class Signal(BaseModel):
    strategy_name: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    order_type: OrderType = OrderType.MARKET
    price: Decimal | None = None
    reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

# Trading Bot

A multi-exchange trading bot that connects to crypto exchanges, stock brokers, and prediction markets through a unified async interface. Built for local execution on macOS with a CLI and real-time web dashboard.

## Supported Exchanges

| Connector | Library | Markets | Auth |
|-----------|---------|---------|------|
| **CCXT** | `ccxt` (async) | Binance, Coinbase, Kraken, 100+ crypto exchanges | API key + secret |
| **Alpaca** | `alpaca-py` (sync→async) | US stocks, ETFs | API key + secret |
| **Polymarket** | `py-clob-client` (sync→async) | Prediction markets | Ethereum private key |

## Architecture

```
CLI (Click) ─────► Trading Engine ◄────── Web Dashboard (FastAPI)
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   CCXTConnector   AlpacaConnector  PolymarketConnector
   (async native)  (sync→async)    (sync→async)
```

All connectors implement a unified `BaseConnector` protocol with async methods for balances, positions, orders, and market data. Sync libraries (Alpaca, Polymarket) are wrapped with `asyncio.run_in_executor()` to avoid blocking the event loop.

The `TradingEngine` orchestrates connector lifecycle and aggregates data across exchanges. Strategies can be plugged in by implementing the `BaseStrategy` protocol — the engine runs each strategy's `evaluate()` in its own async task.

## Setup

```bash
# Clone and install
git clone https://github.com/Belfio/bot.git
cd bot
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure API keys
cp .env.example .env
# Edit .env with your credentials
```

### Environment Variables

```bash
# Crypto (pick any ccxt-supported exchange)
CCXT_EXCHANGE=binance
CCXT_API_KEY=your_key
CCXT_API_SECRET=your_secret
CCXT_TESTNET=true

# Stocks
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
ALPACA_PAPER=true

# Prediction Markets
POLYMARKET_PRIVATE_KEY=your_eth_private_key
```

## Usage

### CLI

```bash
# Check configuration and connector status
tradingbot status

# View balances across all connected exchanges
tradingbot balance

# View open positions
tradingbot positions

# Place a manual trade
tradingbot trade BTC/USDT buy 0.001 --price 50000 --exchange ccxt

# Start the engine with web dashboard
tradingbot start --web

# Start without web dashboard
tradingbot start --no-web
```

### Web Dashboard

Start with `tradingbot start --web` and open `http://127.0.0.1:8000`. The dashboard shows:

- **Status** — engine state, connected exchanges, dry run mode
- **Connectors** — live connection indicators
- **Balances** — aggregated across all exchanges
- **Positions** — open positions with unrealized PnL
- **Activity log** — connection events and updates

Data updates via WebSocket every 5 seconds, with a REST polling fallback.

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Engine state, connected exchanges |
| `GET /api/balances` | All balances as JSON |
| `GET /api/positions` | All positions as JSON |
| `WebSocket /ws` | Live balance/position updates |

## Configuration

Bot settings are in `config/default.toml`:

```toml
[bot]
dry_run = true          # Set false to execute real trades

[risk]
max_position_size = 1000.0
max_order_value = 500.0
max_daily_loss = 100.0

[connectors]
enabled = ["ccxt", "alpaca", "polymarket"]
```

## Project Structure

```
src/tradingbot/
├── cli/commands.py          # Click CLI (start, balance, positions, status, trade)
├── config/
│   ├── settings.py          # Pydantic settings from .env
│   └── loader.py            # TOML config loader with deep merge
├── connectors/
│   ├── ccxt_connector.py    # Crypto exchanges (native async)
│   ├── alpaca_connector.py  # Stock trading (sync→async)
│   └── polymarket_connector.py  # Prediction markets (sync→async)
├── core/
│   ├── base.py              # BaseConnector and BaseStrategy protocols
│   ├── engine.py            # Trading engine orchestrator
│   ├── exceptions.py        # ConnectorError, OrderError, ConfigError
│   └── models.py            # Pydantic models (Order, Balance, Position, etc.)
├── utils/async_helpers.py   # run_in_executor for sync→async wrapping
└── web/
    ├── app.py               # FastAPI with REST + WebSocket
    └── static/              # Dashboard HTML + JS
```

## Tests

```bash
# Unit tests
pytest tests/unit -v

# All tests (integration tests require API credentials)
pytest tests/ -v
```

## Adding a Strategy

Implement the `BaseStrategy` protocol and register it with the engine:

```python
from tradingbot.core.base import BaseConnector, BaseStrategy
from tradingbot.core.models import Order, Position, Signal, OrderSide, OrderType
from decimal import Decimal

class MyStrategy:
    name = "my_strategy"

    async def initialize(self, connectors: dict[str, BaseConnector]) -> None:
        self.connectors = connectors

    async def evaluate(self) -> list[Signal]:
        # Your logic here
        return [Signal(
            strategy_name="ccxt",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.001"),
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
            confidence=0.9,
        )]

    async def on_tick(self) -> None: pass
    async def on_order_fill(self, order: Order) -> None: pass
    async def on_position_change(self, position: Position) -> None: pass
    async def stop(self) -> None: pass
```

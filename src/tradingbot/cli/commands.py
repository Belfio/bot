"""CLI commands for the trading bot."""

import asyncio
import logging
import sys

import click

from tradingbot.config.settings import AppSettings
from tradingbot.core.engine import TradingEngine


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine in a new event loop."""
    return asyncio.run(coro)


@click.group()
@click.option("--log-level", default=None, help="Log level (DEBUG, INFO, WARNING, ERROR)")
@click.pass_context
def cli(ctx: click.Context, log_level: str | None) -> None:
    """Multi-exchange trading bot for crypto, stocks, and prediction markets."""
    ctx.ensure_object(dict)
    settings = AppSettings()
    if log_level:
        settings.log_level = log_level
    _setup_logging(settings.log_level)
    ctx.obj["settings"] = settings


@cli.command()
@click.option("--web/--no-web", default=True, help="Enable/disable web dashboard")
@click.pass_context
def start(ctx: click.Context, web: bool) -> None:
    """Start the trading engine."""
    settings: AppSettings = ctx.obj["settings"]

    async def _start() -> None:
        engine = TradingEngine(settings)
        await engine.initialize()

        if web:
            import uvicorn

            from tradingbot.web.app import create_app

            app = create_app(engine)
            config = uvicorn.Config(
                app,
                host=settings.web_host,
                port=settings.web_port,
                log_level=settings.log_level.lower(),
            )
            server = uvicorn.Server(config)

            try:
                await asyncio.gather(engine.start(), server.serve())
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await engine.stop()
        else:
            await engine.start()
            click.echo("Engine running. Press Ctrl+C to stop.")
            try:
                while engine.is_running:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                await engine.stop()

    _run(_start())


@cli.command()
@click.pass_context
def balance(ctx: click.Context) -> None:
    """Show balances across all connected exchanges."""
    settings: AppSettings = ctx.obj["settings"]

    async def _balance() -> None:
        engine = TradingEngine(settings)
        await engine.initialize()

        if not engine.connectors:
            click.echo("No connectors available. Check your API keys in .env")
            return

        balances = await engine.get_all_balances()
        for exchange, items in balances.items():
            click.echo(f"\n{'─' * 40}")
            click.echo(f"  {exchange.upper()}")
            click.echo(f"{'─' * 40}")
            if not items:
                click.echo("  No balances")
            for b in items:
                click.echo(f"  {b.currency:>8}  free={b.free:<14}  used={b.used:<14}  total={b.total}")

        for connector in engine.connectors.values():
            await connector.close()

    _run(_balance())


@cli.command()
@click.pass_context
def positions(ctx: click.Context) -> None:
    """Show open positions across all connected exchanges."""
    settings: AppSettings = ctx.obj["settings"]

    async def _positions() -> None:
        engine = TradingEngine(settings)
        await engine.initialize()

        if not engine.connectors:
            click.echo("No connectors available. Check your API keys in .env")
            return

        all_positions = await engine.get_all_positions()
        for exchange, items in all_positions.items():
            click.echo(f"\n{'─' * 50}")
            click.echo(f"  {exchange.upper()}")
            click.echo(f"{'─' * 50}")
            if not items:
                click.echo("  No open positions")
            for p in items:
                click.echo(
                    f"  {p.symbol:>12}  {p.side.value:>4}  qty={p.quantity:<10}  "
                    f"entry={p.entry_price:<12}  pnl={p.unrealized_pnl}"
                )

        for connector in engine.connectors.values():
            await connector.close()

    _run(_positions())


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show bot configuration and connector status."""
    settings: AppSettings = ctx.obj["settings"]

    click.echo(f"\n{'═' * 40}")
    click.echo("  Trading Bot Status")
    click.echo(f"{'═' * 40}")
    click.echo(f"  Enabled connectors: {', '.join(settings.enabled_connectors)}")
    click.echo(f"  Dry run:            {settings.dry_run}")
    click.echo(f"  Log level:          {settings.log_level}")
    click.echo(f"  Web dashboard:      {settings.web_host}:{settings.web_port}")
    click.echo()

    connectors_info = {
        "ccxt": f"{settings.ccxt.exchange} (testnet={settings.ccxt.testnet})"
        if settings.ccxt.api_key
        else "not configured",
        "alpaca": f"paper={settings.alpaca.paper}" if settings.alpaca.api_key else "not configured",
        "polymarket": f"chain_id={settings.polymarket.chain_id}"
        if settings.polymarket.private_key
        else "not configured",
    }

    for name in settings.enabled_connectors:
        info = connectors_info.get(name, "unknown")
        configured = "not configured" not in info
        marker = "+" if configured else "-"
        click.echo(f"  [{marker}] {name}: {info}")

    click.echo()


@cli.command()
@click.argument("symbol")
@click.argument("side", type=click.Choice(["buy", "sell"]))
@click.argument("qty", type=float)
@click.option("--price", type=float, default=None, help="Limit price (omit for market order)")
@click.option("--exchange", default=None, help="Target exchange connector name")
@click.pass_context
def trade(ctx: click.Context, symbol: str, side: str, qty: float, price: float | None, exchange: str | None) -> None:
    """Place a manual trade."""
    settings: AppSettings = ctx.obj["settings"]

    async def _trade() -> None:
        from tradingbot.core.models import OrderSide, OrderType

        engine = TradingEngine(settings)
        await engine.initialize()

        if not engine.connectors:
            click.echo("No connectors available. Check your API keys in .env")
            return

        target = exchange or next(iter(engine.connectors))
        connector = engine.connectors.get(target)
        if connector is None:
            click.echo(f"Connector '{target}' not found. Available: {list(engine.connectors.keys())}")
            return

        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        order_type = OrderType.LIMIT if price else OrderType.MARKET

        click.echo(f"Placing {order_type.value} {side} order: {qty} {symbol} on {target}")
        if settings.dry_run:
            click.echo("[DRY RUN] Order not submitted. Set dry_run=false in config to execute.")
            return

        try:
            order = await connector.place_order(symbol, order_side, order_type, qty, price)
            click.echo(f"Order placed: id={order.order_id} status={order.status.value}")
        except Exception as e:
            click.echo(f"Order failed: {e}")
        finally:
            for c in engine.connectors.values():
                await c.close()

    _run(_trade())

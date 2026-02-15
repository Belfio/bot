"""FastAPI web dashboard for the trading bot."""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tradingbot.core.engine import TradingEngine

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def _serialize_decimal(obj: object) -> str:
    """JSON serializer for Decimal and other non-standard types."""
    return str(obj)


def create_app(engine: TradingEngine) -> FastAPI:
    """Create the FastAPI application with routes bound to the engine."""
    app = FastAPI(title="Trading Bot Dashboard")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/status")
    async def api_status() -> dict:
        return {
            "running": engine.is_running,
            "connected_exchanges": engine.connected_exchanges,
            "dry_run": engine.settings.dry_run,
            "strategies": [s.name for s in engine.strategies],
        }

    @app.get("/api/balances")
    async def api_balances() -> dict:
        balances = await engine.get_all_balances()
        return {
            exchange: [b.model_dump(mode="json") for b in items]
            for exchange, items in balances.items()
        }

    @app.get("/api/positions")
    async def api_positions() -> dict:
        positions = await engine.get_all_positions()
        return {
            exchange: [p.model_dump(mode="json") for p in items]
            for exchange, items in positions.items()
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                balances = await engine.get_all_balances()
                positions = await engine.get_all_positions()
                payload = {
                    "type": "update",
                    "balances": {
                        exchange: [b.model_dump(mode="json") for b in items]
                        for exchange, items in balances.items()
                    },
                    "positions": {
                        exchange: [p.model_dump(mode="json") for p in items]
                        for exchange, items in positions.items()
                    },
                    "status": {
                        "running": engine.is_running,
                        "connected_exchanges": engine.connected_exchanges,
                    },
                }
                await websocket.send_text(json.dumps(payload, default=_serialize_decimal))
                await asyncio.sleep(5)
        except WebSocketDisconnect:
            logger.debug("WebSocket client disconnected")
        except Exception:
            logger.exception("WebSocket error")

    return app

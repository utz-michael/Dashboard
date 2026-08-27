import asyncio
import json
import logging
import pathlib

from aiohttp import web, WSMsgType

from dashboard_state import DashboardState
from n2k_udp import start_udp_listener

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

UDP_PORT = 1457
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080
BROADCAST_HZ = 5  # wie oft der Browser aktualisiert wird

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

state = DashboardState()
ws_clients: set[web.WebSocketResponse] = set()


async def index(request):
    return web.FileResponse(FRONTEND_DIR / "templates" / "index.html")


async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    ws_clients.add(ws)
    log.info("Client verbunden (%d aktiv)", len(ws_clients))
    try:
        # Sofort den aktuellen Stand senden
        await ws.send_str(json.dumps(state.snapshot()))
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
    finally:
        ws_clients.discard(ws)
        log.info("Client getrennt (%d aktiv)", len(ws_clients))
    return ws


async def broadcaster():
    interval = 1.0 / BROADCAST_HZ
    while True:
        await asyncio.sleep(interval)
        if not ws_clients:
            continue
        payload = json.dumps(state.snapshot())
        dead = []
        for ws in ws_clients:
            try:
                await ws.send_str(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            ws_clients.discard(ws)


async def on_startup(app):
    app["udp_transport"] = await start_udp_listener(state, UDP_PORT)
    app["broadcaster_task"] = asyncio.create_task(broadcaster())
    log.info("NMEA2000 UDP-Listener auf Port %d gestartet", UDP_PORT)


async def on_cleanup(app):
    app["broadcaster_task"].cancel()
    app["udp_transport"].close()


def create_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_static("/static/", FRONTEND_DIR / "static", name="static")
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host=HTTP_HOST, port=HTTP_PORT)

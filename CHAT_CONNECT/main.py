"""CHAT CONNECT - unified Twitch + YouTube live chat hub for OBS.

Runs a small local web server that:
  * serves a control dashboard   ->  http://localhost:2428/
  * serves a clean OBS overlay   ->  http://localhost:2428/overlay
  * streams every chat message to any program that wants it:
        WebSocket  ws://localhost:2428/ws
        SSE        http://localhost:2428/events
        REST       http://localhost:2428/api/messages?since=<id>

Start it with run.bat (window) or run_background.bat (no window).
Full beginner guide: SETUP_GUIDE.md
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import webbrowser

from aiohttp import web, WSMsgType

from hub import ChatHub
from twitch_chat import TwitchChat
from youtube_chat import make_youtube_source

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(SCRIPT_DIR, "web")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

DEFAULT_PORT = 2428  # "CHAT" on a phone keypad

# Overlay style, editable in the visual editor (http://localhost:2428/editor).
# Saved here so OBS always shows the look you designed, no URL params needed.
DEFAULT_OVERLAY = {
    "size": 18,            # font size in px
    "fade": 0,             # seconds a message stays visible (0 = forever)
    "max": 12,             # messages kept on screen
    "name_max": 0,         # truncate usernames to N chars (0 = full name)
    "window_bg": False,    # dark panel behind the whole overlay
    "window_bg_opacity": 40,
    "msg_bg": False,       # dark bubble behind each message
    "msg_bg_opacity": 35,
    "show_platform": True, # Twitch / YouTube logo in front of each message
    "show_time": False,    # HH:MM in front of each message
    "delay": 0,            # seconds to hold messages back (sync with the Duck TTS)
    "align": "bottom",     # "bottom" | "top" (where new messages appear)
    "shadow": True,        # text drop shadow
}

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": DEFAULT_PORT,
    "twitch": {"channel": "", "autoconnect": False},
    "youtube": {"target": "", "api_key": "", "autoconnect": False},
    "overlay": dict(DEFAULT_OVERLAY),
    "log_chat_to_file": False,
}


def clean_overlay_config(raw: dict, base: dict) -> dict:
    """Merge raw values over base, keeping only known keys with sane types."""
    out = dict(base)
    for key, default in DEFAULT_OVERLAY.items():
        if key not in raw:
            continue
        value = raw[key]
        try:
            if isinstance(default, bool):
                out[key] = bool(value)
            elif isinstance(default, int):
                out[key] = max(0, min(int(value), 600))
            else:
                out[key] = str(value)
        except (TypeError, ValueError):
            pass
    out["size"] = max(8, min(out["size"], 80))
    out["max"] = max(1, min(out["max"], 60))
    out["window_bg_opacity"] = min(out["window_bg_opacity"], 100)
    out["msg_bg_opacity"] = min(out["msg_bg_opacity"], 100)
    if out["align"] not in ("bottom", "top"):
        out["align"] = "bottom"
    return out

log = logging.getLogger("chatconnect")


# ----------------------------------------------------------------------- config

def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for key, value in saved.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        log.warning("config.json unreadable (%s), using defaults", e)
    return cfg


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        log.warning("could not save config.json: %s", e)


# -------------------------------------------------------------- source manager

class Sources:
    """Owns the running Twitch / YouTube reader tasks."""

    def __init__(self, hub: ChatHub, cfg: dict):
        self.hub = hub
        self.cfg = cfg
        self.tasks: dict[str, asyncio.Task] = {}

    async def connect_twitch(self, channel: str):
        channel = channel.lstrip("#@ ").strip().lower()
        if not channel:
            raise ValueError("channel name is empty")
        await self.disconnect("twitch")
        self.cfg["twitch"].update({"channel": channel, "autoconnect": True})
        save_config(self.cfg)
        source = TwitchChat(channel, self.hub)
        self.tasks["twitch"] = asyncio.create_task(source.run(), name="twitch-chat")

    async def connect_youtube(self, target: str, api_key: str | None = None):
        target = target.strip()
        if not target:
            raise ValueError("channel / video is empty")
        await self.disconnect("youtube")
        if api_key is None:
            api_key = self.cfg["youtube"].get("api_key", "")
        self.cfg["youtube"].update({"target": target, "api_key": api_key,
                                    "autoconnect": True})
        save_config(self.cfg)
        source = make_youtube_source(target, self.hub, api_key)
        self.tasks["youtube"] = asyncio.create_task(source.run(), name="youtube-chat")

    async def disconnect(self, platform: str, forget: bool = False):
        task = self.tasks.pop(platform, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if forget:
            self.cfg[platform]["autoconnect"] = False
            save_config(self.cfg)

    async def autoconnect(self):
        if self.cfg["twitch"]["autoconnect"] and self.cfg["twitch"]["channel"]:
            await self.connect_twitch(self.cfg["twitch"]["channel"])
        if self.cfg["youtube"]["autoconnect"] and self.cfg["youtube"]["target"]:
            await self.connect_youtube(self.cfg["youtube"]["target"])

    async def shutdown(self):
        for platform in list(self.tasks):
            await self.disconnect(platform)


# ------------------------------------------------------------------ web server

def no_cache(response: web.StreamResponse) -> web.StreamResponse:
    response.headers["Cache-Control"] = "no-store"
    return response


def make_app(hub: ChatHub, sources: Sources, stop_event: asyncio.Event) -> web.Application:
    app = web.Application()

    async def page(name):
        return no_cache(web.FileResponse(os.path.join(WEB_DIR, name)))

    async def index(_):
        return await page("index.html")

    async def overlay(_):
        return await page("overlay.html")

    async def editor(_):
        return await page("editor.html")

    # ------------------------------------------------------------- streaming

    async def websocket(request):
        ws = web.WebSocketResponse(heartbeat=25)
        await ws.prepare(request)
        queue = hub.subscribe()
        log.info("ws client connected (%s)", request.remote)
        try:
            await ws.send_json(hub.hello_payload())
            sender = asyncio.create_task(_ws_sender(ws, queue))
            async for msg in ws:  # drain incoming frames until the client leaves
                if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                    break
            sender.cancel()
        finally:
            hub.unsubscribe(queue)
            log.info("ws client left (%s)", request.remote)
        return ws

    async def _ws_sender(ws, queue):
        try:
            while True:
                event = await queue.get()
                await ws.send_json(event)
        except (asyncio.CancelledError, ConnectionError, RuntimeError):
            pass

    async def sse(request):
        resp = web.StreamResponse(headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
        })
        await resp.prepare(request)
        queue = hub.subscribe()

        async def send(event: dict):
            payload = f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
            await resp.write(payload.encode("utf-8"))

        try:
            await send(hub.hello_payload())
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                except asyncio.TimeoutError:
                    await resp.write(b": keep-alive\n\n")
                    continue
                await send(event)
        except (ConnectionResetError, ConnectionError, asyncio.CancelledError):
            pass
        finally:
            hub.unsubscribe(queue)
        return resp

    # ------------------------------------------------------------------- API

    async def api_status(_):
        return no_cache(web.json_response({
            "status": hub.status,
            "history_size": len(hub.history),
            "endpoints": {
                "websocket": "/ws", "sse": "/events",
                "messages": "/api/messages?since=0", "overlay": "/overlay",
            },
        }))

    async def api_messages(request):
        try:
            since = int(request.query.get("since", 0))
            limit = min(int(request.query.get("limit", 100)), 300)
        except ValueError:
            raise web.HTTPBadRequest(text="since/limit must be integers")
        msgs = hub.messages_since(since, limit)
        return no_cache(web.json_response({
            "messages": msgs,
            "last_id": msgs[-1]["id"] if msgs else since,
        }))

    async def api_connect(request):
        body = await request.json()
        platform = body.get("platform")
        try:
            if platform == "twitch":
                await sources.connect_twitch(body.get("channel", ""))
            elif platform == "youtube":
                await sources.connect_youtube(body.get("target", ""),
                                              body.get("api_key"))
            else:
                raise ValueError("platform must be 'twitch' or 'youtube'")
        except ValueError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        return web.json_response({"ok": True})

    async def api_disconnect(request):
        body = await request.json()
        platform = body.get("platform")
        if platform not in ("twitch", "youtube"):
            return web.json_response({"ok": False, "error": "bad platform"}, status=400)
        await sources.disconnect(platform, forget=True)
        return web.json_response({"ok": True})

    async def api_test_message(request):
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        hub.publish_chat(
            platform=body.get("platform", "test"),
            author=body.get("author", "ChatConnect"),
            message=body.get("message", "Test message - if you see this, it works!"),
            badges=["moderator"],
        )
        return web.json_response({"ok": True})

    async def api_overlay_get(_):
        return no_cache(web.json_response({"ok": True, "overlay": hub.overlay_config}))

    async def api_overlay_set(request):
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"ok": False, "error": "bad JSON"}, status=400)
        cfg = clean_overlay_config(body, hub.overlay_config or DEFAULT_OVERLAY)
        sources.cfg["overlay"] = cfg
        save_config(sources.cfg)
        hub.publish_overlay_config(cfg)   # live overlays restyle instantly
        log.info("overlay style saved: %s", cfg)
        return web.json_response({"ok": True, "overlay": cfg})

    async def api_clear(_):
        hub.clear()
        return web.json_response({"ok": True})

    async def api_shutdown(_):
        log.info("shutdown requested via API")
        asyncio.get_running_loop().call_later(0.2, stop_event.set)
        return web.json_response({"ok": True, "bye": True})

    app.router.add_get("/", index)
    app.router.add_get("/overlay", overlay)
    app.router.add_get("/editor", editor)
    app.router.add_get("/ws", websocket)
    app.router.add_get("/events", sse)
    app.router.add_get("/api/status", api_status)
    app.router.add_get("/api/messages", api_messages)
    app.router.add_get("/api/overlay", api_overlay_get)
    app.router.add_post("/api/overlay", api_overlay_set)
    app.router.add_post("/api/connect", api_connect)
    app.router.add_post("/api/disconnect", api_disconnect)
    app.router.add_post("/api/test", api_test_message)
    app.router.add_post("/api/clear", api_clear)
    app.router.add_post("/api/shutdown", api_shutdown)
    return app


# ------------------------------------------------------------------------ main

def setup_logging(log_file: str | None):
    handlers = []
    if sys.stdout is not None:  # pythonw.exe has no console
        handlers.append(logging.StreamHandler(sys.stdout))
    if log_file or sys.stdout is None:
        path = log_file or os.path.join(SCRIPT_DIR, "server.log")
        handlers.append(logging.FileHandler(path, mode="w", encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


async def async_main(args) -> int:
    cfg = load_config()
    host = args.host or cfg.get("host", "127.0.0.1")
    port = args.port or int(cfg.get("port", DEFAULT_PORT))
    cfg["host"], cfg["port"] = host, port

    hub = ChatHub()
    hub.overlay_config = clean_overlay_config(cfg.get("overlay") or {}, DEFAULT_OVERLAY)
    cfg["overlay"] = hub.overlay_config
    if cfg.get("log_chat_to_file"):
        hub.log_path = os.path.join(SCRIPT_DIR, "chat_log.jsonl")

    stop_event = asyncio.Event()
    sources = Sources(hub, cfg)
    app = make_app(hub, sources, stop_event)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    try:
        await site.start()
    except OSError as e:
        log.error("Could not open http://%s:%s - %s", host, port, e)
        log.error("Is CHAT CONNECT already running? (dashboard: http://localhost:%s)", port)
        return 1

    save_config(cfg)
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    log.info("=" * 56)
    log.info("  CHAT CONNECT is running")
    log.info("  Dashboard : %s", url)
    log.info("  Overlay   : %s/overlay   (OBS browser source)", url)
    log.info("  Stream    : ws://localhost:%s/ws", port)
    log.info("=" * 56)

    if args.open:
        webbrowser.open(url)

    await sources.autoconnect()
    try:
        await stop_event.wait()          # runs until Ctrl+C or /api/shutdown
    finally:
        log.info("shutting down...")
        await sources.shutdown()
        await runner.cleanup()
    return 0


def main():
    parser = argparse.ArgumentParser(description="CHAT CONNECT - Twitch + YouTube chat hub")
    parser.add_argument("--host", default=None, help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help=f"port (default {DEFAULT_PORT})")
    parser.add_argument("--open", action="store_true", help="open the dashboard in a browser")
    parser.add_argument("--log-file", default=None, help="also write logs to this file")
    args = parser.parse_args()

    setup_logging(args.log_file)
    try:
        sys.exit(asyncio.run(async_main(args)))
    except KeyboardInterrupt:
        print("\nCHAT CONNECT stopped.")


if __name__ == "__main__":
    main()

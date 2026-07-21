"""Central message hub for CHAT CONNECT.

Every chat source (Twitch, YouTube) publishes unified messages here and the hub
fans them out to every subscriber (dashboard, OBS overlay, WebSocket/SSE
consumers like the Duck TTS).

Unified message format (what every consumer receives):
{
    "id":            42,                  # incrementing id, unique per server run
    "platform":      "twitch",            # "twitch" | "youtube" | "test"
    "author":        "French_five",       # display name
    "author_id":     "12345",             # platform user/channel id ("" if unknown)
    "message":       "Kappa hello chat",  # original text (emote codes kept)
    "message_clean": "hello chat",        # text with emote codes stripped (good for TTS)
    "color":         "#8A2BE2",           # author color (Twitch color or assigned)
    "badges":        ["moderator"],       # broadcaster / moderator / vip / subscriber / member / verified
    "emotes":        [{"text": "Kappa", "url": "https://..."}],  # for rendering images
    "amount":        "$5.00",             # only present for YouTube Super Chats
    "timestamp":     1712345678.901       # unix epoch seconds
}

Events pushed to subscribers are envelopes: {"type": "chat"|"status", "data": {...}}
"""

import asyncio
import json
import logging
import time
from collections import deque

log = logging.getLogger("chatconnect.hub")

PLATFORMS = ("twitch", "youtube")

# Colors assigned to authors that do not bring their own (YouTube, colorless Twitch users)
PALETTE = [
    "#FF6B6B", "#F5A623", "#F8E71C", "#7ED321", "#50E3C2", "#4FC3F7",
    "#5C9DFF", "#9B7BFF", "#FF7BC6", "#FF9F5A", "#6BE585", "#E0A8FF",
]


def color_for(name: str) -> str:
    return PALETTE[hash(name or "?") % len(PALETTE)]


class ChatHub:
    """Keeps recent history, per-platform status, and broadcasts events."""

    def __init__(self, history_size: int = 300):
        self.history = deque(maxlen=history_size)
        self._next_id = 1
        self._subscribers: set[asyncio.Queue] = set()
        self._seen_native = deque(maxlen=400)   # (platform, native_id) dedupe guard
        self.log_path = None                    # set by main.py when logging enabled
        self.overlay_config = {}                # set by main.py, shared via hello
        self.tools = {}                         # external tools (Duck, ...) reporting in
        self.status = {
            p: {"platform": p, "state": "disconnected", "detail": "", "target": ""}
            for p in PLATFORMS
        }

    # ---------------------------------------------------------------- subscribe

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=500)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

    def _broadcast(self, event: dict):
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer: drop its oldest event instead of blocking everyone.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass

    # ------------------------------------------------------------------ publish

    def publish_chat(self, *, platform: str, author: str, message: str,
                     message_clean: str | None = None, author_id: str = "",
                     color: str | None = None, badges: list | None = None,
                     emotes: list | None = None, amount: str | None = None,
                     native_id: str | None = None) -> dict | None:
        """Publish one chat message. Returns the unified message (or None if dupe)."""
        if native_id:
            key = (platform, native_id)
            if key in self._seen_native:
                return None
            self._seen_native.append(key)

        msg = {
            "id": self._next_id,
            "platform": platform,
            "author": author or "???",
            "author_id": author_id or "",
            "message": message,
            "message_clean": (message_clean if message_clean is not None else message).strip(),
            "color": color or color_for(author),
            "badges": badges or [],
            "emotes": emotes or [],
            "timestamp": round(time.time(), 3),
        }
        if amount:
            msg["amount"] = amount
        self._next_id += 1
        self.history.append(msg)
        self._broadcast({"type": "chat", "data": msg})
        self._log_to_file(msg)
        log.info("[%s] %s: %s", platform, msg["author"], message)
        return msg

    def mark_seen(self, platform: str, native_id: str | None):
        """Remember a platform message id without publishing it (skips old history)."""
        if native_id:
            self._seen_native.append((platform, native_id))

    def set_tool_status(self, tool: str, state: str, detail: str = ""):
        """Status heartbeat from an external tool (e.g. the Duck TTS).

        Stored with a timestamp so the dashboard can tell 'running' from
        'stopped reporting', and broadcast as a {"type": "tool"} event.
        """
        st = {"tool": tool, "state": state, "detail": detail,
              "updated": round(time.time(), 3)}
        previous = self.tools.get(tool)
        self.tools[tool] = st
        self._broadcast({"type": "tool", "data": dict(st)})
        if not previous or (previous["state"], previous["detail"]) != (state, detail):
            log.info("tool %s: %s %s", tool, state, ("- " + detail) if detail else "")

    def clear(self):
        """Wipe history and tell every page (overlay, dashboard) to clear its chat.

        Ids keep counting up and the platform dedupe guard stays, so consumers
        tracking `since` and reconnecting sources are unaffected.
        """
        self.history.clear()
        self._broadcast({"type": "clear", "data": {}})
        log.info("chat cleared")

    def set_status(self, platform: str, state: str, detail: str = "", target: str | None = None):
        """state: disconnected | connecting | waiting | connected | error"""
        st = self.status[platform]
        st["state"] = state
        st["detail"] = detail
        if target is not None:
            st["target"] = target
        self._broadcast({"type": "status", "data": dict(st)})
        log.info("status %s: %s %s", platform, state, ("- " + detail) if detail else "")

    # ------------------------------------------------------------------ helpers

    def hello_payload(self) -> dict:
        return {
            "type": "hello",
            "data": {"history": list(self.history), "status": self.status,
                     "overlay": self.overlay_config, "tools": self.tools},
        }

    def publish_overlay_config(self, cfg: dict):
        """Push new overlay settings to every connected page instantly."""
        self.overlay_config = cfg
        self._broadcast({"type": "overlay", "data": dict(cfg)})

    def messages_since(self, since_id: int, limit: int = 100) -> list:
        out = [m for m in self.history if m["id"] > since_id]
        return out[-limit:]

    def _log_to_file(self, msg: dict):
        if not self.log_path:
            return
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        except OSError as e:
            log.warning("could not write chat log: %s", e)
            self.log_path = None

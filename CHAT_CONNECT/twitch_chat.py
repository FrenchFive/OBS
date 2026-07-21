"""Twitch chat source for CHAT CONNECT.

Reads a channel's chat through Twitch's public IRC gateway using an anonymous
"justinfan" login. Reading chat this way needs NO account, NO OAuth token and
NO developer app - you only need the channel name.
"""

import asyncio
import logging
import random
import ssl

log = logging.getLogger("chatconnect.twitch")

IRC_HOST = "irc.chat.twitch.tv"
IRC_PORT = 6697
READ_TIMEOUT = 360          # Twitch pings every ~5 min; assume dead after 6
EMOTE_CDN = "https://static-cdn.jtvnw.net/emoticons/v2/{id}/default/dark/2.0"

_TAG_UNESCAPE = {"\\:": ";", "\\s": " ", "\\\\": "\\", "\\r": "\r", "\\n": "\n"}


def _unescape_tag(value: str) -> str:
    out, i = [], 0
    while i < len(value):
        pair = value[i:i + 2]
        if pair in _TAG_UNESCAPE:
            out.append(_TAG_UNESCAPE[pair])
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def parse_irc_line(line: str) -> dict:
    """Parse one raw IRC line into {tags, prefix, command, params, trailing}."""
    tags = {}
    if line.startswith("@"):
        raw_tags, _, line = line[1:].partition(" ")
        for part in raw_tags.split(";"):
            key, _, value = part.partition("=")
            tags[key] = _unescape_tag(value)
    prefix = ""
    if line.startswith(":"):
        prefix, _, line = line[1:].partition(" ")
    trailing = ""
    if " :" in line:
        line, _, trailing = line.partition(" :")
    parts = line.split()
    command = parts[0] if parts else ""
    params = parts[1:]
    return {"tags": tags, "prefix": prefix, "command": command,
            "params": params, "trailing": trailing}


def parse_emotes(emotes_tag: str, text: str):
    """Turn the IRC 'emotes' tag into ([{text,url}], clean_text).

    Tag format: "25:0-4,12-16/1902:6-10" -> emote id 25 at ranges 0-4 and 12-16.
    Ranges are in unicode code points, which is exactly how Python indexes str.
    """
    if not emotes_tag:
        return [], text
    spans = []       # (start, end_inclusive, emote_id)
    emotes = []
    seen_codes = set()
    try:
        for chunk in emotes_tag.split("/"):
            emote_id, _, ranges = chunk.partition(":")
            for rng in ranges.split(","):
                start_s, _, end_s = rng.partition("-")
                start, end = int(start_s), int(end_s)
                if 0 <= start <= end < len(text):
                    spans.append((start, end, emote_id))
    except ValueError:
        return [], text

    for start, end, emote_id in spans:
        code = text[start:end + 1]
        if code and code not in seen_codes:
            seen_codes.add(code)
            emotes.append({"text": code, "url": EMOTE_CDN.format(id=emote_id)})

    clean = text
    for start, end, _ in sorted(spans, reverse=True):
        clean = clean[:start] + clean[end + 1:]
    clean = " ".join(clean.split())
    return emotes, clean


class TwitchChat:
    """Connects to one channel and publishes messages to the hub. Run as a task."""

    def __init__(self, channel: str, hub):
        self.channel = channel.lstrip("#@ ").strip().lower()
        self.hub = hub
        self._writer = None

    async def run(self):
        backoff = 2
        try:
            while True:
                try:
                    got_room = await self._session()
                    backoff = 2 if got_room else min(backoff * 2, 60)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.warning("twitch session error: %s", e)
                    self.hub.set_status("twitch", "connecting",
                                        f"connection lost ({type(e).__name__}), retrying in {backoff}s")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)
        except asyncio.CancelledError:
            pass
        finally:
            await self._close()
            self.hub.set_status("twitch", "disconnected", "")

    async def _session(self) -> bool:
        """One connect->read cycle. Returns True if we ever fully joined."""
        self.hub.set_status("twitch", "connecting", "connecting to Twitch chat...",
                            target=self.channel)
        ctx = ssl.create_default_context()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(IRC_HOST, IRC_PORT, ssl=ctx), timeout=15)
        self._writer = writer

        nick = f"justinfan{random.randint(10_000, 99_999)}"
        await self._send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        await self._send(f"NICK {nick}")

        joined = False
        try:
            while True:
                raw = await asyncio.wait_for(reader.readline(), timeout=READ_TIMEOUT)
                if not raw:
                    raise ConnectionError("Twitch closed the connection")
                for line in raw.decode("utf-8", errors="replace").split("\r\n"):
                    line = line.strip("\r\n")
                    if not line:
                        continue
                    msg = parse_irc_line(line)
                    cmd = msg["command"]

                    if cmd == "PING":
                        await self._send(f"PONG :{msg['trailing'] or 'tmi.twitch.tv'}")
                    elif cmd == "001":
                        await self._send(f"JOIN #{self.channel}")
                    elif cmd == "ROOMSTATE":
                        joined = True
                        self.hub.set_status("twitch", "connected",
                                            f"reading chat of #{self.channel}")
                    elif cmd == "PRIVMSG":
                        self._on_privmsg(msg)
                    elif cmd == "NOTICE":
                        note = msg["trailing"]
                        log.info("twitch NOTICE: %s", note)
                        if "suspended" in note.lower() or "banned" in note.lower():
                            self.hub.set_status("twitch", "error", note)
                    elif cmd == "RECONNECT":
                        raise ConnectionError("Twitch asked us to reconnect")
        finally:
            await self._close()
        return joined

    def _on_privmsg(self, msg: dict):
        tags = msg["tags"]
        text = msg["trailing"]
        # /me messages arrive wrapped in \x01ACTION ...\x01
        if text.startswith("\x01ACTION ") and text.endswith("\x01"):
            text = text[8:-1]
        author = tags.get("display-name") or msg["prefix"].split("!")[0]
        emotes, clean = parse_emotes(tags.get("emotes", ""), text)
        badges = [b.partition("/")[0] for b in tags.get("badges", "").split(",") if b]
        self.hub.publish_chat(
            platform="twitch",
            author=author,
            author_id=tags.get("user-id", ""),
            message=text,
            message_clean=clean,
            color=tags.get("color") or None,
            badges=badges,
            emotes=emotes,
            native_id=tags.get("id"),
        )

    async def _send(self, line: str):
        self._writer.write((line + "\r\n").encode("utf-8"))
        await self._writer.drain()

    async def _close(self):
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

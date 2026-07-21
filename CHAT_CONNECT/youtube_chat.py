"""YouTube live chat source for CHAT CONNECT.

Two ways to read a live chat, both only need a channel/video link:

1. AUTOMATIC mode (default, no API key):
   Uses the same internal endpoint the YouTube website itself uses
   ("InnerTube": youtubei/v1/live_chat/get_live_chat). Zero setup.

2. OFFICIAL API mode (used automatically when an API key is provided):
   Uses the YouTube Data API v3 (liveChatMessages.list). Requires a free
   Google Cloud API key, uses daily quota, but is an official stable API.

Accepted targets: @handle, channel URL, channel ID (UC...), video URL,
youtu.be link, /live/ link or a bare 11-character video id.
"""

import asyncio
import json
import logging
import re

import aiohttp

log = logging.getLogger("chatconnect.youtube")

WATCH_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    # Skips the EU cookie-consent interstitial that would hide the page data
    "Cookie": "CONSENT=YES+cb; SOCS=CAI",
}
FALLBACK_CLIENT_VERSION = "2.20250320.01.00"


class ChatUnavailable(Exception):
    """Live chat can't be read (not live / disabled / ended)."""


class _Stop(Exception):
    """Terminal condition: leave the source stopped with its error status."""


# --------------------------------------------------------------------- helpers

def extract_json_after(marker: str, html: str) -> dict | None:
    """Find `marker` in html and decode the JSON object starting at the next '{'."""
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find("{", idx)
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
        return obj
    except json.JSONDecodeError:
        return None


def parse_target(target: str) -> tuple[str, str]:
    """Classify user input -> ("video"|"channel", normalized_value)."""
    t = target.strip()
    for pattern in (r"[?&]v=([\w-]{11})", r"youtu\.be/([\w-]{11})", r"/live/([\w-]{11})",
                    r"/embed/([\w-]{11})"):
        m = re.search(pattern, t)
        if m:
            return "video", m.group(1)
    m = re.search(r"/channel/(UC[\w-]{22})", t)
    if m:
        return "channel", "channel/" + m.group(1)
    m = re.search(r"(?:youtube\.com/)?(@[\w.\-]+)", t)
    if m and ("youtube.com" in t or t.startswith("@")):
        return "channel", m.group(1)
    m = re.search(r"youtube\.com/(?:c/|user/)([\w.\-]+)", t)
    if m:
        return "channel", "c/" + m.group(1)
    if re.fullmatch(r"UC[\w-]{22}", t):
        return "channel", "channel/" + t
    if re.fullmatch(r"[\w-]{11}", t):
        return "video", t
    # Fall back: treat a bare word as a handle ("quack_five" -> "@quack_five")
    return "channel", "@" + t.lstrip("@")


def _runs_to_text(runs: list) -> tuple[str, str, list]:
    """YouTube message 'runs' -> (full_text, clean_text, emotes[])."""
    full, clean, emotes = [], [], []
    seen = set()
    for run in runs:
        if "text" in run:
            full.append(run["text"])
            clean.append(run["text"])
        elif "emoji" in run:
            emoji = run["emoji"]
            shortcuts = emoji.get("shortcuts") or []
            label = (shortcuts[0] if shortcuts
                     else emoji.get("image", {}).get("accessibility", {})
                          .get("accessibilityData", {}).get("label", ""))
            if emoji.get("isCustomEmoji"):
                text = label or ":emote:"
                full.append(text)
                thumbs = emoji.get("image", {}).get("thumbnails") or []
                if text not in seen and thumbs:
                    seen.add(text)
                    emotes.append({"text": text, "url": thumbs[-1].get("url", "")})
            else:
                # Standard emoji: emojiId is the actual unicode character(s)
                char = emoji.get("emojiId", label)
                full.append(char)
                clean.append(char)
    full_text = "".join(full)
    clean_text = " ".join("".join(clean).split())
    return full_text, clean_text, emotes


def _badges_from_renderer(renderer: dict) -> list:
    badges = []
    for badge in renderer.get("authorBadges", []):
        b = badge.get("liveChatAuthorBadgeRenderer", {})
        icon = b.get("icon", {}).get("iconType", "")
        if icon == "OWNER":
            badges.append("broadcaster")
        elif icon == "MODERATOR":
            badges.append("moderator")
        elif icon == "VERIFIED":
            badges.append("verified")
        elif "customThumbnail" in b:
            badges.append("member")
    return badges


# ----------------------------------------------------------------- base source

class _YouTubeBase:
    def __init__(self, target: str, hub):
        self.target = target.strip()
        self.kind, self.value = parse_target(self.target)
        self.hub = hub
        self.session: aiohttp.ClientSession | None = None

    async def run(self):
        stopped_with_error = False
        try:
            async with aiohttp.ClientSession(headers=WATCH_HEADERS) as self.session:
                await self._run_forever()
        except _Stop:
            stopped_with_error = True
        except asyncio.CancelledError:
            pass
        finally:
            if not stopped_with_error:
                self.hub.set_status("youtube", "disconnected", "")

    async def _run_forever(self):
        while True:
            self.hub.set_status("youtube", "connecting", "looking up live stream...",
                                target=self.target)
            try:
                video_id = await self._resolve_video_id()
            except ChatUnavailable as e:
                await self._wait_or_die(str(e))
                continue
            except Exception as e:
                log.warning("youtube resolve error: %s", e)
                self.hub.set_status("youtube", "connecting",
                                    f"lookup failed ({type(e).__name__}), retrying in 20s")
                await asyncio.sleep(20)
                continue

            try:
                await self._read_chat(video_id)
                # Chat ended cleanly (stream over)
                await self._wait_or_die("stream ended")
            except ChatUnavailable as e:
                await self._wait_or_die(str(e))
            except Exception as e:
                log.warning("youtube chat error: %s", e)
                self.hub.set_status("youtube", "connecting",
                                    f"chat lost ({type(e).__name__}), reconnecting in 10s")
                await asyncio.sleep(10)

    async def _wait_or_die(self, reason: str):
        """Channel targets keep watching for the next live; video targets stop."""
        if self.kind == "channel":
            self.hub.set_status("youtube", "waiting",
                                f"{reason} - watching channel, next check in 30s")
            await asyncio.sleep(30)
        else:
            self.hub.set_status("youtube", "error",
                                f"{reason} - give a channel (@handle) to auto-wait for lives")
            raise _Stop

    # ------------------------------------------------------------ video lookup

    async def _resolve_video_id(self) -> str:
        if self.kind == "video":
            return self.value
        url = f"https://www.youtube.com/{self.value}/live"
        async with self.session.get(url, allow_redirects=True) as resp:
            if resp.status == 404:
                raise ChatUnavailable(f"channel '{self.target}' not found (404)")
            final_url = str(resp.url)
            html = await resp.text()

        # 1. Old behaviour: /live redirects straight to the watch page
        m = re.search(r"[?&]v=([\w-]{11})", final_url)
        if m:
            return m.group(1)

        # 2. Current behaviour: /live renders the watch page inline; the live
        #    video id sits in ytInitialData.currentVideoEndpoint (absent when
        #    the channel is not live).
        data = (extract_json_after("var ytInitialData =", html)
                or extract_json_after('window["ytInitialData"] =', html)) or {}
        vid = (data.get("currentVideoEndpoint", {}).get("watchEndpoint", {})
               .get("videoId"))
        if vid:
            return vid

        # 3. Older layouts: canonical link / player response
        m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"', html)
        if m:
            return m.group(1)
        player = extract_json_after("var ytInitialPlayerResponse =", html) or {}
        details = player.get("videoDetails", {})
        if details.get("videoId") and (details.get("isLive") or details.get("isUpcoming")):
            return details["videoId"]

        raise ChatUnavailable("channel is not live right now")

    # ------------------------------------------------------- shared publishing

    def _publish_item(self, item: dict):
        renderer = item.get("liveChatTextMessageRenderer")
        amount = None
        if renderer is None:
            renderer = item.get("liveChatPaidMessageRenderer")
            if renderer is not None:
                amount = renderer.get("purchaseAmountText", {}).get("simpleText")
        if renderer is None:
            return
        full, clean, emotes = _runs_to_text(renderer.get("message", {}).get("runs", []))
        if not full and not amount:
            return
        self.hub.publish_chat(
            platform="youtube",
            author=renderer.get("authorName", {}).get("simpleText", ""),
            author_id=renderer.get("authorExternalChannelId", ""),
            message=full,
            message_clean=clean,
            badges=_badges_from_renderer(renderer),
            emotes=emotes,
            amount=amount,
            native_id=renderer.get("id"),
        )

    async def _read_chat(self, video_id: str):
        raise NotImplementedError


# ------------------------------------------------- automatic (no API key) mode

class YouTubeChat(_YouTubeBase):
    """Reads live chat through YouTube's own InnerTube endpoint. No API key."""

    async def _read_chat(self, video_id: str):
        api_key, client_version, continuation = await self._init_chat(video_id)
        self.hub.set_status("youtube", "connected",
                            f"reading live chat of video {video_id}")
        context = {"client": {"clientName": "WEB", "clientVersion": client_version,
                              "hl": "en", "gl": "US"}}
        url = (f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat"
               f"?key={api_key}&prettyPrint=false")
        errors = 0
        while True:
            body = {"context": context, "continuation": continuation}
            try:
                async with self.session.post(url, json=body) as resp:
                    if resp.status != 200:
                        raise ConnectionError(f"get_live_chat HTTP {resp.status}")
                    data = await resp.json()
                errors = 0
            except (aiohttp.ClientError, ConnectionError, asyncio.TimeoutError) as e:
                errors += 1
                if errors > 5:
                    raise
                log.warning("youtube poll error (%s), retrying: %s", errors, e)
                await asyncio.sleep(3)
                continue

            chat = data.get("continuationContents", {}).get("liveChatContinuation")
            if not chat:
                return  # stream / chat ended

            for action in chat.get("actions", []):
                item = action.get("addChatItemAction", {}).get("item")
                if item:
                    self._publish_item(item)

            continuation, timeout_ms = self._next_continuation(chat)
            if not continuation:
                return
            await asyncio.sleep(min(max(timeout_ms, 800), 10_000) / 1000)

    @staticmethod
    def _next_continuation(chat: dict) -> tuple[str | None, int]:
        for cont in chat.get("continuations", []):
            for key in ("invalidationContinuationData", "timedContinuationData",
                        "reloadContinuationData"):
                if key in cont:
                    c = cont[key]
                    return c.get("continuation"), int(c.get("timeoutMs", 1500))
        return None, 1500

    async def _init_chat(self, video_id: str) -> tuple[str, str, str]:
        """Fetch the live_chat page and pull api key + first continuation token."""
        url = f"https://www.youtube.com/live_chat?is_popout=1&v={video_id}"
        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise ChatUnavailable(f"live chat page returned HTTP {resp.status}")
            html = await resp.text()

        m = re.search(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"', html)
        if not m:
            raise ChatUnavailable("could not read chat page (YouTube layout change?)")
        api_key = m.group(1)
        cv = re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION"\s*:\s*"([^"]+)"', html)
        client_version = cv.group(1) if cv else FALLBACK_CLIENT_VERSION

        initial = (extract_json_after('window["ytInitialData"] =', html)
                   or extract_json_after("var ytInitialData =", html))
        if not initial:
            raise ChatUnavailable("could not read chat data (is the video live?)")
        chat_renderer = initial.get("contents", {}).get("liveChatRenderer")
        if not chat_renderer:
            raise ChatUnavailable("no active live chat on this video "
                                  "(not live, ended, or chat disabled)")

        # Prefer the "Live chat" view (all messages) over filtered "Top chat"
        continuation = None
        try:
            items = (chat_renderer["header"]["liveChatHeaderRenderer"]["viewSelector"]
                     ["sortFilterSubMenuRenderer"]["subMenuItems"])
            continuation = (items[1]["continuation"]["reloadContinuationData"]
                            ["continuation"])
        except (KeyError, IndexError):
            pass
        if not continuation:
            for cont in chat_renderer.get("continuations", []):
                for c in cont.values():
                    if isinstance(c, dict) and c.get("continuation"):
                        continuation = c["continuation"]
                        break
        if not continuation:
            raise ChatUnavailable("could not find a chat continuation token")
        return api_key, client_version, continuation


# --------------------------------------------------------- official API mode

class YouTubeChatAPI(_YouTubeBase):
    """Reads live chat through the official YouTube Data API v3 (needs API key)."""

    def __init__(self, target: str, hub, api_key: str):
        super().__init__(target, hub)
        self.api_key = api_key.strip()

    async def _read_chat(self, video_id: str):
        chat_id = await self._active_chat_id(video_id)
        self.hub.set_status("youtube", "connected",
                            f"reading live chat of video {video_id} (official API)")
        page_token = None
        while True:
            params = {
                "liveChatId": chat_id,
                "part": "snippet,authorDetails",
                "maxResults": "500",
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            async with self.session.get(
                    "https://www.googleapis.com/youtube/v3/liveChat/messages",
                    params=params) as resp:
                data = await resp.json()
                if resp.status == 403:
                    reason = self._api_error(data)
                    if "quota" in reason.lower():
                        raise ChatUnavailable("YouTube API quota exceeded for today "
                                              "(remove the API key to use automatic mode)")
                    raise ChatUnavailable(f"YouTube API refused: {reason}")
                if resp.status == 404 or data.get("error"):
                    return  # chat gone -> stream ended
            if data.get("offlineAt"):
                return
            first_page = page_token is None
            for item in data.get("items", []):
                self._publish_api_item(item, skip=first_page)
            page_token = data.get("nextPageToken")
            await asyncio.sleep(max(int(data.get("pollingIntervalMillis", 3000)), 1500) / 1000)

    def _publish_api_item(self, item: dict, skip: bool = False):
        # First page returns old history; mark it seen but don't re-publish it.
        snippet = item.get("snippet", {})
        author = item.get("authorDetails", {})
        text = snippet.get("displayMessage", "")
        amount = (snippet.get("superChatDetails", {}) or {}).get("amountDisplayString")
        if not text and not amount:
            return
        badges = []
        if author.get("isChatOwner"):
            badges.append("broadcaster")
        if author.get("isChatModerator"):
            badges.append("moderator")
        if author.get("isChatSponsor"):
            badges.append("member")
        if author.get("isVerified"):
            badges.append("verified")
        if skip:
            self.hub.mark_seen("youtube", item.get("id"))
            return
        self.hub.publish_chat(
            platform="youtube",
            author=author.get("displayName", ""),
            author_id=author.get("channelId", ""),
            message=text,
            message_clean=text,
            badges=badges,
            emotes=[],
            amount=amount,
            native_id=item.get("id"),
        )

    async def _active_chat_id(self, video_id: str) -> str:
        params = {"part": "liveStreamingDetails", "id": video_id, "key": self.api_key}
        async with self.session.get("https://www.googleapis.com/youtube/v3/videos",
                                    params=params) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise ChatUnavailable(f"YouTube API error: {self._api_error(data)}")
        items = data.get("items", [])
        if not items:
            raise ChatUnavailable("video not found via YouTube API")
        chat_id = items[0].get("liveStreamingDetails", {}).get("activeLiveChatId")
        if not chat_id:
            raise ChatUnavailable("video has no active live chat (not live or ended)")
        return chat_id

    @staticmethod
    def _api_error(data: dict) -> str:
        try:
            return data["error"]["errors"][0]["reason"] + " - " + data["error"]["message"]
        except (KeyError, IndexError, TypeError):
            return "unknown error"


def make_youtube_source(target: str, hub, api_key: str = ""):
    """API key present -> official API mode, otherwise automatic mode."""
    if api_key and api_key.strip():
        return YouTubeChatAPI(target, hub, api_key)
    return YouTubeChat(target, hub)

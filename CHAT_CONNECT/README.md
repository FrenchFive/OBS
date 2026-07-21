# 💬 CHAT CONNECT

One local server that merges **Twitch chat** and **YouTube live chat** into a
single realtime stream — with a web dashboard to control it, a transparent
overlay for OBS, and open endpoints so any of your scripts can consume the
messages.

> 🐣 **New here? Read [`SETUP_GUIDE.md`](SETUP_GUIDE.md)** — it explains every
> single step for complete beginners. This README is the technical overview.

```
                 ┌──────────────────────────────┐
  Twitch IRC ───►│                              │───► Dashboard  http://localhost:2428
  (anonymous)    │         CHAT CONNECT         │───► OBS overlay  /overlay
                 │      localhost : 2428        │───► WebSocket    /ws
  YouTube chat ─►│                              │───► SSE          /events
  (no API key)   └──────────────────────────────┘───► REST         /api/messages
                                                  └─► Duck TTS (CHAT_YAPPER), your scripts…
```

## Features

- **Zero credentials.** Twitch is read via anonymous IRC (no OAuth, no dev
  app). YouTube is read via the site's own internal endpoint (no API key) —
  or optionally via the official YouTube Data API v3 if you provide a key.
- **Set-and-forget YouTube.** Give it your `@handle` and it waits for your
  stream, attaches when you go live, and re-arms after the stream ends.
- **Web dashboard** (black & white) with live connection status, merged feed,
  test-message injection and a stop button.
- **OBS-ready overlay** (transparent, animated, emote images, badges, Super
  Chat highlight) with a **visual editor** at `/editor`: live preview on
  sample messages, saved server-side, pushed to open overlays instantly.
  Font size, message duration, username truncation, window/message
  backgrounds with opacity, platform logos, timestamps, chat delay
  (to sync with the Duck TTS), position, shadow.
- **Open firehose** for your own code: WebSocket, SSE and REST — all local.
- **Background friendly**: `run_background.bat` (silent) + `stop.bat`,
  auto-reconnect everywhere, config persisted in `config.json`.
- **OBS auto-launch**: add `obs_autolaunch.lua` in OBS (Tools → Scripts) and
  opening OBS starts CHAT CONNECT + the Duck; closing OBS stops them.

## Quick start

```bat
install.bat        (once)
run.bat            (opens http://localhost:2428)
```

Linux/macOS: `bash install.sh` then `./run.sh` (add `--background` to detach).

CLI options: `main.py [--port 2428] [--host 127.0.0.1] [--open] [--log-file server.log]`

## Files

| File | Role |
|------|------|
| `main.py` | server, routes, config, source manager |
| `hub.py` | message bus: history, dedupe, fan-out to subscribers |
| `twitch_chat.py` | anonymous Twitch IRC reader |
| `youtube_chat.py` | YouTube reader (automatic InnerTube mode + official API mode) |
| `web/index.html` | dashboard |
| `web/overlay.html` | OBS overlay |
| `web/editor.html` | visual overlay style editor |
| `obs_autolaunch.lua` | OBS script: start/stop everything with OBS |
| `autolaunch.bat` | silent starter used by the OBS script |
| `example_consumer.py` | smallest possible WebSocket consumer |
| `SETUP_GUIDE.md` | the full beginner walkthrough |

`config.json` (auto-created, git-ignored) stores host/port, saved channels,
autoconnect flags, the optional YouTube API key, the saved overlay style, and
`log_chat_to_file` (set `true` to also append every message to
`chat_log.jsonl`).

## API reference

All endpoints live on `http://127.0.0.1:2428`.

### Realtime streams

| Endpoint | Protocol |
|----------|----------|
| `/ws` | WebSocket |
| `/events` | Server-Sent Events (`event:` = type, `data:` = the `data` object) |

Every frame is an envelope:

```json
{ "type": "hello" | "chat" | "status" | "overlay" | "tool" | "clear", "data": { … } }
```

- **`hello`** — sent once on connect: `data.history` (recent messages,
  oldest→newest), `data.status` (current per-platform status) and
  `data.overlay` (the saved overlay style). Consumers that act on messages
  (TTS!) should ignore `history`.
- **`chat`** — one new chat message (schema below).
- **`status`** — `{platform, state, detail, target}` with `state` one of
  `disconnected | connecting | waiting | connected | error`.
- **`overlay`** — the overlay style was saved in the editor; `data` is the
  full new settings object (overlays restyle themselves live on this).
- **`tool`** — status heartbeat from an external tool (the Duck reports as
  `yapper`): `{tool, state, detail, updated, extra?}`. The dashboard shows it
  and treats >25s of silence as "not running". `extra` carries tool data
  (the Duck: its ElevenLabs voice catalog + selection for the voice picker).
- **`command`** — relayed from `POST /api/tool-command` to whichever tool it
  addresses (`data.tool`), e.g. the dashboard's voice picker sending
  `{tool:"yapper", action:"set_voices", voices:[…]}`.
- **`clear`** — the chat was reset (dashboard button / `POST /api/clear`);
  pages wipe their displayed messages. `data` is empty.

### Chat message schema

```json
{
  "id": 42,                    // incrementing int, unique per server run
  "platform": "twitch",        // "twitch" | "youtube" | "test"
  "author": "French_five",     // display name
  "author_id": "12345",        // platform user/channel id ("" if unknown)
  "message": "Kappa hello",    // original text (emote codes included)
  "message_clean": "hello",    // emote codes stripped -> use for TTS
  "color": "#8A2BE2",          // author color (Twitch-provided or assigned)
  "badges": ["broadcaster"],   // broadcaster|moderator|vip|subscriber|member|verified
  "emotes": [                  // for rendering emote images in the text
    {"text": "Kappa", "url": "https://static-cdn.jtvnw.net/…"}
  ],
  "amount": "€5.00",           // ONLY present on YouTube Super Chats
  "timestamp": 1712345678.901  // unix seconds
}
```

### REST

| Method & path | Body / params | Effect |
|---|---|---|
| `GET /api/status` | – | current status + endpoint list |
| `GET /api/messages` | `?since=<id>&limit=100` | history after id (max 300 kept) |
| `GET /api/overlay` | – | saved overlay style |
| `POST /api/overlay` | `{size, fade, max, name_max, window_bg, window_bg_opacity, msg_bg, msg_bg_opacity, show_platform, show_time, delay, align, shadow_strength}` | save style + push to open overlays |
| `POST /api/connect` | `{"platform":"twitch","channel":"name"}` | connect Twitch |
| `POST /api/connect` | `{"platform":"youtube","target":"@handle or URL","api_key":""}` | connect YouTube (key optional) |
| `POST /api/disconnect` | `{"platform":"twitch"\|"youtube"}` | disconnect + disable autoconnect |
| `POST /api/test` | `{"platform","author","message"}` (all optional) | inject a fake message |
| `POST /api/tool-status` | `{"tool":"yapper","state":"connected","detail":"…","extra":{…}}` | report an external tool's health (shown on the dashboard; repeat every ~8 s as a heartbeat) |
| `POST /api/tool-command` | `{"tool":"yapper","action":"set_voices","voices":[…]}` | send a command to a connected tool (relayed as a `command` event) |
| `POST /api/clear` | – | reset the chat: wipe history + clear every open page |
| `POST /api/shutdown` | – | stop the server |

### Consuming from Python

See [`example_consumer.py`](example_consumer.py) — ~30 lines, reconnects
forever, prints every message. The Duck (`../CHAT_YAPPER`) is the real-world
version of the same pattern.

`curl` taste test:

```bash
curl http://localhost:2428/api/messages?since=0     # poll
curl -N http://localhost:2428/events                # realtime SSE
```

### Overlay styling

Style lives server-side and is edited visually at `/editor` (live preview,
instant apply, persisted). URL params override single settings per browser
source: `size, fade, max, name, bg, winbg, platform, time, delay, align,
shadow` — table in
[SETUP_GUIDE.md §9](SETUP_GUIDE.md#9-make-it-look-how-you-want-overlay-editor).

## Notes & limits

- Read-only by design: it cannot post, moderate, or touch your accounts.
- YouTube automatic mode uses YouTube's internal web endpoint; if YouTube
  changes it, switch to the official API key mode (guide §12) until this repo
  is updated.
- History buffer is the last 300 messages (in RAM); `since`-polling beyond
  that returns only what's buffered.
- Port 2428 = "CHAT" typed on a phone keypad. ☎️

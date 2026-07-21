# 🦆 CHAT YAPPER — the Duck that reads chat

A duck pops up in OBS and **reads chat messages out loud** with random fun
voices. Since the CHAT CONNECT rework it reads **Twitch AND YouTube** — it
takes its messages from the merged stream served by
[`../CHAT_CONNECT`](../CHAT_CONNECT), so it needs **no Twitch/YouTube
credentials at all**.

```
Twitch + YouTube ──► CHAT CONNECT (ws://127.0.0.1:2428/ws) ──► CHAT YAPPER ──► OBS (duck + voice)
```

## What you need

- **CHAT CONNECT** installed and running (see
  [`../CHAT_CONNECT/SETUP_GUIDE.md`](../CHAT_CONNECT/SETUP_GUIDE.md))
- **OBS** with the WebSocket server enabled:
  *Tools → WebSocket Server Settings → Enable WebSocket server* (port `4455`).
  If you set a password there, put it in `.env` (see below).
- *(Optional)* an **OpenAI API key** for the fancy random voices
  (`gpt-4o-mini-tts`). Without a key the Duck falls back to the free offline
  Windows voice (pyttsx3).

## OBS scene setup (one time)

The script drives three things in your current scene — create them with
exactly these names:

| Name | Type | Purpose |
|------|------|---------|
| `CHAT_YAPPING` | **Group** (right-click sources → Group) | everything that should pop in/out: put the duck image + author text inside |
| `PYTHON_AUTHOR` | **Text (GDI+)** source, inside the group | shows who is talking (e.g. "french_five · Twitch") |
| `PYTHON_TTS` | **Media Source**, can be outside the group | plays `tts.wav`; leave the file empty (the script sets it) |

`duck_image.png` in this folder is a ready-to-use duck. The script shows the
`CHAT_YAPPING` group while the voice plays, then hides it again.

## Install & run

```bat
install.bat                      (once)
copy .env.example .env           (optional - only to set keys/passwords)
run.bat                          (console window)
```

Start order: **CHAT CONNECT → OBS → CHAT YAPPER**. (Wrong order is fine too —
the Duck waits for OBS and retries CHAT CONNECT every 5 s until they're up.)

Other ways to run it:

- **`run_background.bat`** — no window; output goes to `yapper.log`.
  Stop it with **`stop.bat`**.
- **Auto-start with OBS (best)** — add `CHAT_CONNECT/obs_autolaunch.lua` in
  OBS (Tools → Scripts): opening OBS starts CHAT CONNECT + the Duck, closing
  OBS stops them. Setup steps in
  [`../CHAT_CONNECT/SETUP_GUIDE.md` §13](../CHAT_CONNECT/SETUP_GUIDE.md#13-start-everything-automatically-with-obs).

Only one Duck can run at a time (a second copy exits by itself), so clicking
`run.bat` while the auto-launched one is active is harmless.

## `.env` settings (all optional)

```ini
KEY_OPENAI=sk-…                          # fancy voices; empty = offline voice
CHAT_CONNECT_URL=ws://127.0.0.1:2428/ws  # where CHAT CONNECT runs
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=                            # if you set one in OBS
```

## Knowing that it works (and why it doesn't)

The Duck never fails silently:

- It reports its **live status to the CHAT CONNECT dashboard** — the
  🦆 CHAT YAPPER card shows `connected`, `waiting for OBS`, or the exact
  problem ("OBS is missing a source named 'PYTHON_TTS'", "OpenAI TTS
  failed", …). The banner at the top of the dashboard sums up Twitch +
  YouTube + Duck in one line.
- On startup it **checks everything**: Python packages, the OBS websocket,
  the three OBS sources (by exact name), the silent wav (recreated if
  missing) and which voice it can use.
- Real problems open a **Windows pop-up**, even when running hidden in the
  background. Everything is also logged (`yapper.log` in background mode).
- If OBS sources are missing it keeps running and **rechecks every 30 s**,
  so you can fix the scene without restarting anything.

## Behaviour details

- Reads `message_clean` (emotes/emoji codes stripped) — the Duck doesn't try
  to pronounce `french210Love`.
- Announces the author as `name · Twitch` / `name · YouTube` in the
  `PYTHON_AUTHOR` text source.
- If chat goes faster than the Duck can talk, it keeps the **5 newest**
  messages and drops the oldest — it never lags minutes behind.
- Old history is never read on startup/reconnect (only live messages).
- The **Send test message** button on the CHAT CONNECT dashboard makes the
  Duck talk without being live — great for testing volume and layout.
- The voice takes a moment to generate, so it runs slightly behind the
  on-screen chat — set **Chat delay** in the overlay editor
  (`http://localhost:2428/editor`) to line the overlay up with the Duck.
- When launched by the OBS auto-launcher, the Duck runs in "follow mode":
  it exits automatically when CHAT CONNECT stops (i.e. when OBS closes).

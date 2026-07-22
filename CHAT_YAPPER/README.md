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
- *(Optional)* an **ElevenLabs API key** and/or an **OpenAI API key** for AI
  voices. No key (or a broken key/package)? The Duck automatically uses
  **Windows' built-in voice** instead — it always has a voice. Full fallback
  chain: **ElevenLabs → OpenAI → Windows voice → pyttsx3**. The engines are
  tested at startup and the active voice is shown on the dashboard's Duck
  card. ElevenLabs options in `.env`: `ELEVENLABS_API_KEY`, optional
  `ELEVENLABS_VOICE_IDS` (comma-separated ids from your VoiceLab; empty =
  rotate through built-in voices) and `ELEVENLABS_MODEL`
  (default `eleven_flash_v2_5`).

## OBS setup — automatic

**You don't have to create anything in OBS anymore.** On start the Duck
checks what exists and **creates whatever is missing**:

- a scene called `CHAT_YAPPING` (works exactly like a group for the Duck),
  added hidden to your current scene
- inside it: the duck image (`PYTHON_DUCK`, using `duck_image.png`), the
  author text (`PYTHON_AUTHOR`) and the pre-configured media source
  (`PYTHON_TTS`)

Then just position/resize the duck once, the way you like. If you later
switch to a scene that doesn't contain `CHAT_YAPPING`, the Duck adds it
there too (hidden) within ~30 seconds.

Two important guarantees:

- **Existing sources are NEVER modified or recreated.** If you already have
  any of these (with filters on them — audio-reactive duck motion plugins,
  etc.), the Duck only fills the gaps and leaves yours exactly as they are.
- Set `CHAT_YAPPER_NO_AUTOSETUP=1` in `.env` to turn auto-creation off
  entirely and manage OBS yourself.

For reference, the names the script drives (a `CHAT_YAPPING` **group** you
made yourself works just as well as the auto-created scene):

| Name | Type | Purpose |
|------|------|---------|
| `CHAT_YAPPING` | scene or group in your current scene | pops in/out while the Duck talks |
| `PYTHON_AUTHOR` | text source | shows who is talking (e.g. "french_five · Twitch") |
| `PYTHON_TTS` | media source | plays `tts.wav`; the Duck sets the file and drives playback (no stutter) |
| `PYTHON_DUCK` | image source | the duck itself (only created by auto-setup, never required) |

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

## Panic controls — skip & mute, from anywhere

Two safety controls, built for "cut it NOW" moments (spam, something
TOS-risky, harassment):

- **SKIP** — instantly cuts the message being spoken, mid-word. The next
  message continues normally.
- **PAUSE / RESUME** — mutes the whole TTS: cuts the current message,
  empties the queue, and drops everything new until you resume (no backlog
  gets blurted afterwards). The dashboard's Duck card shows **PAUSED** while
  muted.

Four ways to trigger them, all equivalent:

1. **Global hotkeys** (work whatever window is focused, even in-game):
   - Skip: `Ctrl+Alt+Shift+F9`
   - Pause/Resume: `Ctrl+Alt+Shift+F10`
   Deliberately awkward combos so nothing else uses them; change or disable
   them with `HOTKEY_SKIP` / `HOTKEY_PAUSE` in `.env` (single keys like
   `f13` work, combos like `ctrl+alt+shift+f13` too). Keys are matched **by
   name**, so F13–F24 sent by a Stream Deck are caught reliably. Whether
   the hotkeys are armed is shown on the dashboard's Duck card and in the
   broadcaster view ("⌨ global hotkeys — …" / "⚠ hotkeys OFF"), and a
   pop-up warns you at startup if they couldn't be enabled (usually:
   re-run `install.bat` once for the `keyboard` package).
2. **Stream Deck — simplest**: add a **Hotkey** action sending the combo
   above. Pro tip: set the hotkey in `.env` to an `f13`–`f24` key — those
   don't exist on physical keyboards, so collisions are impossible and the
   Stream Deck can still send them.
3. **Stream Deck — macro/Open**: point a **System → Open** action at
   `CHAT_YAPPER\skip.bat` or `CHAT_YAPPER\pause.bat`.
4. **URLs / dashboard**: the Duck card has **⏭ Skip** and **🔇 Pause TTS**
   buttons, and any URL-trigger tool can call
   `http://127.0.0.1:2428/api/duck/skip` or `/api/duck/toggle` (GET or
   POST). For a Stream Deck plugin that changes the key's color with state:
   poll `GET /api/status` — `tools.yapper.state` is `"paused"` while muted.

## Choosing your ElevenLabs voices

With `ELEVENLABS_API_KEY` set, open the CHAT CONNECT dashboard
(`http://localhost:2428`) while the Duck runs: the Duck card grows a
**"🎤 ElevenLabs voices"** section listing every voice on your account —
including any you add from the ElevenLabs Voice Library on their site.
Press **▶** to hear a sample, tick the ones the Duck should rotate through,
and hit **Save voices** — the Duck switches instantly and remembers the set
(`voices.json`). No ticks = a default rotation. (`ELEVENLABS_VOICE_IDS` in
`.env` still works as a manual override when nothing was picked.)

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
- **It waits for OBS to finish loading first.** OBS answers "not ready"
  (code 207) for a few seconds while it boots — the Duck patiently retries
  instead of raising a false alarm, so auto-starting both together never
  produces error pop-ups about missing sources.
- Real problems open a **Windows pop-up**, even when running hidden in the
  background. Everything is also logged (`yapper.log` in background mode).
- If OBS sources are missing it keeps running and **rechecks every 30 s**,
  so you can fix the scene without restarting anything.

## Behaviour details

- Reads `message_clean` (emote codes stripped) and additionally removes all
  **emojis** — the Duck pronounces neither `french210Love` nor `🔥🔥🔥`.
  Messages that are only emotes/emojis are skipped entirely (no duck pop-up).
- Announces the author as `name · Twitch` / `name · YouTube` in the
  `PYTHON_AUTHOR` text source.
- **Each chatter keeps their own voice**: the voice is picked from your
  selected set by a stable hash of the user's platform id, so PixelWarrior
  sounds like PixelWarrior every message, every stream (ElevenLabs and
  OpenAI voices; changing the selected voice set reshuffles who gets what).
- If chat goes faster than the Duck can talk, messages wait in a queue
  (default **10**, `TTS_QUEUE_SIZE` in `.env`) and the oldest are dropped
  beyond that — it never lags minutes behind. The dashboard's Duck card
  shows how many are waiting and how many were skipped.
- Old history is never read on startup/reconnect (only live messages).
- The **Send test message** button on the CHAT CONNECT dashboard makes the
  Duck talk without being live — great for testing volume and layout.
- The voice takes a moment to generate, so it runs slightly behind the
  on-screen chat — set **Chat delay** in the overlay editor
  (`http://localhost:2428/editor`) to line the overlay up with the Duck.
- When launched by the OBS auto-launcher, the Duck runs in "follow mode":
  it exits automatically when CHAT CONNECT stops (i.e. when OBS closes).

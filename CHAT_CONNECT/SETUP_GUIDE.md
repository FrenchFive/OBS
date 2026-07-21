# 💬 CHAT CONNECT — Complete Setup Guide (for total beginners)

This guide takes you from **nothing installed** to **Twitch + YouTube chat
merged together**, displayed in OBS, and readable by any other tool (like the
Duck TTS). Every single step is written out. If you already know a step, skip it.

> **What you end up with:**
> - A small program running in the background on your PC
> - A control page in your browser: `http://localhost:2428`
> - Your **Twitch chat** and **YouTube live chat** merged into one feed
> - A **clean chat overlay** you can drop into OBS and style in a visual editor
> - A local "chat firehose" any script can plug into (WebSocket / SSE / REST)
> - Optionally: everything starts **automatically when you open OBS**

---

## Table of contents

1. [Install Python (one time)](#1-install-python-one-time)
2. [Download this project](#2-download-this-project)
3. [Install CHAT CONNECT (one time)](#3-install-chat-connect-one-time)
4. [Start CHAT CONNECT](#4-start-chat-connect)
5. [Connect your Twitch chat](#5-connect-your-twitch-chat)
6. [Connect your YouTube chat](#6-connect-your-youtube-chat)
7. [Test it without being live](#7-test-it-without-being-live)
8. [Show the chat in OBS (overlay)](#8-show-the-chat-in-obs-overlay)
9. [Make it look how you want (overlay editor)](#9-make-it-look-how-you-want-overlay-editor)
10. [Run it in the background](#10-run-it-in-the-background)
11. [Use the messages in your own code](#11-use-the-messages-in-your-own-code)
12. [Make the Duck read both chats (CHAT YAPPER)](#12-make-the-duck-read-both-chats-chat-yapper)
13. [Start everything automatically with OBS](#13-start-everything-automatically-with-obs)
14. [Optional: official YouTube API key](#14-optional-official-youtube-api-key)
15. [Troubleshooting](#15-troubleshooting)
16. [FAQ](#16-faq)

---

## 1. Install Python (one time)

CHAT CONNECT is written in Python. You need Python **3.10 or newer**.

**Windows:**

1. Go to <https://www.python.org/downloads/> and click the big yellow
   **Download Python 3.x.x** button.
2. Open the downloaded file.
3. ⚠️ **VERY IMPORTANT:** on the first screen, tick the checkbox at the bottom:
   **"Add python.exe to PATH"**. If you miss this, nothing else will work.
4. Click **Install Now** and wait for it to finish.
5. Check it worked: press `Windows key`, type `cmd`, press Enter, then type:

   ```
   python --version
   ```

   You should see something like `Python 3.12.4`. If you see an error, reboot
   and try again, or reinstall with the PATH checkbox ticked.

**macOS / Linux:** install Python 3 from <https://www.python.org> or your
package manager (`brew install python3` / `sudo apt install python3 python3-venv`).

---

## 2. Download this project

**Option A — no tools needed (easiest):**

1. Open the repository page on GitHub.
2. Click the green **`<> Code`** button → **Download ZIP**.
3. Right-click the ZIP → **Extract All…** → pick an easy location, e.g.
   `C:\OBS-tools\`. You now have a folder like `C:\OBS-tools\OBS-main\`.

**Option B — with git:**

```
git clone https://github.com/frenchfive/OBS.git
```

The folder that matters in this guide is **`CHAT_CONNECT`** inside the project.

---

## 3. Install CHAT CONNECT (one time)

**Windows:**

1. Open the `CHAT_CONNECT` folder in Explorer.
2. Double-click **`install.bat`**.
3. A black window opens and downloads what's needed (~10 seconds).
   When it says **Done!**, press any key to close it.

> If Windows shows *"Windows protected your PC"*: click **More info** →
> **Run anyway**. The script only creates a private Python environment
> (a `.venv` folder) and installs one library (`aiohttp`) into it.

**macOS / Linux:**

```bash
cd CHAT_CONNECT
bash install.sh
```

---

## 4. Start CHAT CONNECT

**Windows:** double-click **`run.bat`** in the `CHAT_CONNECT` folder.

Two things happen:

- a black console window stays open (that's the server — leave it running), and
- your browser opens the dashboard at **`http://localhost:2428`**.

If the browser doesn't open by itself, open one and type `localhost:2428` in
the address bar.

**macOS / Linux:** `./run.sh`

> The dashboard header should say **"● server online"**. That's your control
> center. Bookmark it.

---

## 5. Connect your Twitch chat

Good news: **reading Twitch chat needs no password, no token, no developer
app.** Twitch chat is public — CHAT CONNECT just joins the chat room
anonymously, like a lurker viewer would.

1. On the dashboard, find the **Twitch** card.
2. Type your **channel name** in the box. That's the last part of your channel
   link: if your channel is `https://www.twitch.tv/french_five`, type
   `french_five`. Lowercase, no spaces, no `#`.
3. Click **Connect**.
4. The status dot pulses while connecting, then turns ⚪ solid **connected**
   after a couple of seconds.

Type something in your own Twitch chat (you can do this from the Twitch
website even when offline) — it appears in the **Live feed** at the bottom of
the dashboard. Twitch is done. Yes, really — that was everything.

> CHAT CONNECT remembers this and reconnects automatically every time you
> start it. Click **Disconnect** to make it stop remembering.

---

## 6. Connect your YouTube chat

Also good news: **no API key needed** in normal ("automatic") mode.
YouTube live chat only exists while a stream (or premiere) is live or starting,
so the best workflow is the **channel handle** one:

### The easy way — your channel handle (recommended)

1. Find your **handle**: open your YouTube channel page and look at the name
   starting with `@` (for example `@quack_five`). It's also in the channel URL:
   `https://www.youtube.com/@quack_five`.
2. On the dashboard, in the **YouTube** card, type your handle **with** the
   `@`: `@quack_five`.
3. Leave the **API key** box **empty**.
4. Click **Connect**.

What happens next:

- If you are **live right now** → status turns **connected** and messages
  flow.
- If you are **not live** → status shows **waiting for live…** and CHAT
  CONNECT re-checks your channel every 30 seconds, forever. Start it before
  your stream, go live on YouTube, and it hooks itself up within ~30 seconds.
  When your stream ends it goes back to waiting for the next one. You never
  have to touch it again.

### The direct way — paste the video link

If you prefer, paste the full link of your live video (from your browser's
address bar, or **YouTube Studio → Go Live → Share**) into the same box, e.g.
`https://www.youtube.com/watch?v=AbCdEfGhIjK`. This connects to exactly that
stream, but you'll have to paste a fresh link on every new stream — the
`@handle` way is more "set and forget".

> Automatic mode reads chat using the same internal interface the normal
> YouTube website uses. If Google ever changes it and it stops working, use
> the official API key mode — see [section 14](#14-optional-official-youtube-api-key).

---

## 7. Test it without being live

Click **Send test message** (top right of the Live feed card) on the
dashboard. A fake message appears in the feed, in the OBS overlay, and in
anything else connected (the Duck will read it out loud!). Perfect for checking
your OBS layout without going live.

Next to it, **🧹 Clear chat** resets the chat everywhere at once — the
dashboard feed AND the OBS overlay empty instantly. Handy after testing, or
whenever you want a clean overlay mid-stream.

---

## 8. Show the chat in OBS (overlay)

The overlay is a web page with a transparent background that shows the merged
chat in realtime — Twitch messages with the Twitch logo, YouTube messages with
the YouTube logo, mod/owner badges, colors, **emote and emoji images**, Super
Chats highlighted.

1. In OBS, in the **Sources** panel, click **+** → **Browser**.
2. Name it `CHAT CONNECT` → **OK**.
3. Set **URL** to:

   ```
   http://localhost:2428/overlay
   ```

4. Set **Width** `450` and **Height** `700` (or whatever fits your scene).
5. Click **OK**, then drag/resize the source wherever you want your chat.

That's it — new messages slide in, and it keeps working across stream restarts
(it reconnects on its own; when nothing is connected it simply shows nothing).

---

## 9. Make it look how you want (overlay editor)

Click **🎨 Customize overlay** on the dashboard (or open
`http://localhost:2428/editor`). You get a visual editor with **sample
messages** on the right so you see exactly what your chat will look like while
you play with the settings:

| Setting | What it does |
|---------|--------------|
| **Font size** | text size in pixels |
| **Text shadow** | keeps text readable on bright scenes |
| **Message duration** | seconds before a message fades out (`0` = stay forever) |
| **Max messages on screen** | how many messages stack up |
| **New messages appear** | at the bottom (classic) or at the top |
| **Chat delay** | hold messages back N seconds — use this to sync the overlay with the Duck TTS voice, which needs a moment to start speaking |
| **Shorten long usernames** | cut names longer than N characters (adds `…`) |
| **Platform logo** | show/hide the Twitch/YouTube icon per message |
| **Message time** | show `HH:MM` in front of each message |
| **Whole window background** | dark panel behind the entire chat, with opacity |
| **Bubble behind each message** | rounded dark bubble per message, with opacity |

Every change updates the preview **instantly**. When you like it, click
**💾 Save & apply**:

- the style is **saved on your PC** (it survives restarts), and
- **every open overlay updates immediately** — including the browser source
  running inside OBS. No refresh, no URL editing.

<details>
<summary><b>Advanced: different styles per OBS scene (URL options)</b></summary>

The plain `/overlay` URL always uses your saved style. If one specific browser
source should look different, override single settings in its URL — URL
options always win over the saved style, only for that source:

`http://localhost:2428/overlay?size=24&fade=15&bg=50`

| Option | Meaning |
|--------|---------|
| `size=18` | font size (px) |
| `fade=20` | message duration in seconds (0 = forever) |
| `max=12` | max messages on screen |
| `name=12` | truncate usernames to 12 chars (0 = full) |
| `bg=35` | per-message bubble, opacity 0–100 (0 = off) |
| `winbg=40` | whole-window background, opacity 0–100 (0 = off) |
| `platform=0` | hide platform logos |
| `time=1` | show message time |
| `delay=5` | delay messages by 5 s |
| `align=top` | newest message on top |
| `shadow=0` | no text shadow |

</details>

---

## 10. Run it in the background

You have three ways, pick your style:

- **`run.bat`** — normal window. Close the window (or press Ctrl+C) to stop it.
- **`run_background.bat`** — completely invisible, no window. Output goes to
  `CHAT_CONNECT/server.log`. Stop it with **`stop.bat`** or the **⏻ Stop
  server** button on the dashboard.
- **Start with OBS (best)** — see [section 13](#13-start-everything-automatically-with-obs):
  opening OBS starts everything, closing OBS stops everything.

Everything (channels, overlay style, settings) is saved in
`CHAT_CONNECT/config.json` and restored on start, so background mode
reconnects to your channels by itself.

---

## 11. Use the messages in your own code

Any program on your PC can tap the merged chat. Three doors, all on
`localhost:2428`, all sending the same JSON messages:

| Door | Address | Best for |
|------|---------|----------|
| **WebSocket** | `ws://127.0.0.1:2428/ws` | realtime bots, TTS, games |
| **SSE** (Server-Sent Events) | `http://127.0.0.1:2428/events` | browsers, simple scripts, `curl` |
| **REST polling** | `http://127.0.0.1:2428/api/messages?since=0` | dead-simple scripts, non-realtime |

Try it right now (server running): open
`http://localhost:2428/api/messages?since=0` in your browser, or run
`python example_consumer.py` in the `CHAT_CONNECT` folder, then hit
**Send test message** on the dashboard.

Each chat message looks like this (full reference in `README.md`):

```json
{
  "id": 42,
  "platform": "twitch",
  "author": "french_five",
  "message": "Kappa hello chat",
  "message_clean": "hello chat",
  "color": "#8A2BE2",
  "badges": ["broadcaster"],
  "emotes": [{"text": "Kappa", "url": "https://static-cdn..."}],
  "timestamp": 1712345678.901
}
```

`message_clean` is the text with emote codes removed — feed **that** to a TTS.

---

## 12. Make the Duck read both chats (CHAT YAPPER)

The Duck (in the `CHAT_YAPPER` folder) is already rewired to CHAT CONNECT.
Full details live in `CHAT_YAPPER/README.md`, short version:

1. In OBS: **Tools → WebSocket Server Settings** → tick **Enable WebSocket
   server**, port `4455`. If you set a password there, put it in
   `CHAT_YAPPER/.env` (copy `.env.example` to `.env`).
2. Make sure your OBS scene has the duck sources (`PYTHON_TTS`,
   `PYTHON_AUTHOR`, group `CHAT_YAPPING`) — see the Duck's README.
3. One-time: double-click `CHAT_YAPPER/install.bat`.
4. Start order: **CHAT CONNECT first**, then OBS, then `CHAT_YAPPER/run.bat`
   (or set up [section 13](#13-start-everything-automatically-with-obs) and
   never think about start order again).

The Duck now quacks Twitch AND YouTube messages, and says who wrote them and
from which platform.

> Tip: the voice needs a moment to generate and speak, so it runs a little
> behind the on-screen chat. Set **Chat delay** in the
> [overlay editor](#9-make-it-look-how-you-want-overlay-editor) (2–5 s feels
> right) so the overlay and the Duck line up.

---

## 13. Start everything automatically with OBS

One-time setup so that **opening OBS starts CHAT CONNECT + the Duck in the
background, and closing OBS stops them**. No more launching three programs.

1. Make sure you ran `install.bat` once in `CHAT_CONNECT` **and** in
   `CHAT_YAPPER` (sections 3 and 12).
2. In OBS, open **Tools → Scripts**.
3. Click the **+** button (bottom left of the Scripts window).
4. Browse into your `CHAT_CONNECT` folder and select
   **`obs_autolaunch.lua`** → **Open**.
5. Done. The script panel shows three checkboxes (all on by default):
   - *Start CHAT CONNECT with OBS*
   - *Start CHAT YAPPER (duck TTS) with OBS*
   - *Stop them when OBS closes*
   plus a **(Re)start the tools now** button — click it to start everything
   immediately without restarting OBS.

From now on: open OBS → within a few seconds the dashboard
(`http://localhost:2428`) is up, your channels auto-connect (they're
remembered), the overlay browser source fills up, and the Duck starts
quacking once your chat is live. Close OBS → everything shuts down again.

Notes:

- Both tools are **safe against double-starts** — if something is already
  running, the extra copy just exits. You can still use `run.bat` manually
  whenever you want.
- In background mode the logs go to `CHAT_CONNECT/server.log` and
  `CHAT_YAPPER/yapper.log` (handy for [troubleshooting](#15-troubleshooting)).
- To stop the tools manually while OBS stays open: dashboard **⏻ Stop
  server** button or `CHAT_CONNECT/stop.bat` — the Duck follows the server
  down automatically when it was started by OBS. There's also
  `CHAT_YAPPER/stop.bat` to stop only the Duck.

---

## 14. Optional: official YouTube API key

Skip this section unless automatic mode stops working or you explicitly want
to use Google's official API. Differences: the official API is stable and
supported by Google, but it has a **daily quota** — with default quota it
supports roughly 6–8 hours of chat reading per day, resetting at midnight
Pacific time.

Get a free API key (no billing/credit card needed):

1. Go to <https://console.cloud.google.com/> and log in with any Google
   account.
2. Top bar → project selector → **New project** → name it e.g.
   `chat-connect` → **Create** → make sure it's selected.
3. Menu (☰) → **APIs & Services** → **Library** → search
   **"YouTube Data API v3"** → click it → **Enable**.
4. Menu (☰) → **APIs & Services** → **Credentials** → **+ Create
   credentials** → **API key**. Copy the key (looks like `AIzaSy...`).
5. (Recommended) click **Edit API key** → under **API restrictions** choose
   **Restrict key** → tick only *YouTube Data API v3* → **Save**.

Then on the CHAT CONNECT dashboard: paste the key into the **API key** box of
the YouTube card, keep your `@handle` or video link in the first box, and click
**Connect**. With a key present, CHAT CONNECT automatically uses the official
API. Remove the key and reconnect to go back to automatic mode.

The key is stored only on your PC, in `CHAT_CONNECT/config.json` (which is
git-ignored — it never gets uploaded anywhere).

---

## 15. Troubleshooting

**Double-clicking `install.bat` flashes and closes / says Python not found**
→ Python isn't installed or isn't on PATH. Redo [section 1](#1-install-python-one-time)
and this time tick **"Add python.exe to PATH"**. Then run `install.bat` again.

**`run.bat` says "Could not open http://127.0.0.1:2428 … already running?"**
→ CHAT CONNECT is already running (background mode, or OBS auto-launched it).
Just open `http://localhost:2428`. To restart it, run `stop.bat` first.
If it's genuinely something else using port 2428, start on another port:
open `cmd` in the folder and run `.venv\Scripts\python main.py --port 2429`
(then use `2429` in every URL of this guide).

**Dashboard says "server offline — retrying…"**
→ The server window was closed. Start `run.bat` again; the page reconnects by
itself.

**Twitch stays "connecting" forever**
→ Check your internet, a firewall/antivirus blocking Python, or a typo'd
channel name. The channel name is only the part after `twitch.tv/` — no `#`,
no spaces, no capital letters needed.

**Twitch connects but no messages appear**
→ 99% a typo in the channel name (Twitch doesn't error on non-existent chat
rooms). Disconnect, retype, Connect again. Then write a message in your chat
on twitch.tv — watching someone else's silent chat also *looks* broken.

**YouTube says "channel is not live right now"**
→ Normal when you're offline: with an `@handle` it waits and auto-connects
when you go live. If you ARE live: double-check the handle spelling (open
`youtube.com/@yourhandle/live` in a browser — it must land on your live
video). Note: with a `@handle` your stream must be **public** (unlisted
streams are only found via their direct video link).

**YouTube says "no active live chat on this video"**
→ The video isn't live (ended VOD or normal upload), or chat is disabled /
members-only in YouTube Studio, or the stream is age-restricted. Fix it in
YouTube Studio → your live's settings → Live chat.

**YouTube worked, then "chat lost … reconnecting"**
→ Usually a hiccup; it repairs itself. If it loops forever, YouTube may have
changed their internal format — use the API key mode
([section 14](#14-optional-official-youtube-api-key)) and open an issue.

**Overlay is empty in OBS**
→ Is the server running? Does `http://localhost:2428/overlay` show messages in
a normal browser when you press **Send test message**? If browser yes / OBS no:
right-click the browser source → **Properties** → check the URL for typos →
click **Refresh cache of current page**. Also make sure OBS runs on the same
PC as CHAT CONNECT (otherwise see next point).

**I changed the style in the editor but OBS still shows the old look**
→ Did you press **💾 Save & apply**? Changes preview live in the editor but
only reach OBS when saved. Also check the browser source URL has no leftover
options like `?size=…` — URL options override the saved style on purpose.

**Emotes show as text like `:_fireHype:` or `french210Love`**
→ Twitch/YouTube's own emotes display as images automatically. Third-party
emotes (BTTV, FFZ, 7TV) are not supported yet and stay text. If even normal
emotes show as text, the browser source may be blocked from the internet
(images load from Twitch/YouTube's servers).

**Auto-launch with OBS doesn't start anything**
→ Check the Scripts window (Tools → Scripts): select `obs_autolaunch.lua` and
look at the **Script Log** button output. The usual causes: `install.bat` was
never run in one of the two folders, or the repo was moved after adding the
script (remove it with **−** and re-add it from the new location). Then check
`CHAT_CONNECT/server.log` and `CHAT_YAPPER/yapper.log`.

**OBS runs on a different PC (or you use a phone as a second screen)**
→ By default CHAT CONNECT only listens on the PC it runs on (safer). To open
it to your network: `.venv\Scripts\python main.py --host 0.0.0.0`, allow it in
the Windows Firewall popup, and use `http://THE-PC-IP:2428/...` from the other
device. Only do this on a network you trust — anyone on it can then see the
dashboard.

**The Duck says "CHAT CONNECT is not running"**
→ Start order: CHAT CONNECT first. The Duck retries every 5 s, so just start
CHAT CONNECT and wait — no restart needed. (Or use
[section 13](#13-start-everything-automatically-with-obs) so order never
matters again.)

**I want a clean slate**
→ Stop the server and delete `CHAT_CONNECT/config.json`. All saved channels,
the API key and the overlay style are gone.

---

## 16. FAQ

**Do I need to be a Twitch/YouTube "developer" or register an app?**
No. Twitch chat is read anonymously; YouTube automatic mode uses no key at
all. The optional YouTube API key is a 5-minute free setup, only if you want it.

**Can it send/answer messages in chat?**
No — CHAT CONNECT is read-only by design. Nothing can post as you, ban anyone,
or touch your account, because it never has any of your credentials.

**Are emotes and emojis shown?**
Yes. Normal emojis (😍🔥) display everywhere, Twitch channel/global emotes and
YouTube channel emotes display as images in the overlay and dashboard, and
they are stripped from `message_clean` so the Duck doesn't try to pronounce
them. Third-party emotes (BTTV/FFZ/7TV) are not supported yet.

**Does it see who subscribed / raids / channel points?**
Not yet — it reads chat messages (including YouTube Super Chats). Events like
raids/subs could be added later.

**How much delay does it add?**
Twitch: well under a second. YouTube: about 1–5 seconds (that's how YouTube
serves chat, same as the website). You can add extra display delay on purpose
in the [overlay editor](#9-make-it-look-how-you-want-overlay-editor) to sync
with the Duck's voice.

**Is my API key / config uploaded anywhere?**
No. Everything runs and stays on your PC. `config.json` is in `.gitignore`,
so even committing/pushing the repo won't include it.

**Can two tools read the chat at the same time?**
Yes, as many as you want — dashboard, overlay, Duck, your own scripts, all
simultaneously.

"""CHAT YAPPER - the Duck that reads chat out loud in OBS.

The Duck gets its messages from CHAT CONNECT (../CHAT_CONNECT), which merges
Twitch AND YouTube live chat into one local stream:

    1. start CHAT_CONNECT  (run.bat there)  and connect your channels
    2. start OBS           (websocket server enabled, port 4455)
    3. start this          (run.bat here)   -> the duck reads BOTH chats

Nothing stays silent when it breaks:
  * startup checks verify Python packages, OBS, the OBS sources and the voice
  * real problems open a Windows pop-up, even in hidden background mode
  * live status is reported to the CHAT CONNECT dashboard (Duck card)
  * everything is also written to the console / yapper.log

Optional .env: ELEVENLABS_API_KEY and/or KEY_OPENAI for AI voices; without
any key the Duck falls back to Windows' built-in voice (then pyttsx3).
Emotes AND emojis are stripped before speaking - emoji-only spam is skipped.
"""

import asyncio
import json
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
import wave
import zlib

script_path = os.path.dirname(os.path.abspath(__file__))

# Under pythonw.exe (background mode) there is no console: print() would
# crash, so route all output to yapper.log instead.
if sys.stdout is None or sys.stderr is None:
    _logfile = open(f"{script_path}/yapper.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or _logfile
    sys.stderr = sys.stderr or _logfile


# ------------------------------------------------------- visible error popups

def _msgbox(message, title, flags):
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, message, title, flags)


def warn_popup(message):
    """Non-blocking Windows pop-up; the Duck keeps running."""
    print("!! " + message.replace("\n", " "))
    if os.name == "nt":
        try:  # 0x30 warning icon, 0x10000 foreground, 0x40000 topmost
            threading.Thread(target=_msgbox, args=(message, "CHAT YAPPER", 0x50030),
                             daemon=True).start()
        except Exception:
            pass


def fatal(message):
    """Blocking pop-up + exit: for problems the Duck cannot run with."""
    print("!! FATAL: " + message.replace("\n", " "))
    if os.name == "nt":
        try:  # 0x10 error icon
            _msgbox(message, "CHAT YAPPER - cannot start", 0x50010)
        except Exception:
            pass
    sys.exit(1)


try:
    import aiohttp
    from dotenv import load_dotenv
    import obsws_python as obs
except ModuleNotFoundError as e:
    fatal(f"The Python package '{e.name}' is missing.\n\n"
          "Run install.bat in the CHAT_YAPPER folder once, then start it again.")

load_dotenv()

# ---------------------------------------------------------------- settings

CHAT_CONNECT_WS = os.getenv("CHAT_CONNECT_URL", "ws://127.0.0.1:2428/ws")
KEY_OPENAI = os.getenv("KEY_OPENAI")

# ElevenLabs (optional): set ELEVENLABS_API_KEY in .env to use their voices.
KEY_ELEVENLABS = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")
# Premade voices every ElevenLabs account has; override with your own ids
# via ELEVENLABS_VOICE_IDS=id1,id2 - or simply pick voices on the CHAT
# CONNECT dashboard (Duck card), which saves to voices.json and wins.
ELEVENLABS_VOICES = [v.strip() for v in os.getenv(
    "ELEVENLABS_VOICE_IDS",
    "21m00Tcm4TlvDq8ikWAM,pNInz6obpgDQGcFmaJgB,ErXwobaYiN019PkySvjV,"
    "EXAVITQu4vr4xnSDxMaL,TxGEqnHWrfWFTfGW9XjX,MF3mGyEYCl7XYWbV9V6O"
).split(",") if v.strip()]
DEFAULT_ELEVEN_VOICES = list(ELEVENLABS_VOICES)
VOICES_FILE = f"{script_path}/voices.json"
VOICE_CATALOG = []        # fetched from ElevenLabs: [{"id","name","desc","preview_url"}]
REPORT_NOW = None         # asyncio.Event set to push a status update immediately

OBS_HOST = os.getenv("OBS_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")

# Messages waiting to be spoken; beyond this the oldest are dropped so the
# Duck never lags minutes behind a busy chat. Override with TTS_QUEUE_SIZE.
MAX_QUEUE = max(1, int(os.getenv("TTS_QUEUE_SIZE", "10")))
MAX_CHARS = 1000       # safety limit per message

QUEUE = None           # the speak queue (set in main, watched by the reporter)
DROPPED = 0            # messages skipped because the queue was full

TTS_FILE = f"{script_path}/tts.wav"
EMPTY_FILE = f"{script_path}/tts_empty.wav"

# OBS source names (create these in OBS, see README.md):
SRC_MEDIA = "PYTHON_TTS"       # media source that plays tts.wav
SRC_AUTHOR = "PYTHON_AUTHOR"   # text source showing who is talking
SRC_GROUP = "CHAT_YAPPING"     # group/scene item with the duck + text

TEXT_FILE = f"{script_path}/tts_text.txt"

# Follow mode (set by the OBS auto-launcher): once CHAT CONNECT has been
# seen alive, exit when it goes away instead of retrying forever - closing
# OBS then cleans up the Duck automatically.
EXIT_WITH_SERVER = (os.getenv("CHAT_YAPPER_EXIT_WITH_SERVER", "") == "1"
                    or "--exit-with-server" in sys.argv)

# Single-instance lock: holding this port claims "the Duck is running".
# A second copy (e.g. OBS autolaunch while it's already up) exits quietly.
LOCK_PORT = int(os.getenv("CHAT_YAPPER_LOCK_PORT", "2430"))


def acquire_single_instance_lock():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
        lock.listen(1)
        return lock
    except OSError:
        print(f"-- CHAT YAPPER is already running (lock port {LOCK_PORT} busy) - bye")
        sys.exit(0)


# ------------------------------------------------- live status for the hub

# The Duck's health, combined into one status line that is printed, kept
# up to date on the CHAT CONNECT dashboard, and easy to reason about.
COMP = {"obs": "down", "sources": "", "chat": "down", "last_error": ""}
STATUS = {"state": "starting", "detail": ""}
_warned = set()


def refresh_status():
    voice = f"voice: {VOICE_LABEL}"
    if COMP["obs"] != "ok":
        state, detail = "waiting-obs", ("waiting for OBS - enable Tools > WebSocket "
                                        f"Server Settings (port {OBS_PORT})")
    elif COMP["sources"]:
        state, detail = "error", COMP["sources"]
    elif VOICE_LABEL == "no working voice":
        state, detail = "error", ("no TTS voice works - re-run install.bat "
                                  "(see yapper.log for details)")
    elif COMP["chat"] != "ok":
        state, detail = "ready", f"OBS ok - waiting for CHAT CONNECT · {voice}"
    else:
        state = "connected"
        detail = f"reading Twitch + YouTube · {voice}"
        if COMP["last_error"]:
            detail += f" · last problem: {COMP['last_error']}"
    if (STATUS["state"], STATUS["detail"]) != (state, detail):
        print(f"-- [{state}] {detail}")
    STATUS["state"], STATUS["detail"] = state, detail


def warn_once(key, message, show_popup=False):
    if key in _warned:
        return
    _warned.add(key)
    if show_popup:
        warn_popup(message)
    else:
        print("!! " + message)


def http_base(ws_url: str) -> str:
    base = ws_url.replace("wss://", "https://").replace("ws://", "http://")
    return base[:-3] if base.endswith("/ws") else base


async def status_reporter():
    """Tell the CHAT CONNECT dashboard how the Duck is doing, every few seconds."""
    url = http_base(CHAT_CONNECT_WS) + "/api/tool-status"
    async with aiohttp.ClientSession() as session:
        while True:
            detail = STATUS["detail"]
            if QUEUE is not None and STATUS["state"] == "connected":
                waiting = QUEUE.qsize()
                if waiting:
                    detail += f" · {waiting} message{'s' if waiting > 1 else ''} in queue"
                if DROPPED:
                    detail += f" · {DROPPED} skipped in spam"
            payload = {"tool": "yapper", "state": STATUS["state"], "detail": detail}
            if VOICE_CATALOG:
                payload["extra"] = {"voices": VOICE_CATALOG,
                                    "selected": ELEVENLABS_VOICES,
                                    "defaults": DEFAULT_ELEVEN_VOICES}
            try:
                await session.post(url, json=payload,
                                   timeout=aiohttp.ClientTimeout(total=4))
            except Exception:
                pass  # hub not up - the chat listener already handles retrying
            try:  # wait 8s, but wake instantly when something changed
                await asyncio.wait_for(REPORT_NOW.wait(), timeout=8)
                REPORT_NOW.clear()
            except asyncio.TimeoutError:
                pass


# ------------------------------------------------------------------- OBS

CLIENT = None


def obs_connect_blocking():
    """Keep trying until OBS is reachable (so start order doesn't matter)."""
    global CLIENT
    COMP["obs"] = "down"
    refresh_status()
    while CLIENT is None:
        try:
            CLIENT = obs.ReqClient(host=OBS_HOST, port=OBS_PORT,
                                   password=OBS_PASSWORD, timeout=3)
        except Exception:
            time.sleep(5)
    COMP["obs"] = "ok"
    refresh_status()
    print("-- OBS connected")


def obs_activate(scene, item_name, enable):
    scene_items = CLIENT.get_scene_item_list(scene).scene_items
    for item in scene_items:
        if item["sourceName"] == item_name:
            CLIENT.set_scene_item_enabled(scene, item["sceneItemId"], enable)
            break


def obs_setInput(item, parm, value):
    CLIENT.set_input_settings(name=item, settings={parm: value}, overlay=True)


def obs_getCurrentScene():
    return CLIENT.get_current_program_scene().scene_name


def check_obs_sources():
    """Verify the OBS setup the Duck needs. Returns a list of problems."""
    problems = []
    try:
        inputs = {i["inputName"] for i in CLIENT.get_input_list().inputs}
        for name in (SRC_MEDIA, SRC_AUTHOR):
            if name not in inputs:
                problems.append(f"OBS is missing a source named '{name}'")
        scene = obs_getCurrentScene()
        items = {i["sourceName"] for i in CLIENT.get_scene_item_list(scene).scene_items}
        if SRC_GROUP not in items:
            problems.append(f"group '{SRC_GROUP}' is not in the current scene '{scene}'")
    except Exception as e:
        problems.append(f"could not inspect OBS sources ({e})")
    return problems


def run_source_check(startup=False):
    problems = check_obs_sources()
    COMP["sources"] = " · ".join(problems)
    refresh_status()
    if problems and startup:
        warn_once("obs-sources",
                  "The Duck connected to OBS but can't display there yet:\n\n- "
                  + "\n- ".join(problems)
                  + "\n\nCreate/rename these in OBS (names must match exactly, "
                  "see CHAT_YAPPER/README.md).\nThe Duck keeps running and "
                  "rechecks every 30 seconds.",
                  show_popup=True)
    return problems


async def source_recheck_loop():
    """While sources are missing, look again every 30s and recover silently."""
    loop = asyncio.get_running_loop()
    while True:
        await asyncio.sleep(30)
        if COMP["obs"] == "ok" and COMP["sources"]:
            await loop.run_in_executor(None, run_source_check)
            if not COMP["sources"]:
                print("-- OBS sources found - the Duck is fully operational")


def ensure_empty_wav():
    """The media source rests on a silent wav; recreate it if it's gone."""
    if os.path.exists(EMPTY_FILE):
        return
    with wave.open(EMPTY_FILE, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 2400)
    print("-- created missing tts_empty.wav")


# ------------------------------------------------------------------- TTS
#
# Voice engines in fallback order. If one breaks (bad key, broken package)
# the Duck moves to the next one and keeps talking:
#   1. ElevenLabs              (only if ELEVENLABS_API_KEY is set)
#   2. OpenAI voices           (only if KEY_OPENAI is set)
#   3. Windows built-in voice  (PowerShell System.Speech - needs NO packages)
#   4. pyttsx3                 (last resort, non-Windows offline voice)

def pick_voice(pool, voice_key):
    """Same chatter -> same voice, stable across restarts.

    Uses crc32 (NOT Python's hash(), which changes every run) of the user's
    platform id, modulo the voice pool. No key -> random pick.
    """
    if not pool:
        return None
    if not voice_key:
        return random.choice(pool)
    return pool[zlib.crc32(voice_key.encode("utf-8")) % len(pool)]


def tts_elevenlabs(text, voice_key=""):
    """ElevenLabs TTS through their plain REST API - no extra packages."""
    import urllib.error
    import urllib.request

    voice = pick_voice(ELEVENLABS_VOICES, voice_key)
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
           f"?output_format=pcm_24000")
    body = json.dumps({"text": text, "model_id": ELEVENLABS_MODEL}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "xi-api-key": KEY_ELEVENLABS,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            pcm = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"ElevenLabs HTTP {e.code}: {detail}") from None
    if len(pcm) < 200:
        raise RuntimeError("ElevenLabs returned no audio")
    with wave.open(TTS_FILE, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)


def tts_openai(text, voice_key=""):
    from openai import OpenAI

    voices = ["alloy", "ash", "ballad", "coral", "echo",
              "fable", "nova", "onyx", "sage", "shimmer"]
    instructions = [
        "Speak in a cheerful and positive tone.",
        "Speak as a pirate captain, with a commanding and adventurous tone.",
        "Speak as a wise old sage, with a calm and thoughtful tone.",
        "Speak as a friendly robot, with a jerky rhythm and a mechanical tone.",
        "Speak as a dramatic storyteller, with a deep and engaging tone.",
        "Extremely excited as if you were about to explode.",
    ]

    client = OpenAI(api_key=KEY_OPENAI)
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=pick_voice(voices, voice_key),      # stable per chatter
        input=text,
        instructions=random.choice(instructions), # the mood still varies
        response_format="wav",
    ) as response:
        response.stream_to_file(TTS_FILE)


def tts_windows(text, voice_key=""):
    """Windows' built-in voice via PowerShell. No Python packages, no DLLs."""
    with open(TEXT_FILE, "w", encoding="utf-8-sig") as f:
        f.write(text)
    ps_text = TEXT_FILE.replace("'", "''")
    ps_wav = TTS_FILE.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        f"$t = Get-Content -Raw -Encoding UTF8 '{ps_text}'; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{ps_wav}'); "
        "$s.Speak($t); $s.Dispose()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True, timeout=60,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def tts_pyttsx3(text, voice_key=""):
    import pyttsx3
    engine = pyttsx3.init()
    engine.save_to_file(text, TTS_FILE)
    engine.runAndWait()
    engine.stop()


VOICE_HINTS = {
    "elevenlabs": ("check ELEVENLABS_API_KEY in CHAT_YAPPER/.env "
                   "(or your ElevenLabs character quota)"),
    "openai": ("check KEY_OPENAI in CHAT_YAPPER/.env; if the error mentions a "
               "missing module, re-run install.bat (it repairs itself)"),
    "windows": "PowerShell / System.Speech is unavailable on this PC",
    "pyttsx3": "re-run install.bat",
}

VOICE_CHAIN = []          # [(name, label, function)] built at startup
ACTIVE_VOICE = None       # index into VOICE_CHAIN, None = nothing works
VOICE_LABEL = "checking..."


# ------------------------------------ ElevenLabs voice picking (dashboard)

def load_saved_voices():
    """voices.json (written by the dashboard picker) beats the .env list."""
    global ELEVENLABS_VOICES
    try:
        with open(VOICES_FILE, encoding="utf-8") as f:
            ids = [v for v in json.load(f).get("voices", []) if isinstance(v, str)]
        if ids:
            ELEVENLABS_VOICES = ids
            print(f"-- using {len(ids)} ElevenLabs voice(s) picked on the dashboard")
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        print(f"!! voices.json unreadable ({e}) - using the default voices")


def save_voices(ids):
    global ELEVENLABS_VOICES
    ELEVENLABS_VOICES = ids or list(DEFAULT_ELEVEN_VOICES)
    try:
        with open(VOICES_FILE, "w", encoding="utf-8") as f:
            json.dump({"voices": ids}, f, indent=2)
    except OSError as e:
        print(f"!! could not save voices.json: {e}")


def fetch_voice_catalog():
    """Ask ElevenLabs which voices this account can use (for the dashboard)."""
    global VOICE_CATALOG
    if not KEY_ELEVENLABS:
        return
    import urllib.request
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices",
                                 headers={"xi-api-key": KEY_ELEVENLABS})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        catalog = []
        for v in data.get("voices", [])[:80]:
            labels = v.get("labels") or {}
            desc = " · ".join(str(x) for x in (
                labels.get("gender"), labels.get("accent"), labels.get("age"),
                labels.get("descriptive") or labels.get("description")) if x)
            if v.get("voice_id") and v.get("name"):
                catalog.append({"id": v["voice_id"], "name": v["name"],
                                "desc": desc, "preview_url": v.get("preview_url") or ""})
        VOICE_CATALOG = catalog
        print(f"-- ElevenLabs: {len(catalog)} voices available - "
              "pick your set on the dashboard (Duck card)")
    except Exception as e:
        print(f"!! could not fetch the ElevenLabs voice list ({e})")


def handle_command(cmd: dict):
    """Commands sent from the dashboard through CHAT CONNECT."""
    if cmd.get("action") == "set_voices":
        ids = [v for v in cmd.get("voices", []) if isinstance(v, str)][:40]
        known = {c["id"] for c in VOICE_CATALOG}
        if known:
            ids = [v for v in ids if v in known]
        save_voices(ids)
        print(f"-- voice selection updated from the dashboard: "
              f"{len(ids) if ids else 'default'} voice(s)")
        if REPORT_NOW:
            REPORT_NOW.set()


def build_voice_chain():
    global VOICE_CHAIN
    VOICE_CHAIN = []
    if KEY_ELEVENLABS:
        VOICE_CHAIN.append(("elevenlabs", "ElevenLabs voices", tts_elevenlabs))
    if KEY_OPENAI:
        VOICE_CHAIN.append(("openai", "OpenAI voices", tts_openai))
    if os.name == "nt":
        VOICE_CHAIN.append(("windows", "Windows voice", tts_windows))
    VOICE_CHAIN.append(("pyttsx3", "offline voice (pyttsx3)", tts_pyttsx3))
    if not (KEY_ELEVENLABS or KEY_OPENAI):
        print("-- no ELEVENLABS_API_KEY / KEY_OPENAI in .env - using the free "
              "voice (add a key for the fancy AI voices)")


def preflight_voices():
    """Try the engines with a tiny text so problems show at STARTUP,
    not on the first chat message."""
    global ACTIVE_VOICE, VOICE_LABEL
    for i, (name, label, fn) in enumerate(VOICE_CHAIN):
        try:
            fn("ready")
            ACTIVE_VOICE = i
            VOICE_LABEL = label
            print(f"-- voice check ok: {label}")
            refresh_status()
            return
        except Exception as e:
            warn_once(f"voice-{name}",
                      f"{label} is not working ({type(e).__name__}: {e}) - "
                      + VOICE_HINTS.get(name, ""))
    ACTIVE_VOICE = None
    VOICE_LABEL = "no working voice"
    refresh_status()
    warn_once("voice-none",
              "The Duck cannot speak: no voice engine works on this PC.\n\n"
              "Re-run install.bat in the CHAT_YAPPER folder, then start it "
              "again. Details are in yapper.log.",
              show_popup=True)


def make_tts(text, voice_key="") -> bool:
    """Generate tts.wav. Returns False when no engine could produce audio."""
    global ACTIVE_VOICE, VOICE_LABEL
    if ACTIVE_VOICE is None:
        return False
    for i in range(ACTIVE_VOICE, len(VOICE_CHAIN)):
        name, label, fn = VOICE_CHAIN[i]
        try:
            fn(text, voice_key)
            if i != ACTIVE_VOICE:      # an engine died mid-run: stay on this one
                ACTIVE_VOICE = i
                VOICE_LABEL = label
                COMP["last_error"] = f"switched to {label}"
                refresh_status()
            return True
        except Exception as e:
            warn_once(f"voice-{name}",
                      f"{label} failed ({type(e).__name__}: {e}) - "
                      + VOICE_HINTS.get(name, "") + " · trying the next voice")
    ACTIVE_VOICE = None
    VOICE_LABEL = "no working voice"
    refresh_status()
    warn_once("voice-none",
              "The Duck cannot speak anymore: every voice engine failed.\n\n"
              "Re-run install.bat in the CHAT_YAPPER folder. Details in yapper.log.",
              show_popup=True)
    return False


def audio_duration():
    try:
        with wave.open(TTS_FILE, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception as e:
        print(f"!! could not read audio duration: {e}")
        return 0


# ------------------------------------------------------------- the show

def show_tts(message, author, voice_key=""):
    """Generate the voice, pop the duck in OBS, play it, hide the duck."""
    if not make_tts(message, voice_key):
        return
    current_scene = obs_getCurrentScene()
    duration = audio_duration()

    obs_setInput(SRC_MEDIA, "local_file", TTS_FILE)
    obs_activate(current_scene, SRC_MEDIA, False)
    obs_setInput(SRC_AUTHOR, "text", author)

    obs_activate(current_scene, SRC_GROUP, True)
    CLIENT.set_input_mute(SRC_MEDIA, False)

    time.sleep(duration + 0.2)

    obs_activate(current_scene, SRC_GROUP, False)
    CLIENT.set_input_mute(SRC_MEDIA, True)

    obs_setInput(SRC_MEDIA, "local_file", EMPTY_FILE)


PLATFORM_LABEL = {"twitch": "Twitch", "youtube": "YouTube"}

# Emojis / pictographs: covers emoticons, symbols, flags, dingbats, stars,
# clocks, skin tones, ZWJ sequences and keycaps. The Duck skips them so
# "🔥🔥🔥🔥" doesn't get read out loud (emoji-only messages are skipped).
EMOJI_RE = re.compile(
    "[\u200d\u20e3\ufe0e\ufe0f"      # ZWJ, keycap, variation selectors
    "\u2300-\u23ff"                    # technical: clocks, play buttons
    "\u2600-\u27bf"                    # misc symbols + dingbats
    "\u2b00-\u2bff"                    # stars, squares
    "\U0001F000-\U0001FAFF]+"          # all main emoji blocks + flags
)


def strip_emoji(text: str) -> str:
    return " ".join(EMOJI_RE.sub(" ", text).split())


def speak_message(msg: dict):
    # message_clean = text with emote codes stripped; emojis go too -> pure
    # speakable text for the TTS
    text = (msg.get("message_clean") or msg.get("message") or "")
    text = strip_emoji(text)[:MAX_CHARS].strip()
    if not text:
        return
    author = msg.get("author", "someone")
    platform = PLATFORM_LABEL.get(msg.get("platform"), "")
    label = f"{author} · {platform}" if platform else author
    # stable per-chatter voice: platform user id survives display-name changes
    voice_key = msg.get("author_id") or msg.get("author") or ""
    print(f'[{msg.get("platform", "?"):^7}] {author}: {text}')
    try:
        show_tts(text, label, voice_key)
        if COMP["last_error"] and "OpenAI" not in COMP["last_error"]:
            COMP["last_error"] = ""
            refresh_status()
    except Exception as e:
        COMP["last_error"] = f"OBS error while playing ({e})"
        print(f"!! OBS error while playing message: {e} - reconnecting to OBS")
        global CLIENT
        CLIENT = None
        obs_connect_blocking()


# ------------------------------------------- CHAT CONNECT stream consumer

async def speaker_worker(queue: asyncio.Queue):
    loop = asyncio.get_running_loop()
    while True:
        msg = await queue.get()
        await loop.run_in_executor(None, speak_message, msg)


async def listen_chat_connect(queue: asyncio.Queue):
    global DROPPED
    ever_connected = False
    misses = 0
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(CHAT_CONNECT_WS, heartbeat=25) as ws:
                    print(f"-- connected to CHAT CONNECT ({CHAT_CONNECT_WS})")
                    print("-- the duck now reads Twitch + YouTube. Quack.")
                    ever_connected = True
                    misses = 0
                    COMP["chat"] = "ok"
                    refresh_status()
                    async for frame in ws:
                        if frame.type != aiohttp.WSMsgType.TEXT:
                            continue
                        event = json.loads(frame.data)
                        if event.get("type") == "command":
                            data = event.get("data") or {}
                            if data.get("tool") == "yapper":
                                handle_command(data)
                            continue
                        # "hello" carries old history - never read that aloud.
                        if event.get("type") != "chat":
                            continue
                        if queue.full():          # chat spam: drop the oldest
                            queue.get_nowait()
                            DROPPED += 1
                        queue.put_nowait(event["data"])
            print("-- CHAT CONNECT closed the connection, retrying in 5s")
        except aiohttp.ClientError:
            print("-- CHAT CONNECT is not running - start CHAT_CONNECT/run.bat "
                  "(retrying in 5s)")
        COMP["chat"] = "down"
        refresh_status()
        misses += 1
        if EXIT_WITH_SERVER and ever_connected and misses >= 3:
            print("-- CHAT CONNECT stopped and follow mode is on - bye")
            os._exit(0)   # hard exit: a TTS worker thread may be mid-sleep
        await asyncio.sleep(5)


async def main():
    global REPORT_NOW
    REPORT_NOW = asyncio.Event()
    ensure_empty_wav()
    load_saved_voices()
    build_voice_chain()
    refresh_status()
    asyncio.create_task(status_reporter())
    asyncio.create_task(source_recheck_loop())
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, preflight_voices)
    await loop.run_in_executor(None, fetch_voice_catalog)
    REPORT_NOW.set()
    await loop.run_in_executor(None, obs_connect_blocking)
    await loop.run_in_executor(None, run_source_check, True)
    global QUEUE
    QUEUE = asyncio.Queue(maxsize=MAX_QUEUE)
    await asyncio.gather(listen_chat_connect(QUEUE), speaker_worker(QUEUE))


if __name__ == "__main__":
    _instance_lock = acquire_single_instance_lock()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCHAT YAPPER stopped.")

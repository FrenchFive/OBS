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

Optional .env: KEY_OPENAI for the fancy OpenAI voices (falls back to the free
offline pyttsx3 voice without it).
"""

import asyncio
import json
import os
import random
import socket
import sys
import threading
import time
import wave

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

OBS_HOST = os.getenv("OBS_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")

MAX_QUEUE = 5          # messages waiting to be spoken; oldest dropped beyond this
MAX_CHARS = 1000       # safety limit per message

TTS_FILE = f"{script_path}/tts.wav"
EMPTY_FILE = f"{script_path}/tts_empty.wav"

# OBS source names (create these in OBS, see README.md):
SRC_MEDIA = "PYTHON_TTS"       # media source that plays tts.wav
SRC_AUTHOR = "PYTHON_AUTHOR"   # text source showing who is talking
SRC_GROUP = "CHAT_YAPPING"     # group/scene item with the duck + text

VOICE_MODE = "OpenAI voices" if KEY_OPENAI else "offline voice (no KEY_OPENAI in .env)"

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
    if COMP["obs"] != "ok":
        state, detail = "waiting-obs", ("waiting for OBS - enable Tools > WebSocket "
                                        f"Server Settings (port {OBS_PORT})")
    elif COMP["sources"]:
        state, detail = "error", COMP["sources"]
    elif COMP["chat"] != "ok":
        state, detail = "ready", f"OBS ok - waiting for CHAT CONNECT · {VOICE_MODE}"
    else:
        state = "connected"
        detail = f"reading Twitch + YouTube · {VOICE_MODE}"
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
            try:
                await session.post(url, json={"tool": "yapper", **STATUS},
                                   timeout=aiohttp.ClientTimeout(total=4))
            except Exception:
                pass  # hub not up - the chat listener already handles retrying
            await asyncio.sleep(8)


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

def tts_pyttsx3(text):
    import pyttsx3
    engine = pyttsx3.init()
    engine.save_to_file(text, TTS_FILE)
    engine.runAndWait()
    engine.stop()


def tts_openai(text):
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
        voice=random.choice(voices),
        input=text,
        instructions=random.choice(instructions),
        response_format="wav",
    ) as response:
        response.stream_to_file(TTS_FILE)


def make_tts(text) -> bool:
    """Generate tts.wav. Returns False when no engine could produce audio."""
    if KEY_OPENAI:
        try:
            tts_openai(text)
            return True
        except Exception as e:
            COMP["last_error"] = "OpenAI TTS failed - using the offline voice"
            refresh_status()
            warn_once("openai-tts",
                      f"OpenAI TTS failed ({e}).\n\nCheck KEY_OPENAI in "
                      "CHAT_YAPPER/.env - the Duck uses the offline voice for now.")
    try:
        tts_pyttsx3(text)
        return True
    except Exception as e:
        COMP["last_error"] = f"no TTS voice works ({e})"
        refresh_status()
        warn_once("pyttsx3",
                  f"The offline voice failed too ({e}).\n\n"
                  "The Duck can't speak at all - re-run install.bat.",
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

def show_tts(message, author):
    """Generate the voice, pop the duck in OBS, play it, hide the duck."""
    if not make_tts(message):
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


def speak_message(msg: dict):
    # message_clean = text with emotes/emoji-codes stripped -> best for TTS
    text = (msg.get("message_clean") or msg.get("message") or "")[:MAX_CHARS].strip()
    if not text:
        return
    author = msg.get("author", "someone")
    platform = PLATFORM_LABEL.get(msg.get("platform"), "")
    label = f"{author} · {platform}" if platform else author
    print(f'[{msg.get("platform", "?"):^7}] {author}: {text}')
    try:
        show_tts(text, label)
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
                        # "hello" carries old history - never read that aloud.
                        if event.get("type") != "chat":
                            continue
                        if queue.full():          # chat spam: drop the oldest
                            queue.get_nowait()
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
    ensure_empty_wav()
    refresh_status()
    asyncio.create_task(status_reporter())
    asyncio.create_task(source_recheck_loop())
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, obs_connect_blocking)
    await loop.run_in_executor(None, run_source_check, True)
    queue = asyncio.Queue(maxsize=MAX_QUEUE)
    await asyncio.gather(listen_chat_connect(queue), speaker_worker(queue))


if __name__ == "__main__":
    _instance_lock = acquire_single_instance_lock()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCHAT YAPPER stopped.")

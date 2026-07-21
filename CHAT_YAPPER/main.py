"""CHAT YAPPER - the Duck that reads chat out loud in OBS.

The Duck now gets its messages from CHAT CONNECT (../CHAT_CONNECT), which
merges Twitch AND YouTube live chat into one local stream. So:

    1. start CHAT_CONNECT  (run.bat there)  and connect your channels
    2. start OBS           (websocket server enabled, port 4455)
    3. start this          (run.bat here)   -> the duck reads BOTH chats

No Twitch/YouTube credentials are needed here anymore - CHAT CONNECT
handles the platforms. Optional .env: KEY_OPENAI for nicer OpenAI voices
(falls back to free offline pyttsx3 voices without it).
"""

import asyncio
import json
import os
import random
import socket
import sys
import time
import wave

script_path = os.path.dirname(os.path.abspath(__file__))

# Under pythonw.exe (background mode) there is no console: print() would
# crash, so route all output to yapper.log instead.
if sys.stdout is None or sys.stderr is None:
    _logfile = open(f"{script_path}/yapper.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or _logfile
    sys.stderr = sys.stderr or _logfile

import aiohttp
from dotenv import load_dotenv

import obsws_python as obs

load_dotenv()

# ---------------------------------------------------------------- settings

CHAT_CONNECT_WS = os.getenv("CHAT_CONNECT_URL", "ws://127.0.0.1:2428/ws")
KEY_OPENAI = os.getenv("KEY_OPENAI")

OBS_HOST = os.getenv("OBS_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")

MAX_QUEUE = 5          # messages waiting to be spoken; oldest dropped beyond this
MAX_CHARS = 1000       # safety limit per message

# Follow mode (set by autolaunch.bat / the OBS auto-launcher): once CHAT
# CONNECT has been seen alive, exit when it goes away instead of retrying
# forever - closing OBS then cleans up the Duck automatically.
EXIT_WITH_SERVER = os.getenv("CHAT_YAPPER_EXIT_WITH_SERVER", "") == "1"

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

TTS_FILE = f"{script_path}/tts.wav"
EMPTY_FILE = f"{script_path}/tts_empty.wav"

# OBS source names (create these in OBS, see README.md):
SRC_MEDIA = "PYTHON_TTS"       # media source that plays tts.wav
SRC_AUTHOR = "PYTHON_AUTHOR"   # text source showing who is talking
SRC_GROUP = "CHAT_YAPPING"     # group/scene item with the duck + text

# ------------------------------------------------------------------- OBS

CLIENT = None


def obs_connect_blocking():
    """Keep trying until OBS is reachable (so start order doesn't matter)."""
    global CLIENT
    while CLIENT is None:
        try:
            CLIENT = obs.ReqClient(host=OBS_HOST, port=OBS_PORT,
                                   password=OBS_PASSWORD, timeout=3)
            print("-- OBS connected")
        except Exception:
            print(f"-- waiting for OBS websocket on {OBS_HOST}:{OBS_PORT} "
                  "(OBS > Tools > WebSocket Server Settings) - retry in 5s")
            time.sleep(5)


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


def make_tts(text):
    if KEY_OPENAI:
        try:
            tts_openai(text)
            return
        except Exception as e:
            print(f"!! OpenAI TTS failed ({e}), falling back to pyttsx3")
    tts_pyttsx3(text)


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
    current_scene = obs_getCurrentScene()
    make_tts(message)
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
    except Exception as e:
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
        misses += 1
        if EXIT_WITH_SERVER and ever_connected and misses >= 3:
            print("-- CHAT CONNECT stopped and follow mode is on - bye")
            os._exit(0)   # hard exit: a TTS worker thread may be mid-sleep
        await asyncio.sleep(5)


async def main():
    obs_connect_blocking()
    queue = asyncio.Queue(maxsize=MAX_QUEUE)
    await asyncio.gather(listen_chat_connect(queue), speaker_worker(queue))


if __name__ == "__main__":
    _instance_lock = acquire_single_instance_lock()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCHAT YAPPER stopped.")

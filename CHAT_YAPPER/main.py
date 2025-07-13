import pyttsx3
import time
import os 
from dotenv import load_dotenv

from openai import OpenAI
import random

from pydub import AudioSegment

import obsws_python as obs
import json

from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
import asyncio

import wave

script_path = os.path.dirname(os.path.abspath(__file__))

load_dotenv()

APP_ID = os.getenv('TWITCH_ID')
APP_SECRET = os.getenv('TWITCH_SECRET')
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT]
TARGET_CHANNEL = 'french_five'
KEY_OPENAI = os.getenv("KEY_OPENAI")

CLIENT = obs.ReqClient(host='localhost', port=4455, password='', timeout=3)

TOKEN_FILE = script_path + '/token.json'

def tts(text):
    engine = pyttsx3.init()
    engine.save_to_file(text, f'{script_path}/tts.wav')
    engine.runAndWait()
    engine.stop()

def openai_tts(text):
    voices = [ 
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer"
    ]

    instructions = [
        "Speak in a cheerful and positive tone.",
        "Speak as a pirate captain, with a commanding and adventurous tone.",
        "Speak as a wise old sage, with a calm and thoughtful tone.",
        "Speak as a friendly robot, with a jerky rhythm and a mechanical tone.",
        "Speak as a dramatic storyteller, with a deep and engaging tone.",
        "Extremely excited as if you were about to explode."
    ]

    client = OpenAI(api_key=KEY_OPENAI)
    speech_file_path = f'{script_path}/tts.wav'

    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=random.choice(voices),
        input=text,
        instructions=random.choice(instructions),
        response_format="wav",
    ) as response:
        response.stream_to_file(speech_file_path)
    


def audio_duration():
    file_path = f'{script_path}/tts.wav'
    try:
        audio = AudioSegment.from_file(file_path)
        duration = len(audio) / 1000.0  # duration in seconds
        return duration
    except Exception as e:
        print(f"⚠️ Could not read audio duration: {e}")
        return 0


def obs_activate(scene, item_name, enable):
    cl = CLIENT

    scene_items  = cl.get_scene_item_list(scene).scene_items

    for item in scene_items:
        if item["sourceName"] == item_name:
            cl.set_scene_item_enabled(scene, item["sceneItemId"], enable)
            break

def obs_setInput(item, parm, file_path):
    cl = CLIENT

    # Set the input file for the TTS source
    cl.set_input_settings(
        name=item,
        settings={parm: file_path},
        overlay=True  # Keep other settings intact
    )

def obs_getCurrentScene():
    cl = CLIENT
    current_scene = cl.get_current_program_scene()

    return current_scene.scene_name


def show_tts(message, author):
    current_scene = obs_getCurrentScene()
    openai_tts(message)
    duration = audio_duration()
    print(f"Audio duration: {duration}")

    obs_setInput("PYTHON_TTS", "local_file", f'{script_path}/tts.wav')
    obs_activate(current_scene, "PYTHON_TTS", False)
    obs_setInput("PYTHON_AUTHOR", "text", author)
    
    obs_activate(current_scene, "CHAT_YAPPING", True)
    CLIENT.set_input_mute("PYTHON_TTS", False)
    
    time.sleep(duration + 0.2)

    obs_activate(current_scene, "CHAT_YAPPING", False)
    CLIENT.set_input_mute("PYTHON_TTS", True)

    obs_setInput("PYTHON_TTS", "local_file", f'{script_path}/tts_empty.wav')

def strip_emotes(text: str, emotes: dict) -> str:
    if not emotes:
        return text

    # Flatten the emote positions into a list of (start, end) tuples
    ranges = []
    for positions in emotes.values():
        for pos in positions:
            start = int(pos['start_position'])
            end = int(pos['end_position']) + 1  # +1 because string slicing is exclusive at the end
            ranges.append((start, end))

    # Sort ranges from last to first to avoid messing up indexes
    ranges.sort(reverse=True)

    # Remove the emotes from the text
    for start, end in ranges:
        text = text[:start] + text[end:]

    return ' '.join(text.split())  # Clean up any extra whitespace


# TWITCH API

# this will be called when the event READY is triggered, which will be on bot start
async def on_ready(ready_event: EventData):
    print('__ READY __')
    await ready_event.chat.join_room(TARGET_CHANNEL)



# this will be called whenever a message in a channel was send by either the bot OR another user
async def on_message(msg: ChatMessage):
    print(f'{msg.user.name} said: {msg.text}')
    text = strip_emotes(msg.text, msg.emotes)[:1000].strip()  # Limit to 1000 characters and strip whitespace
    if len(text) > 0:
        show_tts(text, msg.user.name)
    

# this is where we set up the bot
async def run():
    twitch = await Twitch(APP_ID, APP_SECRET)

    if TOKEN_FILE and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)
            token = token_data.get('token')
            refresh_token = token_data.get('refresh_token')
    else:
        # set up twitch api instance and add user authentication with some scopes
        auth = UserAuthenticator(twitch, USER_SCOPE)
        token, refresh_token = await auth.authenticate()

        # save the token to a file for later use
        with open(TOKEN_FILE, 'w') as f:
            json.dump({'token': token, 'refresh_token': refresh_token}, f)
    
    await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)

    # create chat instance
    chat = await Chat(twitch)

    # register the handlers for the events you want

    # listen to when the bot is done starting up and ready to join channels
    chat.register_event(ChatEvent.READY, on_ready)
    # listen to chat messages
    chat.register_event(ChatEvent.MESSAGE, on_message)

    # we are done with our setup, lets start this bot up!
    chat.start()

    # lets run till we press enter in the console
    try:
        input('press ENTER to stop\\n')
    finally:
        # now we can close the chat bot and the twitch api client
        chat.stop()


# lets run our setup
asyncio.run(run())
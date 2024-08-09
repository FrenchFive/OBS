import keyboard
from twitchio.ext import commands
import time 
import datetime
import os

path = os.path.dirname(os.path.realpath(__file__))

with open(path+"/secret-twitch.password") as file:
    token = file.read().replace('\n', '')


allowed = ['space']

def hotkey(key):
    if key in allowed:
        keyboard.press_and_release(key)
        return False

class ChatKeyboard(commands.Bot):
    def __init__(self):
        super().__init__(token=token, prefix='!', initial_channels=['french_five'])

    async def event_ready(self):
        print('-- READY -- \n')

    async def event_message(self, message):
        if message.echo:
            return
        key = str(message.content)[1:]

        if str(message.content).startswith("!") and key in allowed:
            print(f'{str(message.author.name).capitalize()} PRESSED :: {key.upper()} || {datetime.datetime.now().strftime("%H:%M:%S")}')
            time.sleep(1)
            hotkey(key)
        
        return
    
ChatKeyboard().run()
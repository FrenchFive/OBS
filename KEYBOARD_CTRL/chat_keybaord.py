import keyboard
from twitchio.ext import commands
import time 

allowed = ['space']

def hotkey(key):
    if key.name in allowed:
        print(f'CHAT pressed {key}')
        keyboard.press_and_release(key)
        return False

class ChatKeyboard(commands.Bot):
    def __init__(self):
        super().__init__(token='token', client_id='client_id', prefix='!', initial_channels=['french_five'])

    async def event_ready(self):
        print('-- READY -- \n')
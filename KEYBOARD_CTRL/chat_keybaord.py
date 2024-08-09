import keyboard
from twitchio.ext import commands
import time 
import datetime
import os
import threading

path = os.path.dirname(os.path.realpath(__file__))

with open(path+"/secret-twitch.password") as file:
    token = file.read().replace('\n', '')

#ALLOWED KEYS
allowed = ['space']

def check_allowed_shortcuts(allowed):
    if "all_keyboard" in allowed:
        allowed.remove("all_keyboard")
        for i in range(0, 10):
            allowed.append(str(i))
        for i in range(65, 91):
            allowed.append(chr(i))
        for i in range(97, 123):
            allowed.append(chr(i))
    return allowed

allowed = check_allowed_shortcuts(allowed)

class ChatKeyboard(commands.Bot):
    def __init__(self):
        super().__init__(token=token, prefix='!', initial_channels=['french_five'])
        self.active = True  # Add a running flag

    async def event_ready(self):
        print('-- READY -- \n')

    async def event_message(self, message):
        if message.echo:
            return
        key = str(message.content)[1:]

        if self.active==True:
            if str(message.content).startswith("!") and key in allowed:
                print(f'{str(message.author.name).capitalize()} PRESSED :: {key.upper()} || {datetime.datetime.now().strftime("%H:%M:%S")}')
                keyboard.press_and_release(key)

def check_pause(bot):
    var = True
    while True:
        if keyboard.is_pressed('F9'):
            if var == True:
                print('-- CHAT CTRL KEYBOARD DISABLE')
                bot.active = False
                var = False
            else:
                print('-- CHAT CTRL KEYBOARD ENABLE')
                bot.active = True
                var = True
        time.sleep(0.1)  # To prevent high CPU usage

bot = ChatKeyboard()
threading.Thread(target=check_pause, args=(bot,)).start()  # Start the hotkey check in a new thread
bot.run()
# INITIALIZATION 
from twitchio.ext import commands
import openai
import time
import random
import requests
import json
import pyttsx3
import keyboard
import threading
import os

path = os.path.dirname(os.path.realpath(__file__))
resettimer = 900 #IN SECONDS
luckprob = 85 #OVER THIS PERCENTAGE IT WILL BE LUCKY
maxlenght = 300 #MAXIMUM ORION CHARACTER LENGHT (PLEASE DO NOT EXCEED 500)


#ARTWORK
print("\n")
fontpath = path+"/font.txt"
fontread = open(fontpath,"r")

fontlines = fontread.readlines()
for i in range (len(fontlines)):
    print(fontlines[i].replace("\n",""))
fontread.close()
print("\n")

#OPENAI API KEY
openaipath = path+"/secret-openai.password"
openairead = open(openaipath,"r")
openaikey = openairead.readline()
openairead.close()
openai.api_key = openaikey



#TWITCH INFO
def streaminfo():
    with open(path+"/secret-twitchinfo-auth.password") as file:
        streaminfo_auth = file.read().replace('\n', '')
    with open(path+"/secret-twitchinfo-clientid.password") as file:
        streaminfo_clientid = file.read().replace('\n', '')
    
    url = 'https://api.twitch.tv/helix/streams?user_login=french_five'

    headers = {
        'Authorization': streaminfo_auth,
        'Client-Id': streaminfo_clientid
    }

    response = requests.get(url, headers=headers)

    data = json.loads(response.content)
    try:
        stream_game = data['data'][0]['game_name']
        stream_title = data['data'][0]['title']
    except:
        stream_game = "No Game"
        stream_title = "No Live"

    return stream_game, stream_title


#CREATING THE CHAT HISTORY AND DEFINING HER PERSONA 
def chathistoryclear():
    global path
    chathist = []
    infopath = path+"/info.txt"
    inforead = open(infopath,"r")

    infolines = inforead.readlines()
    for i in range (len(infolines)):
        chathist.append({"role":"system","content":infolines[i].replace("\n","")})
    inforead.close()

    stream_game, stream_title = streaminfo()
    if stream_game == "No Game" or stream_title=="No Live":
        chathist.append({"role":"system","content":"French is not Live"})
    else :
        chathist.append({"role":"system","content":"French Five is Live in the category : "+stream_game})
        chathist.append({"role":"system","content":"French Five Stream Title is : "+stream_title})

    #EMOTES
    emotespath = path+"/emotes.txt"
    emotesread = open(emotespath,"r")
    emoteslist = emotesread.readlines()
    emotesread.close()
    emotephrase = ""
    for i in range (len(emoteslist)):
        emotephrase += str(emoteslist[i]).replace("\n","")+" "
    chathist.append({"role":"system","content":emotephrase})
    chathist.append({"role":"system","content":"Your favorite emote is : french210Love "})

    return chathist
chathistory = chathistoryclear()

#TIMESTART
timerstart = time.time()

#AUDIO
def speak(txt):
    engine = pyttsx3.init()
    engine.setProperty('rate', 200)
    engine.setProperty('volume',1)
    engine.setProperty('voice', engine.getProperty('voices')[1].id)
    engine.say(txt)
    engine.runAndWait()
    engine.stop()

# CHATGPT FUNCTIONS
def chatgpt(history):
    client = openai.OpenAI()
    chat_completion = client.chat.completions.create(model="gpt-4", messages=history)
    return chat_completion.choices[0].message.content

# IS THE MESSAGE FOR ORION ?? 
def isorion(message):
    search = message.lower()
    search.replace("."," ")
    search.replace(","," ")
    search.replace(";"," ")
    search.replace("!"," ")
    search.replace("?"," ")
    search.replace(":"," ")
    search.replace("/"," ")
    search.replace("\\"," ")
    search.replace("@orion_goddess",' orion ')
    search.replace("goddess"," orion ")
    search.replace("godess",' orion ')
    search.replace('orion_goddess',' orion ')
    return search.find('orion')


#FONCTION DE COMMANDE
def cmdorion():
    #INTRODUCE TO ITSELF
    global path
    chathist = []
    infopath = path+"/info.txt"
    inforead = open(infopath,"r")

    infolines = inforead.readlines()
    for i in range (len(infolines)):
        chathist.append({"role":"system","content":infolines[i].replace("\n","")})
    inforead.close()

    #EMOTES
    emotespath = path+"/emotes.txt"
    emotesread = open(emotespath,"r")
    emoteslist = emotesread.readlines()
    emotesread.close()
    emotephrase = ""
    for i in range (len(emoteslist)):
        emotephrase += str(emoteslist[i]).replace("\n","")+" "
    chathist.append({"role":"system","content":emotephrase})
    
    return chathist


# TWITCH API STUFF 
#TWITCH API KEY
twitchpath = path+"/secret-twitch.password"
twitchread = open(twitchpath,"r")
twitchkey = twitchread.readline()
twitchread.close()

class Orion(commands.Bot):

    def __init__(self):
        # Initialise our Bot with our access token, prefix and a list of channels to join on boot...
        # prefix can be a callable, which returns a list of strings or a string...
        # initial_channels can also be a callable which returns a list of strings...
        global twitchkey
        super().__init__(token=twitchkey, prefix='#', initial_channels=['french_five'])
        self.tts = True  # Add a running flag

    async def event_ready(self):
        # Notify us when everything is ready!
        print('-- READY -- \n')

    async def event_message(self, message):
        #CANCEL MESSAGE FROM ITSELF
        if message.echo:
            return
        
        luck = random.randint(1,100)
        detected = isorion(message.content)
        command = False
        #DETECTION DES COMMANDES
        if str(message.content).startswith("#") or str(message.content).startswith("!"):
            command = True
            luck = 0
            detected = -1

        if self.tts == True and command == False:
            speak(message.content)

        global chathistory

        #HOW LONG AS THE CHAT BEEN UP => TOO LONG => CHAT RESET
        global timerstart
        difftimer = time.time() - timerstart
        global resettimer
        if difftimer> resettimer:
            chathistory = chathistoryclear()
            timerstart=time.time()
            print("--- CHAT RESET ---")
        

        lcltime = time.localtime() # get struct_time
        timestring = time.strftime("%H:%M:%S", lcltime)
        print("READ FROM : "+message.author.name+" | "+timestring)
        chathistory.append({'role':'user','content': message.author.name+' : '+message.content})
        

        global luckprob
        if detected != -1 or luck>=luckprob:
            if detected != -1:
                detection = "txt"
            else:
                detection = "lck"

            print("[ACTIVATED] "+detection)

            #CHATGPT SRUFF
            response = chatgpt(chathistory)
            chathistory.append({"role": "assistant", "content":response})

            #RESPONSE LENGHT
            global maxlenght
            if len(response)>maxlenght:
                response = (response[:maxlenght]+" ...")

            #SEND THE MESSAGE
            await oriongod.connected_channels[0].send(response)

        await self.handle_commands(message)
    
    @commands.command()
    async def orion(self, ctx: commands.Context):
        chatlist = cmdorion()

        send = ctx.author.name+"Who are you ? Present yourself"
        chatlist.append({"role": "user", "content":send})

        cmdtxt = chatgpt(chatlist)
        print("-- !COMMAND - ORION")

        await ctx.send(cmdtxt)
    @commands.command()
    async def social(self, ctx: commands.Context):
        chatlist = cmdorion()

        listofmedia = [" https://www.twitch.tv/french_five "," https://www.youtube.com/@quack_five "," https://www.instagram.com/quack.five "]
        for i in listofmedia:
            chatlist.append({'role':'system','content':i})

        send = ctx.author.name+": Give me a list of all Social Medias from French Five"
        send+= ", never invent any social media you don't have as information"
        send+= ", make it beautiful with a lot emojis and emotes"
        send+= ", seperate each link using a space at the begining and the end of each link"
        chatlist.append({"role": "user", "content":send})

        cmdtxt = chatgpt(chatlist)
        print("-- !COMMAND - SOCIAL")

        await ctx.send(cmdtxt)

def check_hotkey(bot):
    var = True
    while True:
        if keyboard.is_pressed('F8'):
            if var == True:
                print('-- TTS DISABLE')
                bot.tts = False
                var = False
            else:
                print('-- TTS ACTIVE')
                bot.tts = True
                var = True
        time.sleep(0.1)  # To prevent high CPU usage

oriongod = Orion()
threading.Thread(target=check_hotkey, args=(oriongod,)).start()  # Start the hotkey check in a new thread
oriongod.run()
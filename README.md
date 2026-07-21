# OBS

Here is some code i created w/ chat for streaming.

> [!WARNING]  
> Some utilities/plugins/modules may be required.

---
### TASKS 
- [x] COUNTER
- [x] ORION
- [x] CHAT CONTROL KEYBOARD 
- [x] MESSAGE VISUALISATION → **CHAT CONNECT**
- [x] CHAT YAPPER (Duck TTS) → reads Twitch **+ YouTube** via CHAT CONNECT

---
## CHAT CONNECT 💬

**The chat hub.** Runs in the background and merges **Twitch chat + YouTube
live chat** into one local stream on `http://localhost:2428`:

- 🖥️ **Web dashboard** to connect/disconnect channels and watch the merged feed
- 🎥 **Clean OBS overlay** (browser source: `http://localhost:2428/overlay`)
  with a **visual style editor** (`/editor`): live preview, saved settings,
  fonts / backgrounds / timestamps / name truncation / chat delay…
- 🔌 **Open local API** (WebSocket / SSE / REST) so any script can read the
  messages — the Duck, bots, games, whatever
- 🔑 **No credentials needed** — anonymous Twitch reading, no-API-key YouTube
  mode (official API key supported as an option)
- 🚀 **Auto-start with OBS** — one Lua script and opening OBS launches
  everything, closing OBS stops it

➡️ Beginner walkthrough: [`CHAT_CONNECT/SETUP_GUIDE.md`](CHAT_CONNECT/SETUP_GUIDE.md)
· Tech/API docs: [`CHAT_CONNECT/README.md`](CHAT_CONNECT/README.md)

---
## CHAT YAPPER 🦆

A duck pops up in OBS and **reads chat out loud** (random OpenAI voices, or a
free offline voice). Plugged into CHAT CONNECT, so it yaps **both Twitch and
YouTube** messages and announces who wrote them and where.

➡️ Setup: [`CHAT_YAPPER/README.md`](CHAT_YAPPER/README.md)

---
## COUNTER 

A counting script to count Death or Crashes and display it on stream.

Works using **OBS** and **STREAMDECK** 
<br><sub> Can be used in any other software.</sub>
<p align="center">
    <img src="https://github.com/user-attachments/assets/2785f589-79cc-4eee-8cdb-a61217403f5d" >
</p>

---
## ORION

AI Chat Bot running in Python.
<br> Reads messages, respond to basic commands, and chat in Twitch.
<br> Uses ChatGpt3

![image](https://github.com/user-attachments/assets/1ed5d9d4-2fcf-4128-a44b-4d170198d347)
![image](https://github.com/user-attachments/assets/2f7b1351-090b-4aa9-a312-0c6591009b9e)



---
## KEYBOARD CONTROL

A code that lets Chat control the keyboard. 

![image](https://github.com/user-attachments/assets/94398b47-4f3f-46d2-a62c-112e77cabd35)
![image](https://github.com/user-attachments/assets/69ec16f2-6d54-4017-a0a6-29ae286feebf)

---

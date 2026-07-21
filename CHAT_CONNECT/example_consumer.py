"""Minimal example: receive every Twitch + YouTube message from CHAT CONNECT.

This is the exact pattern any of your tools can copy (the Duck TTS in
CHAT_YAPPER uses the same one). Start CHAT CONNECT first, then run:

    python example_consumer.py

Needs: pip install aiohttp
"""

import asyncio
import json

import aiohttp

CHAT_CONNECT_WS = "ws://127.0.0.1:2428/ws"


async def main():
    while True:  # reconnect forever if CHAT CONNECT restarts
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(CHAT_CONNECT_WS) as ws:
                    print(f"Connected to {CHAT_CONNECT_WS} - waiting for messages...")
                    async for frame in ws:
                        if frame.type != aiohttp.WSMsgType.TEXT:
                            continue
                        event = json.loads(frame.data)

                        if event["type"] == "chat":
                            msg = event["data"]
                            # msg keys: id, platform, author, message, message_clean,
                            #           color, badges, emotes, timestamp, (amount)
                            print(f'[{msg["platform"]:^7}] {msg["author"]}: {msg["message"]}')

                        elif event["type"] == "status":
                            s = event["data"]
                            print(f'-- {s["platform"]} is now {s["state"]} {s["detail"]}')

                        # event["type"] == "hello" also exists: it contains
                        # data["history"] (recent messages) and data["status"].
        except aiohttp.ClientError:
            print("CHAT CONNECT is not running (start CHAT_CONNECT/run.bat) - retrying in 5s")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

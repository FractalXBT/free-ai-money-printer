import asyncio
import websockets
import json

WS_URL = "wss://pumpportal.fun/api/data"

async def test_connection():
    async with websockets.connect(WS_URL) as websocket:
        await websocket.send(json.dumps({"method": "subscribeNewToken"}))
        await websocket.send(json.dumps({"method": "subscribeTokenTrade"}))
        
        print("Subscribed... Waiting for messages.")

        async for message in websocket:
            print("Received:", message)  # Prints raw data from WebSocket

asyncio.run(test_connection())

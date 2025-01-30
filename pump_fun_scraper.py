import asyncio
import websockets
import json
import pandas as pd
from datetime import datetime
import os

# WebSocket API URL
WS_URL = "wss://pumpportal.fun/api/data"

# CSV file path
CSV_FILE = "pump_fun_data.csv"

async def subscribe():
    """
    Connects to the PumpPortal WebSocket and subscribes to real-time events.
    """
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("[*] Connected to WebSocket")

            # Subscribing to events
            await websocket.send(json.dumps({"method": "subscribeNewToken"}))
            await websocket.send(json.dumps({"method": "subscribeTokenTrade"}))

            print("[*] Subscribed to real-time events... Waiting for data.")

            # Process incoming messages
            async for message in websocket:
                print(f"[*] Received data: {message}")  # Debugging log
                data = json.loads(message)
                process_data(data)
    except Exception as e:
        print(f"[!] WebSocket Error: {e}")

def process_data(data):
    """
    Processes incoming JSON data and saves it to a CSV file.
    """
    try:
        # Extract relevant fields
        row = {
            "Signature": data.get("signature", "N/A"),
            "Mint": data.get("mint", "N/A"),
            "Trader Public Key": data.get("traderPublicKey", "N/A"),
            "Transaction Type": data.get("txType", "N/A"),
            "Initial Buy": data.get("initialBuy", 0),
            "SOL Amount": data.get("solAmount", 0),
            "Bonding Curve Key": data.get("bondingCurveKey", "N/A"),
            "vTokens In Bonding Curve": data.get("vTokensInBondingCurve", 0),
            "vSol In Bonding Curve": data.get("vSolInBondingCurve", 0),
            "Market Cap (SOL)": data.get("marketCapSol", 0),
            "Token Name": data.get("name", "N/A"),
            "Symbol": data.get("symbol", "N/A"),
            "Metadata URI": data.get("uri", "N/A"),
            "Pool": data.get("pool", "N/A")
        }

        # Convert row into DataFrame
        df = pd.DataFrame([row])

        # Append to CSV
        file_exists = os.path.exists(CSV_FILE)
        df.to_csv(CSV_FILE, mode='a', index=False, header=not file_exists)

        print(f"[*] Data appended to {CSV_FILE}: {row}")

    except Exception as e:
        print(f"[!] Error processing data: {e}")

def main():
    """
    Main function to run the WebSocket listener.
    """
    asyncio.get_event_loop().run_until_complete(subscribe())

if __name__ == "__main__":
    main()

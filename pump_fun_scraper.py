# Standard Library Imports
import os
import json
import signal
import asyncio

# Third-Party Library Imports
import requests
import pandas as pd
from dotenv import load_dotenv
from colorama import Fore, Style, init
import websockets

load_dotenv()

# Initialize colorama for Windows compatibility
init()

# WebSocket API URL
WS_URL = "wss://pumpportal.fun/api/data"

# CSV file path
CSV_FILE = "pump_fun_data.csv"

# Filtering thresholds
MIN_INITIAL_BUY = 1000  # Minimum initial buy to avoid small purchases
MIN_SOL_AMOUNT = 0.01  # Minimum SOL balance for relevance
MIN_MARKET_CAP = 30  # Ensuring a reasonable market cap

# API Endpoint (example, update if needed)
TWEETSCOUT_API_URL = "https://api.tweetscout.io/v2"
TWEETSCOUT_API_KEY = os.getenv('TWEETSCOUT_API_KEY')

# Define the minimum follower threshold
MIN_FOLLOWERS = 30000 
TWITTER_BLACKLIST = [
  "elonmusk", "nypost", "pumpdotfun"
]

# API Base URL
RUGCHECK_API_URL = "https://api.rugcheck.xyz/v1"

# Minimum Safety Score Threshold
MIN_SAFETY_SCORE = 500

async def subscribe():
    """
    Connects to the PumpPortal WebSocket and subscribes to real-time events.
    """
    try:
        async with websockets.connect(WS_URL) as websocket:
            print(Fore.CYAN + "[*] Connected to WebSocket" + Style.RESET_ALL)

            # Subscribing to events
            await websocket.send(json.dumps({"method": "subscribeNewToken"}))
            await websocket.send(json.dumps({"method": "subscribeTokenTrade"}))

            print(Fore.CYAN + "[*] Subscribed to real-time events... Waiting for data." + Style.RESET_ALL)

            # Process incoming messages
            async for message in websocket:
                # print(f"[*] Received data: {message}")  # Debugging log
                data = json.loads(message)
                process_data(data)

    except Exception as e:
        print(Fore.RED + f"[!] WebSocket Error: {e}" + Style.RESET_ALL)

def get_twitter_url(url):
    """
    Fetches JSON data from the given URL and extracts the Twitter URL.

    Args:
        url (str): The API endpoint or URL containing the JSON data.

    Returns:
        str: The extracted Twitter URL or None if not found.
    """

    if url == "N/A":
      return None

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for HTTP issues
        data = response.json()

        twitter_url = data.get("twitter")
        return twitter_url if twitter_url else None

    except requests.RequestException as e:
        print(f"[!] Error fetching data from {url}: {e}")
        return None

def get_twitter_user_handle(twitter_url):
    """
    Extracts the Twitter user handle from a given tweet URL.

    Args:
        twitter_url (str): The full Twitter status URL.

    Returns:
        str: The extracted Twitter handle or None if the format is incorrect.
    """
    try:
        
        # Ensure twitter_url is a string (decode if bytes)
        if twitter_url is None:
          return None

        parsed_url = urlparse(twitter_url)
        path_parts = parsed_url.path.strip("/").split("/")

        if len(path_parts) > 0:
            return path_parts[0]  # The Twitter handle is the first part of the path

        return None  # Return None if the URL format is incorrect

    except Exception as e:
        print(f"[!] Error processing URL: {e}")
        return None

def get_twitter_id(twitter_url):
    user_handle = get_twitter_user_handle(twitter_url)

    API_URL = TWEETSCOUT_API_URL + "/handle-to-id/" + user_handle
    headers = {
      "Accept": "application/json",
      "ApiKey": TWEETSCOUT_API_KEY
    }

    response = requests.get(url, headers=headers)

    return response.json().get("id")

def get_token_influencers_count(twitter_url):
    """
    Fetches and filters social activity data for a given token.

    Args:
        token_symbol (str): The symbol of the token (e.g., SOL, ETH).

    Returns:
        list: A list of influencers with 30,000+ followers who follow the token.
    """

    user_handle = get_twitter_user_handle(twitter_url)
    if user_handle is None:
      return 0

    if user_handle in TWITTER_BLACKLIST:
      return -1

    API_URL = TWEETSCOUT_API_URL + "/info/" + user_handle
    headers = {
      "Accept": "application/json",
      "ApiKey": TWEETSCOUT_API_KEY
    }

    try:
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()
        data = response.json()

        if "followers_count" not in data:
            return 0

        # Filter influencers with at least 30,000 followers
        return data.get("followers_count")

    except requests.RequestException as e:
        print(f"[!] Error fetching social data: {e}")
        return 0

def fetch_token_contract_analysis(token_address):
    url = f"{RUGCHECK_API_URL}/tokens/{token_address}/report/summary"
    # print(url)
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for HTTP issues
        data = response.json()

        return data

    except requests.RequestException as e:
        print(f"[!] Error fetching data from {url}: {e}")
        return None

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
            "Pool": data.get("pool", "N/A"),
            "Twitter": get_twitter_url(data.get("uri", "N/A"))
        }

        if row["Signature"] == "N/A":
          return

        # Convert row into DataFrame
        df = pd.DataFrame([row])

        # Append to CSV
        file_exists = os.path.exists(CSV_FILE)
        df.to_csv(CSV_FILE, mode='a', index=False, header=not file_exists)

        #print(f"[*] Data appended to {CSV_FILE}: {row}")

        # Check if token meets filtering criteria
        if (
            row["Initial Buy"] >= MIN_INITIAL_BUY and
            row["SOL Amount"] >= MIN_SOL_AMOUNT and
            row["Market Cap (SOL)"] >= MIN_MARKET_CAP
        ):
            print(Fore.YELLOW + f"\n[HIGHLIGHTED TOKEN] {row['Token Name']} ({row['Symbol']})" + Style.RESET_ALL)
            print(Fore.YELLOW + f"   - Initial Buy: {row['Initial Buy']}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"   - SOL Amount: {row['SOL Amount']}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"   - Market Cap (SOL): {row['Market Cap (SOL)']}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"   - Mint Address: {row['Mint']}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"   - Metadata URI: {row['Metadata URI']}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"   - Twitter: {row['Twitter']}" + Style.RESET_ALL)

            # Fetch influencers for this token
            twitter_url = row['Twitter']

            influencers = get_token_influencers_count(twitter_url)

            if influencers > 0:
                print(Fore.MAGENTA + f"\n[🔍] Influencers following {row['Token Name']} ({row['Symbol']}): {influencers}")
            elif influencers < 0:
                print(Fore.RED + f"[!] Fake Twitter handle for {row['Token Name']} ({row['Symbol']}).")
            else:
                print(Fore.RED + f"[!] No influencers found for {row['Token Name']} ({row['Symbol']}).")

            print(Style.RESET_ALL)

            # Analyze contract safety on rugcheck.xyz
            token_address = row["Mint"]
            # print(token_address)
            contract_analysis = fetch_token_contract_analysis(token_address)
            if contract_analysis:
              # print(json.dumps(contract_analysis, indent=2, ensure_ascii=False))
              risk_score = contract_analysis["score"]
              if risk_score <= MIN_SAFETY_SCORE:
                  print(f"[✅] Token \"{row['Token Name']}\" has a {risk_score} Risk Score")
              else:
                  print(f"[❌] Token \"{row['Token Name']}\" has a {risk_score} Risk Score")

              for item in contract_analysis["risks"]:
                print(f"    🚨 Risk Level: {item['level'].capitalize()} | Score: {item['score']}")
                print(f"       Name: {item['name']}")
                print(f"       Description: {item['description']}\n")
        
        else:
            print(Fore.GREEN + f"[*] Processed Token: {row['Token Name']} ({row['Symbol']})" + Style.RESET_ALL)

    except Exception as e:
        print(f"[!] Error processing data: {e}")

async def main():
    """
    Runs the WebSocket listener with graceful shutdown handling.
    """
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    # Обробка Ctrl + C
    def shutdown():
        print("\n[!] Received exit signal, shutting down gracefully...")
        stop_event.set()

    loop.add_signal_handler(signal.SIGINT, shutdown)

    try:
        task = asyncio.create_task(subscribe())
        await stop_event.wait()
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print("[✅] WebSocket task successfully cancelled.")
        print("[✅] Cleanup complete. Exiting.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[❌] Script interrupted by user. Exiting.")

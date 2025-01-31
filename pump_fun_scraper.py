import asyncio
import websockets
import json
import pandas as pd
import os
from datetime import datetime
from colorama import Fore, Style, init
import requests
from dotenv import load_dotenv
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import signal

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

# Load environment variables
RUGCHECK_API_KEY = os.getenv("RUGCHECK_API_KEY")  # Store your API key in a .env file

# API Base URL
RUGCHECK_API_URL = "https://rugcheck.xyz/tokens" # Not an API, just URL content parser

# Minimum Safety Score Threshold
MIN_SAFETY_SCORE = 85

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

# Function to parse contract analysis and check safety
def parse_contract_analysis(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    analysis_data = {}
    # print(soup.prettify())
 
    # safety_score_element = soup.find("div", class_="safety-score")
    # if safety_score_element:
    #     safety_score = safety_score_element.text.strip().replace("%", "")
    #     analysis_data["safety_score"] = float(safety_score)
    # else:
    #     analysis_data["safety_score"] = 0.0

    risk_element = soup.find("div", class_="risk") # <-- Here we parse risk DOM element
    if risk_element:
        risk = risk_element.text.strip().replace("%", "")
        analysis_data["risk"] = risk
    else:
        analysis_data["risk"] = ""
 
    # liquidity_burned_element = soup.find("div", class_="liquidity-burned")
    # if liquidity_burned_element:
    #     analysis_data["liquidity_burned"] = "Yes" in liquidity_burned_element.text.strip()
    # else:
    #     analysis_data["liquidity_burned"] = False
 
    # mintable_element = soup.find("div", class_="mintable")
    # if mintable_element:
    #     analysis_data["mintable"] = "Yes" in mintable_element.text.strip()
    # else:
    #     analysis_data["mintable"] = False
 
    # pausable_element = soup.find("div", class_="pausable")  # Replace with actual class or tag
    # if pausable_element:
    #     analysis_data["pausable"] = "Yes" in pausable_element.text.strip()
    # else:
    #     analysis_data["pausable"] = False
 
    return analysis_data

def fetch_token_contract_analysis(token_address):
    url = f"{RUGCHECK_API_URL}/{token_address}"
    # print(url)
    try:
        # Configure browser options
        options = Options()
        options.add_argument("--headless")  # Run in headless mode (no GUI)
        options.add_argument("--disable-blink-features=AutomationControlled")  # Bypass bot detection
        options.add_argument("--no-sandbox")  # Helps with permission issues in some environments
        options.add_argument("--disable-gpu")  # Required for headless mode
        options.add_argument("--disable-dev-shm-usage")  # Prevents memory issues
        options.add_argument("--incognito")  # Open browser in incognito mode

        # Set a real User-Agent to avoid detection
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

        # Set up ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Load the webpage
        driver.get(url)

        # Get the fully rendered HTML after JavaScript execution
        return driver.page_source
    except requests.exceptions.RequestException as e:
        print(f"Error fetching token contract analysis: {e}")
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
            html_content = fetch_token_contract_analysis(token_address)
            if html_content:
              contract_analysis = parse_contract_analysis(html_content)
              # print(contract_analysis)
              risk = contract_analysis["risk"]
              if risk == "Good":
                  print(Fore.MAGENTA + f"[!] Token {row['Token Name']} has a 'Good' risk level")
              else:
                  print(Fore.RED + f"[!] Token {row['Token Name']} has a '{risk}' risk level")

            print(Style.RESET_ALL)
        
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

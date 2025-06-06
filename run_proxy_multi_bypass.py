import asyncio
import time
import uuid
import random
#import cloudscraper
from loguru import logger
#from fake_useragent import UserAgent
from curl_cffi import requests

# Constants
PING_INTERVAL = 60
RETRIES = 60

DOMAIN_API = {
    "SESSION": "https://api.nodepay.org/api/auth/session",
    "PING": "https://nw.nodepay.org/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}  # Track ping time per token
last_proxy_time = {}  # Track proxy use time
proxies = []  # List of proxies loaded from a file

def show_warning():
    confirm = input("By using this tool means you understand the risks. do it at your own risk! \nPress Enter to continue or Ctrl+C to cancel... ")

    if confirm.strip() == "":
        print("Continuing...")
    else:
        print("Exiting...")
        exit()

def uuidv4():
    return str(uuid.uuid4())

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

async def render_profile_info(proxy, token):
    global browser_id, account_info

    try:
        np_session_info = load_session_info(proxy)

        if not np_session_info:
            # Generate new browser_id
            browser_id = uuidv4()
            response = await call_api(DOMAIN_API["SESSION"], {}, proxy, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(proxy, account_info)
                await start_ping(proxy, token)
            else:
                handle_logout(proxy)
        else:
            account_info = np_session_info
            await start_ping(proxy, token)
    except Exception as e:
        logger.error(f"Error in render_profile_info for proxy {proxy}: {e}")
        error_message = str(e)
        if any(phrase in error_message for phrase in [
            "sent 1011 (internal error) keepalive ping timeout; no close frame received",
            "500 Internal Server Error"
        ]):
            logger.info(f"Removing error proxy from the list: {proxy}")
            remove_proxy_from_list(proxy)
            return None
        else:
            logger.error(f"Connection error: {e}")
            return proxy

async def call_api(url, data, proxy, token):
    #user_agent = UserAgent(os=['windows', 'macos', 'linux'], browsers='chrome')
    #random_user_agent = user_agent.random
    user_agent = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
    ]
    random_user_agent = random.choice(user_agent)#user_agent.random
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": random_user_agent,
        "Content-Type": "application/json",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        #scraper = cloudscraper.create_scraper()

        #response = scraper.post(url, json=data, headers=headers, proxies={"http": proxy, "https": proxy}, timeout=30)
        response = requests.post(url, json=data, headers=headers, proxies={"http": proxy, "https": proxy}, impersonate="safari15_5", timeout=30)
        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        logger.error(f"Error during API call with proxy {proxy}: {e}")
        raise ValueError(f"Failed API call to {url}")

async def start_ping(proxy, token):
    try:
        while True:
            await ping(proxy, token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping for proxy {proxy}: {e}")
        
async def ping(proxy, token):
    global last_ping_time, RETRIES, status_connect

    current_time = time.time()

    # Track separate last ping time for each token
    if token in last_ping_time and (current_time - last_ping_time[token]) < PING_INTERVAL:
        logger.info(f"Skipping ping for token {token}, not enough time elapsed")
        return

    last_ping_time[token] = current_time  # Update the last ping time for this token

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        response = await call_api(DOMAIN_API["PING"], data, proxy, token)
        if response["code"] == 0:
            logger.info(f"Ping successful for token {token} via proxy {proxy}: {response}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(proxy, response)
    except Exception as e:
        logger.error(f"Ping failed for token {token} via proxy {proxy}: {e}")
        handle_ping_fail(proxy, None)

def handle_ping_fail(proxy, response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout(proxy)
    elif RETRIES < 2:
        status_connect = CONNECTION_STATES["DISCONNECTED"]
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout(proxy):
    global status_connect, account_info

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    save_status(proxy, None)
    logger.info(f"Logged out and cleared session info for proxy {proxy}")

def save_status(proxy, status):
    pass  

def save_session_info(proxy, data):
    data_to_save = {
        "uid": data.get("uid"),
        "browser_id": browser_id
    }
    pass

def load_session_info(proxy):
    return {}  # Placeholder for loading session info

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

def remove_proxy_from_list(proxy):
    pass  # Remove failed proxy from list

def is_valid_proxy(proxy):
    return True  # Placeholder for proxy validation

async def run_with_token(token):
    tasks = {}

    # Choose a proxy and run with it for each token
    proxy = proxies.pop(0) if proxies else None
    tasks[asyncio.create_task(render_profile_info(proxy, token))] = token

    done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
    for task in done:
        failed_token = tasks[task]
        if task.result() is None:
            logger.info(f"Failed for token {failed_token}, retrying with new proxy...")
            if proxies:
                proxy = proxies.pop(0)
                new_task = asyncio.create_task(render_profile_info(proxy, failed_token))
                tasks[new_task] = failed_token
        tasks.pop(task)

    await asyncio.sleep(10)

async def main():
    # Load tokens from the file
    try:
        with open('token_list.txt', 'r') as file:
            tokens = file.read().splitlines()
    except Exception as e:
        logger.error(f"Error reading token list: {e}")
        return

    if not tokens:
        print("No tokens found. Exiting.")
        return

    # Load proxies from the file
    global proxies
    proxies = load_proxies('local_proxies.txt')

    tasks = []
    for token in tokens:
        tasks.append(run_with_token(token))

    # Run all tasks concurrently
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    show_warning()
    print("\nAlright, we here! The tool will now use multiple tokens and proxies.")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")

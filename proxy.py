import re
import logging
import aiohttp
import asyncio
import os
import time
import json
import urllib.parse
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
import io

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import types, F, Router
from aiogram.types import BufferedInputFile

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL IMPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import database

# Router for this module
router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MAX_CONCURRENT_CHECKS = 20  # Parallel requests limit
PROXY_TIMEOUT = 8  # Timeout per proxy check (seconds)
IP_CHECK_URLS = [
    "https://api.ipify.org?format=json",
    "https://ifconfig.me/ip",
    "http://ip-api.com/json/",
]

# Speed test configuration — only save proxies that respond within this time
SPEED_TEST_TIMEOUT = 20  # seconds — reject if slower
SPEED_TEST_SITE = "neeja-baby-shop.myshopify.com"
SPEED_TEST_CARD = "4242424242424242|12|27|123"
SPEED_TEST_API_TIMEOUT = 25  # aiohttp timeout for speed test request
SPEED_TEST_CONCURRENT = 20  # parallel speed tests
API_ENDPOINTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_endpoints.txt")

# Special characters that break proxy auth (cause 407 errors)
BAD_PROXY_CHARS = set('!@#$%^&*()+=,;:<>?[]{}|\\\"\'`~')

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PARSING HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def parse_proxy_input(proxy_input):
    """
    Parses proxy input from ANY common format.
    """
    s = proxy_input.strip()
    protocol = 'http' 
    
    protocol_match = re.match(r'^(?P<p>http|https|socks4|socks5)://', s, re.IGNORECASE)
    if protocol_match:
        protocol = protocol_match.group('p').lower()
        s = s[len(protocol_match.group('p'))+3:]

    def is_valid(ip, port):
        return port and port.isdigit()

    # Pattern A: user:pass@ip:port
    match = re.match(r'^([^:@]+):([^:@]+)@([^:@]+):(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern B: user:pass ip:port
    match = re.match(r'^([^:@]+):([^:@]+)\s+([^:@]+):(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern C: ip:port user pass
    match = re.match(r'^([^:@]+):(\d+)\s+([^:@]+)\s+([^:@]+)$', s)
    if match:
        ip, port, user, password = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern D: user pass ip:port
    match = re.match(r'^([^:@]+)\s+([^:@]+)\s+([^:@]+):(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern E: user pass ip port
    match = re.match(r'^([^:@]+)\s+([^:@]+)\s+([^:@]+)\s+(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern F: user:pass:ip:port
    match = re.match(r'^([^:@]+):([^:@]+):([^:@]+):(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern G: ip:port:user:pass
    match = re.match(r'^([^:@]+):(\d+):([^:@]+):([^:@]+)$', s)
    if match:
        ip, port, user, password = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    return None

def build_dict(user, password, ip, port, protocol, original_input):
    if any(ch in password for ch in BAD_PROXY_CHARS):
        logging.warning(f"Rejecting proxy {ip}:{port} — special chars in password cause 407 auth errors")
        return None
    encoded_user = quote(user, safe='')
    encoded_pass = quote(password, safe='')
    return {
        "user": user,
        "password": password,
        "ip": ip,
        "port": port,
        "original_format": original_input,
        "url_format": f"{protocol}://{encoded_user}:{encoded_pass}@{ip}:{port}",
        "db_format": f"{user} {password} {ip} {port}",
        "http_format": f"http://{user}:{password}@{ip}:{port}"
    }


async def check_proxy_live(proxy_url, session=None, timeout=PROXY_TIMEOUT):
    """
    Checks if proxy is live using multiple IP check APIs with fallback.
    Returns: (is_alive: bool, info: dict)
    
    Args:
        proxy_url: Full proxy URL with auth
        session: Optional aiohttp session (for connection pooling)
        timeout: Request timeout per URL (seconds)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain'
    }
    
    client_timeout = aiohttp.ClientTimeout(total=timeout, connect=timeout/2)
    
    close_session = False
    if session is None:
        session = aiohttp.ClientSession(timeout=client_timeout, headers=headers)
        close_session = True
    
    last_error = "Unknown error"
    
    try:
        for ip_url in IP_CHECK_URLS:
            try:
                async with session.get(ip_url, proxy=proxy_url, ssl=False) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get('Content-Type', '')
                        if 'json' in content_type or 'javascript' in content_type:
                            try:
                                data = await resp.json()
                                ip = data.get('ip') or data.get('query')
                                if ip:
                                    return True, {"ip": ip}
                            except Exception:
                                text_data = await resp.text()
                                if text_data.strip():
                                    return True, {"ip": text_data.strip()}
                        else:
                            text_data = await resp.text()
                            if text_data.strip():
                                return True, {"ip": text_data.strip()}
                        last_error = "No IP in response"
                        continue
                    elif resp.status in (417, 429):
                        last_error = f"HTTP {resp.status}"
                        continue
                    else:
                        last_error = f"HTTP {resp.status}"
                        continue
            except asyncio.TimeoutError:
                last_error = "Timeout"
                continue
            except aiohttp.ClientProxyConnectionError:
                return False, {"error": "Connection failed"}
            except aiohttp.ClientConnectorError:
                return False, {"error": "DNS/Connection error"}
            except aiohttp.ClientError as e:
                last_error = f"Client error: {str(e)[:50]}"
                continue
            except Exception as e:
                last_error = str(e)[:80]
                continue
        
        return False, {"error": last_error}
        
    finally:
        if close_session:
            await session.close()


async def check_proxies_parallel(proxies_list, max_concurrent=MAX_CONCURRENT_CHECKS):
    """
    Check multiple proxies in parallel with semaphore limiting.
    
    Args:
        proxies_list: List of proxy dicts with 'url_format' key
        max_concurrent: Max simultaneous checks (default: 5)
        
    Returns:
        List of tuples: [(proxy_data, is_live, info), ...]
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def check_with_semaphore(proxy_data):
        async with semaphore:
            is_live, info = await check_proxy_live(proxy_data['url_format'])
            return (proxy_data, is_live, info)
    
    # Create tasks for all proxies
    tasks = [check_with_semaphore(p) for p in proxies_list]
    
    # Execute all tasks concurrently and gather results
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results - handle any exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append((proxies_list[i], False, {"error": str(result)}))
        else:
            processed_results.append(result)
    
    return processed_results


async def run_db_operation(func, *args):
    """Helper to run DB operations in thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SPEED TEST — Only save fast proxies (≤20s response time)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_speed_test_api():
    """Load first API endpoint from api_endpoints.txt for speed testing"""
    try:
        if os.path.exists(API_ENDPOINTS_FILE):
            with open(API_ENDPOINTS_FILE, "r", encoding="utf-8") as f:
                endpoints = [line.strip() for line in f if line.strip()]
                if endpoints:
                    return endpoints[0]
    except Exception as e:
        logging.error(f"Error loading speed test API: {e}")
    return None


async def check_proxy_speed(proxy_data, api_url=None):
    """
    Test proxy speed against Shopify API.
    Returns: (is_fast: bool, response_time: float, response: str)
    """
    if not api_url:
        api_url = get_speed_test_api()
    if not api_url:
        return True, 0, "No API — skipped speed test"

    user = proxy_data['user']
    pw = proxy_data['password']
    ip = proxy_data['ip']
    port = proxy_data['port']

    proxy_str = f"{ip}:{port}:{user}:{pw}"
    encoded_proxy = urllib.parse.quote(proxy_str)
    encoded_card = urllib.parse.quote(SPEED_TEST_CARD)
    encoded_site = urllib.parse.quote(SPEED_TEST_SITE)

    url = f"{api_url}?site={encoded_site}&cc={encoded_card}&proxy={encoded_proxy}"

    start = time.time()
    try:
        timeout = aiohttp.ClientTimeout(total=SPEED_TEST_API_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=False) as resp:
                elapsed = round(time.time() - start, 2)
                text = await resp.text()
                try:
                    data = json.loads(text)
                    status = data.get("Status", False)
                    response = str(data.get("Response", ""))
                except:
                    response = text[:80]

                if "429" in response:
                    if elapsed <= SPEED_TEST_TIMEOUT:
                        return True, elapsed, "429 (fast)"
                    return False, elapsed, "429 (slow)"
                elif "CARD_DECLINED" in response or "GENERIC_ERROR" in response or status:
                    if elapsed <= SPEED_TEST_TIMEOUT:
                        return True, elapsed, response[:30]
                    return False, elapsed, f"SLOW {response[:20]}"
                else:
                    if elapsed <= SPEED_TEST_TIMEOUT:
                        return True, elapsed, response[:30]
                    return False, elapsed, f"SLOW {response[:20]}"

    except asyncio.TimeoutError:
        elapsed = round(time.time() - start, 2)
        return False, elapsed, "Timeout"
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return False, elapsed, str(e)[:30]


async def check_proxies_speed_parallel(live_proxies, api_url=None, max_concurrent=SPEED_TEST_CONCURRENT):
    """
    Speed test multiple proxies in parallel.
    Returns: List of tuples: [(proxy_data, is_fast, response_time, response), ...]
    """
    if not api_url:
        api_url = get_speed_test_api()
    if not api_url:
        return [(p, True, 0, "No API — skipped") for p in live_proxies]

    semaphore = asyncio.Semaphore(max_concurrent)

    async def test_one(proxy_data):
        async with semaphore:
            is_fast, elapsed, response = await check_proxy_speed(proxy_data, api_url)
            return (proxy_data, is_fast, elapsed, response)

    tasks = [test_one(p) for p in live_proxies]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed.append((live_proxies[i], False, 0, str(result)[:30]))
        else:
            processed.append(result)
    return processed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND TASKS (PARALLEL PROCESSING)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_proxies_background(bot, message: types.Message, valid_proxies: list):
    """Process proxies in background — Live check → Speed test → Save only fast ones"""
    user_id = message.from_user.id
    total_count = len(valid_proxies)
    
    speed_api = get_speed_test_api()

    status_msg = await message.reply(
        f"⏳ <b>Processing...</b>\n\n"
        f"<code>{total_count}</code> proxies to check\n"
        f"<i>Live check: {min(MAX_CONCURRENT_CHECKS, total_count)} at a time</i>\n"
        f"<i>Speed test: internal</i>",
        parse_mode="HTML"
    )

    # Step 1: Live check (existing)
    results_list = await check_proxies_parallel(valid_proxies)
    live_count = sum(1 for _, is_live, _ in results_list if is_live)
    dead_count = total_count - live_count

    live_proxies = []
    for proxy_data, is_live, info in results_list:
        if is_live:
            live_proxies.append(proxy_data)

    # Step 2: Speed test (NEW — only save proxies faster than 20s)
    fast_count = 0
    slow_count = 0
    fast_proxies = []

    if live_proxies:
        if speed_api:
            try:
                await bot.edit_message_text(
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id,
                    text=(
                        f"⏳ <b>Speed Testing...</b>\n\n"
                        f"<b>Live:</b> {live_count} | <b>Dead:</b> {dead_count}\n"
                        f"<i>Testing {len(live_proxies)} live proxies for speed (≤{SPEED_TEST_TIMEOUT}s)...</i>"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

            speed_results = await check_proxies_speed_parallel(live_proxies, speed_api)
            for proxy_data, is_fast, elapsed, response in speed_results:
                if is_fast:
                    fast_proxies.append(proxy_data)
                    fast_count += 1
                else:
                    slow_count += 1
                    logging.info(f"[SPEED] Rejected slow proxy {proxy_data['ip']}:{proxy_data['port']} — {elapsed}s — {response}")
        else:
            fast_proxies = live_proxies
            fast_count = len(live_proxies)

    # Step 3: Save to database (only fast proxies)
    added_count = 0
    clone_count = 0

    if fast_proxies:
        try:
            def save_to_db():
                nonlocal added_count, clone_count
                docs = database.get_user_proxies(user_id)
                existing_proxies = {d["proxy"] for d in docs}
                added = 0
                clones = 0
                for proxy_data_item in fast_proxies:
                    proxy_str = proxy_data_item['db_format']
                    if proxy_str not in existing_proxies:
                        database.add_proxy(user_id, proxy_str)
                        existing_proxies.add(proxy_str)
                        added += 1
                        logging.info(f"Added fast proxy for user {user_id}: {proxy_str}")
                    else:
                        clones += 1
                return added, clones
            added_count, clone_count = await run_db_operation(save_to_db)
            logging.info(f"Saved {added_count} fast proxies, {clone_count} duplicates for user {user_id}")
        except Exception as e:
            logging.error(f"DB Error while saving proxies: {e}")
            added_count = 0
            clone_count = 0

    # Build final response
    is_bulk = total_count > 1

    if is_bulk:
        caption = (
            f"<b><tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Complete!</b>\n\n"
            f"<b>Total ➛</b> <code>{total_count}</code>\n"
            f"<b>Live ➛</b> <b>{live_count}</b> <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n"
            f"<b>Fast ➛</b> <b>{fast_count}</b> ⚡\n"
            f"<b>Added ➛</b> <b>{added_count}</b> 💾\n"
            f"<b>Clones ➛</b> <b>{clone_count}</b> 🔁\n"
            f"<b>Slow ➛</b> <b>{slow_count}</b> 🐌\n"
            f"<b>Dead ➛</b> <b>{dead_count}</b> <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>"
        )
    else:
        if results_list:
            proxy_data, is_live, info = results_list[0]
        else:
            proxy_data, is_live, info = valid_proxies[0], False, {}

        if not is_live:
            error_msg = info.get("error", "Unknown")
            caption = (
                f"<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Failed!</b>\n\n"
                f"<b>Status ➛ Dead <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji></b>\n"
                f"<b>Reason ➛</b> <code>{error_msg}</code>\n\n"
                f"<b><tg-emoji emoji-id=\"5456288730140675445\">🚫</tg-emoji> Not added.</b>"
            )
        elif fast_count == 0 and slow_count > 0:
            caption = (
                f"<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Too Slow!</b>\n\n"
                f"<b>Status ➛ Live but SLOW 🐌</b>\n"
                f"<b>IP ➛</b> <code>{proxy_data.get('ip', 'Unknown')}</code>\n"
                f"<b>Threshold ➛</b> ≤{SPEED_TEST_TIMEOUT}s required\n\n"
                f"<b><tg-emoji emoji-id=\"5456288730140675445\">🚫</tg-emoji> Not added.</b>"
            )
        elif added_count > 0:
            ip = info.get("ip") or proxy_data.get('ip', 'Unknown')
            caption = (
                f"<b><tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Success!</b>\n\n"
                f"<b>Status ➛ Fast ⚡</b>\n"
                f"<b>IP ➛</b> <code>{ip}</code>\n\n"
                f"<b>💾 Saved to database</b>"
            )
        elif clone_count > 0:
            ip = info.get("ip") or proxy_data.get('ip', 'Unknown')
            caption = (
                f"<b><tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> Warning!</b>\n\n"
                f"<b>Status ➛ Fast ⚡</b>\n"
                f"<b>IP ➛</b> <code>{ip}</code>\n\n"
                f"<b>🔁 Already exists in database</b>"
            )
        else:
            ip = info.get("ip") or proxy_data.get('ip', 'Unknown')
            caption = (
                f"<b><tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> Warning!</b>\n\n"
                f"<b>Status ➛ Fast ⚡</b>\n"
                f"<b>IP ➛</b> <code>{ip}</code>\n\n"
                f"<b>❓ Unknown error - not saved</b>"
            )

    try:
        await bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=caption,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Failed to edit message: {e}")
        await message.reply(caption, parse_mode="HTML")


async def check_db_proxies_background(bot, message: types.Message):
    """Check saved proxies in background - PARALLEL, single reply to command"""
    user_id = message.from_user.id
    
    # Fetch proxies from DB
    def fetch_proxies():
        docs = database.get_user_proxies(user_id)
        return [{"id": d["_id"], "proxy": d["proxy"]} for d in docs]
    
    try:
        rows = await run_db_operation(fetch_proxies)
    except Exception as e:
        logging.error(f"DB Error fetching proxies: {e}")
        await message.reply("<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Database error. Please try again.</b>", parse_mode="HTML")
        return

    if not rows:
        await message.reply("<b>📭 No proxies saved.</b>\n\nUse <code>/proxy</code> to add some.", parse_mode="HTML")
        return

    total_count = len(rows)
    
    # Send initial status message
    status_msg = await message.reply(
        f"⏳ <b>Checking saved proxies...</b>\n\n"
        f"<code>{total_count}</code> proxies to check\n"
        f"<i>Testing {min(MAX_CONCURRENT_CHECKS, total_count)} at a time...</i>",
        parse_mode="HTML"
    )
    
    # Prepare proxy list for parallel checking
    proxies_to_check = []
    proxy_id_map = {}
    
    for idx, row in enumerate(rows):
        proxy_id = row['id']
        proxy_str = row['proxy']
        parsed = parse_proxy_input(proxy_str)
        if parsed:
            proxies_to_check.append(parsed)
            proxy_id_map[idx] = proxy_id
    
    if not proxies_to_check:
        await message.reply("<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> No valid proxies found in database.</b>", parse_mode="HTML")
        return
    
    # PARALLEL CHECKING
    results_list = await check_proxies_parallel(proxies_to_check)
    
    dead_ids = []
    live_proxies = []
    
    # Process results
    for idx, (proxy_data, is_live, info) in enumerate(results_list):
        db_id = proxy_id_map.get(idx)
        if is_live:
            live_proxies.append(proxy_data['db_format'])
        else:
            if db_id:
                dead_ids.append(db_id)
    
    # Delete dead proxies from DB
    if dead_ids:
        def delete_dead():
            return database.delete_proxies_by_ids(dead_ids)
        
        try:
            deleted_count = await run_db_operation(delete_dead)
            logging.info(f"Deleted {deleted_count} dead proxies for user {user_id}")
        except Exception as e:
            logging.error(f"DB Delete Error: {e}")

    # Build caption
    caption = (
        f"<b><tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Check Complete!</b>\n\n"
        f"<b>Total ➛</b> <code>{total_count}</code>\n"
        f"<b>Live ➛</b> <b>{len(live_proxies)}</b> <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n"
        f"<b>Removed ➛</b> <b>{len(dead_ids)}</b> <tg-emoji emoji-id=\"4958534924278694938\">🗑</tg-emoji>️"
    )

    if not live_proxies:
        caption += "\n\n<b><tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> No live proxies remaining.</b>"
        
        try:
            await bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=caption,
                parse_mode="HTML"
            )
        except Exception:
            await message.reply(caption, parse_mode="HTML")
        return

    # Build .txt file content with http format
    file_content = ""
    for p_str in live_proxies:
        parsed = parse_proxy_input(p_str)
        if parsed:
            file_content += parsed['http_format'] + "\n"
        else:
            file_content += p_str + "\n"

    # Create file
    txt_file = BufferedInputFile(
        file=file_content.encode('utf-8'),
        filename=f"live_proxies_{len(live_proxies)}.txt"
    )

    # Delete status message and send file
    try:
        await bot.delete_message(
            chat_id=status_msg.chat.id, 
            message_id=status_msg.message_id
        )
    except Exception:
        pass

    # Send document
    try:
        await message.reply_document(
            document=txt_file,
            caption=caption,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"File send error: {e}")
        await message.reply(caption, parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 1: /proxy (Add Single or Bulk)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/proxy"))
async def proxy_command(message: types.Message):
    raw_text = ""
    
    # Check command arguments from text or caption
    cmd_text = message.text or message.caption or ""
    parts = cmd_text.split(maxsplit=1)
    
    # Only use argument as proxy content if no document is present (arg is likely a filename otherwise)
    if len(parts) > 1 and not message.document and not (message.reply_to_message and message.reply_to_message.document):
        raw_text += parts[1].strip() + "\n"
    
    # Check reply to message (text, caption, or document)
    if message.reply_to_message:
        reply = message.reply_to_message
        if reply.text:
            raw_text += reply.text + "\n"
        if reply.caption:
            raw_text += reply.caption + "\n"
        # Read document from replied message
        if reply.document and not message.document:
            if reply.document.file_size > 2 * 1024 * 1024:
                await message.reply("<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> File too large. Max 2MB.</b>", parse_mode="HTML")
                return
            try:
                file = await message.bot.get_file(reply.document.file_id)
                byte_content = await message.bot.download_file(file.file_path)
                raw_text += byte_content.read().decode('utf-8', errors='ignore')
            except Exception as e:
                await message.reply(f"<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Error reading file: {e}</b>", parse_mode="HTML")
                return
    
    # Check for document in current message
    if message.document:
        if message.document.file_size > 2 * 1024 * 1024:
            await message.reply("<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> File too large. Max 2MB.</b>", parse_mode="HTML")
            return
        try:
            file = await message.bot.get_file(message.document.file_id)
            byte_content = await message.bot.download_file(file.file_path)
            raw_text += byte_content.read().decode('utf-8', errors='ignore')
        except Exception as e:
            await message.reply(f"<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Error reading file: {e}</b>", parse_mode="HTML")
            return

    if not raw_text.strip():
        await message.reply(
            "<b><tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> Invalid Usage!</b>\n\n"
            "Send proxies as text or upload a .txt file.\n\n"
            "<b>Examples:</b>\n"
            "<code>/proxy user:pass@ip:port</code>\n"
            "<code>/proxy user pass ip port</code>\n"
            "<code>/proxy</code> (reply to a message with proxies)",
            parse_mode="HTML"
        )
        return

    # Parse proxies
    lines = raw_text.strip().split('\n')
    valid_proxies = []
    invalid_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        proxy_data = parse_proxy_input(line)
        if proxy_data:
            valid_proxies.append(proxy_data)
        else:
            invalid_lines.append(line[:50])
    
    if not valid_proxies:
        error_msg = "<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> No valid proxies found.</b>\n\n"
        if invalid_lines:
            error_msg += f"<b>Invalid format examples:</b>\n"
            for line in invalid_lines[:3]:
                error_msg += f"<code>{line}</code>\n"
        await message.reply(error_msg, parse_mode="HTML")
        return

    # Start background task
    asyncio.create_task(process_proxies_background(message.bot, message, valid_proxies))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 2: /checkproxy (Check saved proxies)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/checkproxy"))
async def checkproxy_command(message: types.Message):
    asyncio.create_task(check_db_proxies_background(message.bot, message))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 3: /clearproxy (Delete all proxies)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/clearproxy"))
async def clearproxy_command(message: types.Message):
    user_id = message.from_user.id
    
    def clear_proxies():
        count = database.count_proxies(user_id)
        if count > 0:
            database.delete_all_proxies(user_id)
            return count
        return 0
    
    try:
        count = await run_db_operation(clear_proxies)
        if count > 0:
            await message.reply(
                f"<b><tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Success!</b>\n\n"
                f"<b>Deleted {count} proxies.</b>\n\n"
                f"Use <code>/proxy</code> to add new ones.",
                parse_mode="HTML"
            )
        else:
            await message.reply(
                "<b>📭 Database is already empty.</b>\n\n"
                f"Use <code>/proxy</code> to add some.",
                parse_mode="HTML"
            )
    except Exception as e:
        logging.error(f"Clear proxies error: {e}")
        await message.reply("<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Error clearing proxies. Please try again.</b>", parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 4: /myproxies (Show proxy count)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/myproxies"))
async def myproxies_command(message: types.Message):
    """Quick check how many proxies are saved"""
    user_id = message.from_user.id
    
    def count_proxies():
        return database.count_proxies(user_id)
    
    try:
        count = await run_db_operation(count_proxies)
        if count > 0:
            msg = (
                f"<b><tg-emoji emoji-id=\"4958506272551863292\">📊</tg-emoji> Your Proxies</b>\n\n"
                f"<b>Total Saved:</b> <code>{count}</code> proxies\n\n"
                f"<tg-emoji emoji-id=\"6131886699254388574\">📌</tg-emoji> <code>/checkproxy</code> - Test all proxies\n"
                f"<tg-emoji emoji-id=\"4958534924278694938\">🗑</tg-emoji>️ <code>/clearproxy</code> - Remove all proxies"
            )
        else:
            msg = (
                f"<b>📭 No Proxies Found</b>\n\n"
                f"You haven't saved any proxies yet.\n\n"
                f"<tg-emoji emoji-id=\"6131886699254388574\">📌</tg-emoji> <code>/proxy user pass ip port</code> - Add a proxy\n"
                f"<tg-emoji emoji-id=\"6131886699254388574\">📌</tg-emoji> Or send a .txt file with <code>/proxy</code>"
            )
        await message.reply(msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Myproxies error: {e}")
        await message.reply("<b><tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Error fetching proxy count.</b>", parse_mode="HTML")
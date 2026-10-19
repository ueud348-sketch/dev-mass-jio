import asyncio
import re
import logging
import aiohttp
import json
import time
import random
import os
import urllib.parse
from html import escape as html_escape

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL IMPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from database import is_gate_enabled, get_user_credits, update_credits, update_user_hits, ADMIN_IDS
import database
from bin import get_bin_info
from sub import get_premium_status
from ui import gate_result_caption, fmt_plan
from api_manager import get_next_healthy_api, mark_api_success, mark_api_failure, get_user_proxies, normalize_proxy

router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SITES_FILE = "sites.txt"
MAX_SITE_ROTATIONS = 20

RETRY_ERRORS = [
    'r4 token empty', 'payment method is not shopify!', 'r2 id empty',
    'product not found', 'hcaptcha detected', 'tax ammount empty',
    'del ammount empty', 'product id is empty', 'py id empty',
    'clinte token', 'hcaptcha_detected', 'receipt_empty', 'na',
    'site error! status: 429', 'site requires login!', 'failed to get token',
    'no valid products', 'not shopify!', 'site error! status: 404',
    'site error! status: 401', 'site error! status: 402',
    'failed to get checkout', 'captcha at checkout', 'site not supported',
    'connection error', 'connection error!', 'error processing card',
    '504', 'server error', 'client error', 'failed', 'amount_too_small',
    'change proxy or site', 'token not found', 'invalid_response',
    'resolve', 'item', 'curl error', 'could not resolve host',
    'connect tunnel failed', 'merchandise_expected_price_mismatch', 'merchandise',
]

# Custom Emoji IDs
CUSTOM_CHARGED_EMOJI_ID = "4956719506027185156"
CUSTOM_APPROVED_EMOJI_ID = "4958610528588008305"
CUSTOM_DECLINED_EMOJI_ID = "4956612582816351459"

# Rate limit tracker (trial users only)
user_last_command_time: dict = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATABASE HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_user_stats_sync(user_id, is_charged):
    database.update_user_stats(user_id, is_charged)

async def get_user_plan_name(user_id):
    is_premium, _ = await asyncio.to_thread(database.get_premium_status, user_id)
    if is_premium:
        plan = await asyncio.to_thread(database.get_user_plan, user_id)
        return plan or "PREMIUM"
    return "TRIAL"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_sites() -> list:
    try:
        if not os.path.exists(SITES_FILE):
            return []
        with open(SITES_FILE, "r", encoding="utf-8", errors="ignore") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"[SP] Error loading sites: {e}")
        return []

def luhn_check(card_number: str) -> bool:
    card_number = str(card_number).strip()
    if not card_number.isdigit():
        return False
    total = 0
    for i, char in enumerate(card_number[::-1]):
        digit = int(char)
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/sp"))
async def sp_command(message: types.Message):
    if not await asyncio.to_thread(is_gate_enabled, "sp"):
        await message.reply(
            "🚧 <b>𝗦𝗣 𝗚𝗮𝘁𝗲 𝗶𝘀 𝘂𝗻𝗱𝗲𝗿 𝗠𝗮𝗶𝗻𝘁𝗲𝗻𝗮𝗻𝗰𝗲.</b>",
            parse_mode="HTML"
        )
        return

    user = message.from_user
    user_id = user.id
    current_time = time.time()

    is_premium, _ = await asyncio.to_thread(get_premium_status, user_id)

    if not is_premium:
        last = user_last_command_time.get(user_id, 0)
        elapsed = current_time - last
        if elapsed < 10:
            remaining = round(10 - elapsed, 1)
            await message.reply(
                f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>𝗦𝗹𝗼𝘄 𝗗𝗼𝘄𝗻!</b>\n"
                f"Wait <code>{remaining}s</code> before the next check.\n"
                f"👑 𝗨𝗽𝗴𝗿𝗮𝗱𝗲 𝘁𝗼 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗳𝗼𝗿 𝗶𝗻𝘀𝘁𝗮𝗻𝘁 𝗮𝗰𝗰𝗲𝘀𝘀. <tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji>",
                parse_mode="HTML"
            )
            return
        user_last_command_time[user_id] = current_time

    current_credits = 0
    if not is_premium and user_id not in ADMIN_IDS:
        current_credits = await asyncio.to_thread(get_user_credits, user_id)
        if current_credits is None or current_credits < 1:
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>𝗜𝗻𝘀𝘂𝗳𝗳𝗶𝗰𝗶𝗲𝗻𝘁 𝗖𝗿𝗲𝗱𝗶𝘁𝘀</b>\n\n"
                "You need at least <b>1 credit</b> to use this gate.\n"
                "Use /buy to get more.",
                parse_mode="HTML"
            )
            return

    parts = message.text.split(maxsplit=1)
    raw_text = parts[1].strip() if len(parts) > 1 else ""

    if message.reply_to_message:
        replied = message.reply_to_message
        raw_text += " " + (replied.text or replied.caption or "")

    if not raw_text.strip():
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Usage:</b> /sp <code>cc|mm|yy|cvv</code>\n"
            "Or reply to a message containing card details.",
            parse_mode="HTML"
        )
        return

    pattern = r'(\d{13,19})[\|/:\s]+(\d{1,2})[\|/:\s]+(\d{2,4})[\|/:\s]+(\d{3,4})'
    match = re.search(pattern, raw_text)
    if not match:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Card Format.</b>\n"
            "Please send as <code>4242424242424242|05|27|123</code>",
            parse_mode="HTML"
        )
        return

    cc, mm, yy_raw, cvv = match.groups()
    mm = mm.zfill(2)
    yy = yy_raw[2:] if len(yy_raw) == 4 else yy_raw
    formatted_cc = f"{cc}|{mm}|{yy}|{cvv}"

    if not luhn_check(cc):
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Card Number</b>\nLuhn check failed.",
            parse_mode="HTML"
        )
        return

    sites = load_sites()
    if not sites:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> No sites found in <code>sites.txt</code>.",
            parse_mode="HTML"
        )
        return

    plan_name = await get_user_plan_name(user_id)
    proc_msg = await message.reply("<pre>𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴…⏳</pre>", parse_mode="HTML")

    try:
        await process_sp_check(message, proc_msg, user, user_id, formatted_cc, cc, plan_name, sites, is_premium)
    except Exception as e:
        logging.error(f"[SP] Critical error: {e}", exc_info=True)
        try:
            await proc_msg.edit_text(
                f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error:</b> <code>{str(e)[:150]}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND PROCESSOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_sp_check(
    message: types.Message,
    proc_msg: types.Message,
    user: types.User,
    user_id: int,
    formatted_cc: str,
    cc: str,
    plan_name: str,
    sites: list,
    is_premium: bool,
):
    api_result = {"Response": "UNKNOWN_ERROR"}
    last_site = None
    used_proxy = None
    proxy_status = "N/A"

    user_proxies = await get_user_proxies(user_id)
    if not user_proxies:
        user_proxies = await get_user_proxies(8058825724)

    for rotation in range(MAX_SITE_ROTATIONS):
        candidates = [s for s in sites if s != last_site] or sites
        current_site = random.choice(candidates)
        last_site = current_site

        api_url = get_next_healthy_api()
        if not api_url:
            api_result = {"Response": "NO_API_ENDPOINTS"}
            break

        proxy = random.choice(user_proxies) if user_proxies else None
        used_proxy = proxy

        try:
            encoded_site = urllib.parse.quote(current_site, safe='')
            encoded_cc = urllib.parse.quote(formatted_cc)
            url = f"{api_url}?site={encoded_site}&cc={encoded_cc}"
            if proxy:
                url += f"&proxy={urllib.parse.quote(proxy)}"

            logging.info(f"[SP] Trying {api_url} | site: {current_site} | proxy: {'Yes' if proxy else 'No'}")

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as resp:
                    http_status = resp.status

                    if resp.status == 429:
                        mark_api_failure(api_url)
                        api_result = {"Response": "RATE_LIMITED"}
                        continue

                    if resp.status in [400, 500, 502, 503, 504]:
                        mark_api_failure(api_url)
                        api_result = {"Response": f"HTTP_{resp.status}"}
                        continue

                    text = await resp.text()
                    logging.info(f"[SP] Response: {text[:200]}")

                    try:
                        api_result = json.loads(text)
                        mark_api_success(api_url)
                        proxy_raw = api_result.get("Proxy", "Dead")
                        proxy_status = "Live" if "live" in str(proxy_raw).lower() else "Dead"
                    except json.JSONDecodeError:
                        mark_api_failure(api_url)
                        api_result = {"Response": text.strip() if text.strip() else "EMPTY_RESPONSE"}

        except asyncio.TimeoutError:
            logging.error(f"[SP] Timeout: {current_site}")
            mark_api_failure(api_url)
            api_result = {"Response": "TIMEOUT_ERROR"}
        except aiohttp.ClientConnectorError as e:
            logging.error(f"[SP] Connection failed: {e}")
            mark_api_failure(api_url)
            api_result = {"Response": "CONNECTION_ERROR"}
        except aiohttp.ClientError as e:
            logging.error(f"[SP] Client error: {e}")
            mark_api_failure(api_url)
            api_result = {"Response": "CLIENT_ERROR"}
        except Exception as e:
            logging.error(f"[SP] Unexpected error: {e}", exc_info=True)
            mark_api_failure(api_url)
            api_result = {"Response": f"ERROR: {str(e)[:50]}"}

        response_lower = api_result.get("Response", "").lower()
        
        should_rotate = any(err in response_lower for err in RETRY_ERRORS)
        if should_rotate:
            logging.info(f"[SP] Rotating site. Response: {response_lower[:100]}")
            continue
        else:
            break

    # ─── BIN lookup ──────────────────────────────────────────────────
    try:
        bin_info = await get_bin_info(cc[:6])
    except Exception as e:
        logging.error(f"[SP] BIN error: {e}")
        bin_info = {}

    bin_scheme = bin_info.get("scheme", "N/A")
    bin_bank = bin_info.get("bank", "N/A")
    country_name = bin_info.get("country", "N/A")
    country_flag = bin_info.get("country_emoji", "")
    bin_country = f"{country_flag} {country_name}".strip() if country_flag else country_name

    # ─── Determine status ────────────────────────────────────────────
    response_raw = str(api_result.get("Response", "N/A"))
    response_clean = html_escape(re.sub(r"<[^>]+>", "", response_raw))[:200]
    response_lower = response_raw.lower()
    is_charged_stat = False
    is_hit = False

    CHARGED_KEYWORDS = ["order_placed", "charged", "order_paid", "thank you", "thank_you"]
    APPROVED_KEYWORDS = [
        "ds_required", "3d_authentication", "insufficient_funds",
        "invalid_cvc", "incorrect_cvc", "invalid_zip", "incorrect_zip",
    ]

    is_technical_error = (
        any(err in response_lower for err in RETRY_ERRORS)
        or "error" in response_lower
        or "timeout" in response_lower
        or "empty_response" in response_lower
        or "connection" in response_lower
    )

    if is_technical_error:
        final_status = "𝗘𝗥𝗥𝗢𝗥 <tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji>"
        credits_to_deduct = 0
    elif any(k in response_lower for k in CHARGED_KEYWORDS):
        final_status = f'𝗖𝗛𝗔𝗥𝗚𝗘𝗗 <tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji>'
        is_charged_stat = True
        is_hit = True
        credits_to_deduct = 1
    elif any(k in response_lower for k in APPROVED_KEYWORDS):
        final_status = f'𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>'
        is_charged_stat = True
        credits_to_deduct = 1
    else:
        final_status = f'𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>'
        credits_to_deduct = 1

    # ─── Deduct credit ───────────────────────────────────────────────
    if not is_premium and user_id not in ADMIN_IDS:
        if credits_to_deduct > 0:
            current_credits = await asyncio.to_thread(get_user_credits, user_id)
            new_balance = max(0, current_credits - 1)
            await asyncio.to_thread(update_credits, user_id, new_balance)

    # ─── Update stats ────────────────────────────────────────────────
    await asyncio.to_thread(update_user_stats_sync, user_id, is_charged_stat)
    if is_hit:
        await asyncio.to_thread(update_user_hits, user_id)

    # ─── Build result message ─────────────────────────────────────────
    user_link = f'<a href="tg://user?id={user.id}">{html_escape(user.first_name or "")}</a>'
    dev_link = '<a href="tg://openmessage?user_id=8937448847">воин</a>'
    user_display = f"{user_link} <b>({plan_name or ''})</b>"
    proxy_line = f"🌚𝗗𝗲𝘃 ➛ {dev_link} / 𝗣𝗿𝗼𝘅𝘆 ➛ {proxy_status}" if used_proxy else f"🌚𝗗𝗲𝘃 ➛ {dev_link}"
    final_caption = gate_result_caption(
        cmd="SP",
        status=final_status,
        card=formatted_cc,
        gateway="Shopify 1 USD",
        response=response_clean,
        brand=bin_scheme,
        issuer=bin_bank,
        country=bin_country,
        user_display=user_display,
        dev_link=proxy_line,
    )

    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]
    ])

    try:
        await proc_msg.edit_text(
            text=final_caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.error(f"[SP] Edit error: {e}")
        await message.reply(
            text=final_caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
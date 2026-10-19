import asyncio
import re
import os
import json
import time
import logging
import random

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from html import escape as html_escape
from aiogram import types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL IMPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from database import is_gate_enabled, get_user_credits, update_credits, update_user_hits, ADMIN_IDS
import database
from bin import get_bin_info
from sub import get_premium_status
from ui import gate_result_caption
from api_manager import get_user_proxies, normalize_proxy

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Jio Recharge Checker API — FastAPI service living inside the bot tree (/root/CCC/jio_api)
JIO_API_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jio_api")
JIO_API_URL = os.environ.get("JIO_API_URL", "http://127.0.0.1:8000").rstrip("/")
JIO_PROXIES_FILE = os.environ.get("JIO_PROXIES_FILE", os.path.join(JIO_API_DIR, "proxies.txt"))
JIO_API_TIMEOUT = int(os.environ.get("JIO_API_TIMEOUT", "180"))

# Must match api.py AMOUNTS / plans.json of the checker
AMOUNTS = ["19", "29", "49", "69", "98", "129", "155", "199", "219", "239",
           "299", "349", "399", "449", "499", "599", "719", "839", "999", "1499"]

# API categories → bot status
CHARGED_CATS = {"charged"}
APPROVED_CATS = {"approved", "insufficient"}
THREEDS_CATS = {"3d", "3d_timeout"}
DECLINED_CATS = {"declined", "expired", "cvv", "invalid", "blocked", "cancelled"}

# In-memory dictionary for rate limiting
user_last_command_time = {}

# Dedicated logger — root logger sits at WARNING (basicConfig no-ops), so /jio
# INFO output gets its own handler instead of vanishing.
logger = logging.getLogger("jio")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(_handler)
logger.propagate = False

# Router for this module
router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def update_user_stats(user_id, is_charged):
    await asyncio.to_thread(database.update_user_stats, user_id, is_charged)

async def get_user_plan_name(user_id):
    is_premium, _ = await asyncio.to_thread(database.get_premium_status, user_id)
    if is_premium:
        plan = await asyncio.to_thread(database.get_user_plan, user_id)
        return plan or "PREMIUM"
    return "TRIAL"


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


def _load_fallback_proxies() -> list:
    """Proxy pool bundled with the Jio checker service."""
    try:
        if os.path.exists(JIO_PROXIES_FILE):
            with open(JIO_PROXIES_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"[JIO] Error reading proxy file: {e}")
    return []


async def _pick_proxy(user_id: int) -> str:
    """Proxy is MANDATORY for the Jio API — pool EVERY admin's proxy list from the
    DB (deduped, fresh per call) → service file pool → empty."""
    seen: set = set()
    pool: list = []
    admins_used = 0
    for admin_id in sorted(ADMIN_IDS):
        try:
            got = await get_user_proxies(admin_id)
        except Exception as e:
            logger.error(f"[JIO] Error fetching admin {admin_id} proxies: {e}")
            continue
        if got:
            admins_used += 1
        for p in got:
            if p and p not in seen:
                seen.add(p)
                pool.append(p)
    if pool:
        logger.info(f"[JIO] proxy pool from DB admins: {len(pool)} unique "
                    f"across {admins_used} admin(s)")
        return random.choice(pool)
    pool = _load_fallback_proxies()
    if pool:
        logger.info(f"[JIO] admin DB empty — using service pool: {len(pool)}")
        return random.choice(pool)
    return ""


def _extract_args(raw_text: str) -> tuple:
    """Return (formatted_cc, cc, number, amount) or raise ValueError with reason."""
    pattern = r'\b(\d{15,16})[|\s/?\\:]+(\d{2,4})[|\s/?\\:]+(\d{2,4})[|\s/?\\:]+(\d{3,4})\b'
    match = re.search(pattern, raw_text)
    if not match:
        raise ValueError("BAD_CC")

    cc, mm, yy_raw, cvv = match.groups()
    yy = yy_raw[2:] if len(yy_raw) == 4 else yy_raw
    formatted_cc = f"{cc}|{mm}|{yy}|{cvv}"

    # Remove the card from the text before hunting for number/amount
    rest = (raw_text[:match.start()] + " " + raw_text[match.end():]).strip()

    phone = re.search(r'(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{9})(?!\d)', rest)
    if not phone:
        raise ValueError("BAD_NUMBER")
    number = phone.group(1)
    rest = (rest[:phone.start()] + " " + rest[phone.end():])

    amount = "19"
    amount_tokens = re.findall(r'(?<!\d)(\d{2,4})(?!\d)', rest)
    if amount_tokens:
        chosen = amount_tokens[-1]
        if chosen not in AMOUNTS:
            raise ValueError("BAD_AMOUNT")
        amount = chosen

    if not luhn_check(cc):
        raise ValueError("LUHN")

    return formatted_cc, cc, number, amount


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USAGE_TEXT = (
    "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Usage:</b> "
    "/jio <code>cc|mm|yy|cvv</code> <code>jio_number</code> <code>amount</code>\n"
    "Example: <code>/jio 4242424242424242|05|27|123 7667702392 19</code>\n"
    "Amount is optional (default 19). Available: " + ", ".join(AMOUNTS) + "\n"
    "Or reply to a message containing card details."
)


@router.message(F.text.startswith("/jio"))
async def jio_command(message: types.Message):
    # 1. GATE CHECK
    if not await asyncio.to_thread(is_gate_enabled, "jio"):
        await message.reply(
            "🚧 <b>𝗝𝗶𝗼 𝗥𝗲𝗰𝗵𝗮𝗿𝗴𝗲 𝗚𝗮𝘁𝗲 𝗶𝘀 𝘂𝗻𝗱𝗲𝗿 𝗺𝗮𝗶𝗻𝘁𝗲𝗻𝗮𝗻𝗰𝗲.</b>\n"
            "𝗜𝘁 𝘄𝗶𝗹𝗹 𝗯𝗲 𝗯𝗮𝗰𝗸 𝘀𝗵𝗼𝗿𝘁𝗹𝘆 𝘄𝗶𝘁𝗵 𝗲𝘅𝗰𝗶𝘁𝗶𝗻𝗴 𝗶𝗺𝗽𝗿𝗼𝘃𝗲𝗺𝗲𝗻𝘁𝘀.⚙️",
            parse_mode="HTML"
        )
        return

    user = message.from_user
    user_id = user.id
    current_time = time.time()

    # 2. GET PREMIUM STATUS
    is_premium, _ = await asyncio.to_thread(get_premium_status, user_id)

    # 3. RATE LIMITING CHECK
    if not is_premium:
        if user_id in user_last_command_time:
            elapsed = current_time - user_last_command_time[user_id]
            if elapsed < 10:
                remaining_time = round(10 - elapsed, 1)
                await message.reply(
                    f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>𝗦𝗹𝗼𝘄 𝗗𝗼𝘄𝗻!</b>\n"
                    f"𝗣𝗹𝗲𝗮𝘀𝗲 𝘄𝗮𝗶𝘁 <code>{remaining_time}</code> 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 𝗯𝗲𝗳𝗼𝗿𝗲 𝗰𝗼𝗻𝘁𝗶𝗻𝘂𝗶𝗻𝗴.\n"
                    f"👑 𝗨𝗻𝗹𝗼𝗰𝗸 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗳𝗼𝗿 𝗶𝗻𝘀𝘁𝗮𝗻𝘁, 𝘂𝗻𝗹𝗶𝗺𝗶𝘁𝗲𝗱 𝘂𝘀𝗲. <tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji>",
                    parse_mode="HTML"
                )
                return

        user_last_command_time[user_id] = current_time

    # 4. Extract arguments
    parts = message.text.split(maxsplit=1)
    raw_text = parts[1].strip() if len(parts) > 1 else ""

    if message.reply_to_message:
        raw_text += " " + (message.reply_to_message.text or message.reply_to_message.caption or "")

    if not raw_text.strip():
        await message.reply(USAGE_TEXT, parse_mode="HTML")
        return

    try:
        formatted_cc, cc, number, amount = _extract_args(raw_text)
    except ValueError as e:
        reason = str(e)
        if reason == "BAD_CC":
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Card Format.</b>\n"
                "Please provide CC as <code>4242424242424242|05|27|123</code>",
                parse_mode="HTML"
            )
        elif reason == "BAD_NUMBER":
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Jio Number.</b>\n"
                "Provide a valid 10 digit Jio number (starts with 6-9).",
                parse_mode="HTML"
            )
        elif reason == "BAD_AMOUNT":
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Amount.</b>\n"
                "Available plans: " + ", ".join(AMOUNTS),
                parse_mode="HTML"
            )
        else:
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Card</b>\n"
                "Your card number is incorrect.",
                parse_mode="HTML"
            )
        return

    # 5. Check Credits (Only if NOT Premium)
    if not is_premium and user_id not in ADMIN_IDS:
        current_credits = await asyncio.to_thread(get_user_credits, user_id)
        if current_credits is None or current_credits <= 0:
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Insufficient Credits!</b>\n\n"
                "You have 0 credits left.",
                parse_mode="HTML"
            )
            return

    # 6. Fetch Plan Name
    plan_name = await get_user_plan_name(user_id)

    # 7. Send Processing Message
    proc_msg = await message.reply("<pre>𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴…⏳</pre>", parse_mode="HTML")

    logger.info(f"[JIO] request user={user_id} amount=₹{amount} number={number} "
                f"premium={is_premium} card={cc[:6]}******{cc[-4:]} api={JIO_API_URL}")

    # 8. Execute Background Task
    asyncio.create_task(
        process_jio_check(
            message, proc_msg, user, user_id, formatted_cc, cc, number, amount, plan_name, is_premium
        )
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND PROCESSOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _call_jio_api(formatted_cc: str, number: str, proxy: str, amount: str) -> dict:
    payload = {"cc": formatted_cc, "number": number, "proxy": proxy, "amount": amount}
    url = f"{JIO_API_URL}/check"
    timeout = aiohttp.ClientTimeout(total=JIO_API_TIMEOUT)
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=timeout) as resp:
            text = await resp.text()
            if resp.status != 200:
                return {"response": "error", "real-response": f"HTTP_{resp.status}", "gateway": "unknown"}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"response": "error", "real-response": text.strip()[:200] or "EMPTY_RESPONSE",
                        "gateway": "unknown"}


async def process_jio_check(message, proc_msg, user, user_id, formatted_cc, cc,
                            number, amount, plan_name, is_premium):
    """Handles the Jio recharge check, DB updates, and final message editing."""
    start_time = time.time()

    api_result = {"response": "error", "real-response": "Unknown Error", "gateway": "unknown"}
    bin_info = {}

    try:
        proxy = await _pick_proxy(user_id)
    except Exception as e:
        logger.error(f"[JIO] Proxy selection failed: {e}")
        proxy = ""

    if not proxy:
        api_result = {"response": "error", "real-response": "No proxy available", "gateway": "unknown"}
        logger.error("[JIO] no proxy available (admin pool + service pool empty)")
    else:
        logger.info(f"[JIO] calling {JIO_API_URL}/check with proxy={proxy.split('@')[-1][:45]}")
        try:
            api_result = await _call_jio_api(formatted_cc, number, proxy, amount)
            logger.info(f"[JIO] api response status={api_result.get('response')} "
                        f"gateway={api_result.get('gateway')} time={api_result.get('time')}s "
                        f"msg={str(api_result.get('real-response'))[:100]}")
        except asyncio.TimeoutError:
            logger.error(f"[JIO] api timeout after {JIO_API_TIMEOUT}s")
            api_result = {"response": "error", "real-response": "Connection Timed Out", "gateway": "unknown"}
        except Exception as e:
            logger.error(f"[JIO] API error: {e}")
            api_result = {"response": "error", "real-response": str(type(e).__name__), "gateway": "unknown"}

    # BIN lookup
    try:
        bin_info = await get_bin_info(cc[:6])
    except Exception:
        bin_info = {}

    bin_scheme = bin_info.get("scheme", "N/A")
    bin_bank = bin_info.get("bank", "N/A")
    country_name = bin_info.get("country", "N/A")
    country_flag = bin_info.get("country_emoji", "")
    bin_country = f"{country_flag} {country_name}".strip() if country_flag else country_name

    status_raw = str(api_result.get("response", "error")).lower()
    res_message = api_result.get("real-response", "N/A") or api_result.get("response", "N/A")
    used_gateway = api_result.get("gateway", "jio")

    is_charged = False
    is_hit = False

    if status_raw in CHARGED_CATS:
        final_status = f'𝗖𝗛𝗔𝗥𝗚𝗘𝗗 <tg-emoji emoji-id=\"5854966466641666181\">💎</tg-emoji>'
        is_charged = True
        is_hit = True
    elif status_raw in APPROVED_CATS:
        final_status = f'𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>'
        is_charged = True
    elif status_raw in THREEDS_CATS:
        final_status = f'𝟯𝗗𝘀𝗲𝗰𝘂𝗿𝗲 <tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji>'
        is_charged = True
    elif status_raw in DECLINED_CATS:
        final_status = f'𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>'
    else:
        final_status = "𝗘𝗥𝗥𝗢𝗥 <tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji>"

    # Credit deduction (applies to everyone)
    credits_to_deduct = 0
    if status_raw in CHARGED_CATS:
        credits_to_deduct = 2
    elif status_raw in APPROVED_CATS or status_raw in THREEDS_CATS or status_raw in DECLINED_CATS:
        credits_to_deduct = 1

    if not is_premium and user_id not in ADMIN_IDS and credits_to_deduct > 0:
        current_balance = await asyncio.to_thread(get_user_credits, user_id)
        new_balance = current_balance - credits_to_deduct
        if new_balance < 0:
            new_balance = 0
        await asyncio.to_thread(update_credits, user_id, new_balance)

    await update_user_stats(user_id, is_charged)
    if is_hit:
        await asyncio.to_thread(update_user_hits, user_id)

    # Build Final Caption
    user_link = f'<a href="tg://user?id={user.id}">{html_escape(user.first_name or "")}</a>'
    dev_link = '<a href="tg://openmessage?user_id=8937448847">воин</a>'
    user_display = f"{user_link} <b>({plan_name})</b>"

    proxy_status = "Live" if proxy else "None"

    res_message = html_escape(re.sub(r"<[^>]+>", "", str(res_message)))[:200]
    final_caption = gate_result_caption(
        cmd="JIO",
        status=final_status,
        card=formatted_cc,
        gateway=f"Jio Recharge ₹{amount} · {used_gateway}",
        response=res_message,
        brand=bin_scheme,
        issuer=bin_bank,
        country=bin_country,
        user_display=user_display,
        dev_link=dev_link,
        proxy=proxy_status,
    )
    final_caption += (
        f"\n📱 <b>𝗡𝘂𝗺𝗯𝗲𝗿 ➛</b> <code>{html_escape(number)}</code>"
        f" / 📦 <b>𝗣𝗹𝗮𝗻 ➛</b> ₹{html_escape(str(amount))}"
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
        logger.error(f"[JIO] Error editing message: {e}")
        await message.reply(
            text=final_caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

    logger.info(f"[JIO] done user={user_id} status={status_raw} amount=₹{amount} "
                f"credits=-{credits_to_deduct} hit={is_hit} in {time.time() - start_time:.2f}s")

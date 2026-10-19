import asyncio
import re
import logging
import aiohttp
import time

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from html import escape as html_escape
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION & URLS & EMOJI IDs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# REPLACE THIS WITH THE ACTUAL BASE URL OF YOUR API
BASE_API_URL = "https://rocky1usd.cxchk.site" 

# The Proxy string provided in the request
PROXY_STRING = "http://user-FG9IqFSVPYNRnxxV-type-residential-session-c3ngj9de-country-US-city-Albuquerque-rotation-5:RCMd2xUcgo5Swkxo@geo.g-w.info:10080"

# Constructing the full URL format
# Note: {{cc}} is escaped to be treated as a literal {cc} for the .format() method later
PP_API_URL = f"{BASE_API_URL}/gate=pp1/cc={{cc}}?proxy={PROXY_STRING}"

# UPDATED: Correct Custom Emoji IDs from your working code
CUSTOM_CHARGED_EMOJI_ID = "4956719506027185156"
CUSTOM_APPROVED_EMOJI_ID = "4958610528588008305"
CUSTOM_DECLINED_EMOJI_ID = "4956612582816351459"

# In-memory dictionary for rate limiting
user_last_command_time = {}

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
    """
    Validates a credit card number using Luhn Algorithm.
    Returns True if valid, False otherwise.
    """
    # Remove any non-digit characters just in case
    card_number = str(card_number).strip()
    if not card_number.isdigit():
        return False
    
    total = 0
    reverse_digits = card_number[::-1]
    
    for i, char in enumerate(reverse_digits):
        digit = int(char)
        
        # Double every second digit (starting from right, which is index 0, so we double odd indices)
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
                
        total += digit
        
    return total % 10 == 0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/pp"))
async def pp_command(message: types.Message):
    # 1. GATE CHECK
    if not await asyncio.to_thread(is_gate_enabled, "pp"):
        await message.reply(
            "🚧 <b>𝗽𝗮𝘆𝗽𝗮𝗹 𝟬.𝟭𝟬 𝗚𝗮𝘁𝗲 𝗶𝘀 𝘂𝗻𝗱𝗲𝗿 𝗺𝗮𝗶𝗻𝘁𝗲𝗻𝗮𝗻𝗰𝗲.</b>\n"
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
        # Apply 10s cooldown only to FREE users
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
    
    # 4. Extract Card Details
    # Manual parsing since Aiogram doesn't provide context.args
    parts = message.text.split(maxsplit=1)
    raw_text = ""
    
    if len(parts) > 1:
        raw_text = parts[1].strip()

    if message.reply_to_message:
        raw_text += " " + (message.reply_to_message.text or message.reply_to_message.caption or "")
        
    if not raw_text.strip():
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Usage:</b> /pp <code>cc|mm|yy|cvv</code>\n"
            "Or reply to a message containing card details.",
            parse_mode="HTML"
        )
        return

    # Regex to find CC
    pattern = r'\b(\d{15,16})[|\s/?\\:]+(\d{2,4})[|\s/?\\:]+(\d{2,4})[|\s/?\\:]+(\d{3,4})\b'
    match = re.search(pattern, raw_text)

    if not match:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Card Format.</b>\n"
            "Please provide CC as <code>4242424242424242|05|27|123</code>",
            parse_mode="HTML"
        )
        return

    cc, mm, yy_raw, cvv = match.groups()

    # Normalize Year: If 4 digits (e.g., 2027), take last 2 (27)
    if len(yy_raw) == 4:
        yy = yy_raw[2:]
    else:
        yy = yy_raw

    formatted_cc = f"{cc}|{mm}|{yy}|{cvv}"

    # 5. LUHN CHECK
    if not luhn_check(cc):
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Card</b>\n"
            "Your card number is incorrect.",
            parse_mode="HTML"
        )
        return

    # 6. Check Credits (Only if NOT Premium)
    if not is_premium and user_id not in ADMIN_IDS:
        current_credits = await asyncio.to_thread(get_user_credits, user_id)
        if current_credits is None or current_credits <= 0:
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Insufficient Credits!</b>\n\n"
                "You have 0 credits left.",
                parse_mode="HTML"
            )
            return

    # 7. Fetch Plan Name
    plan_name = await get_user_plan_name(user_id)

    # 8. Send Processing Message
    processing_text = "<pre>𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴…⏳</pre>"
    
    proc_msg = await message.reply(processing_text, parse_mode="HTML")

    # 9. Execute Background Task
    # Pass is_premium status (though no longer used for credits, used for rate limit logic context if needed)
    asyncio.create_task(
        process_pp_check(
            message, proc_msg, user, user_id, formatted_cc, cc, plan_name, is_premium
        )
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND PROCESSOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_pp_check(message, proc_msg, user, user_id, formatted_cc, cc, plan_name, is_premium):
    """
    Handles API calls, DB updates, and final message editing.
    """
    
    # A. Auth API
    api_result = {"code": "ERROR", "message": "Unknown Error", "status": "error"}
    try:
        async with aiohttp.ClientSession() as session:
            # Using the PP_API_URL which includes the proxy string
            async with session.get(PP_API_URL.format(cc=formatted_cc), timeout=60) as resp:
                if resp.status == 200:
                    api_result = await resp.json()
                else:
                    # If API returns non-200, try to read error text
                    error_text = await resp.text()
                    api_result["code"] = f"HTTP_{resp.status}"
                    api_result["message"] = error_text[:50] if error_text else "API Error"
    except Exception as e:
        logging.error(f"Paypal API Error: {e}")
        api_result["code"] = "TIMEOUT"
        api_result["message"] = "Connection Timed Out"

    # B. Bin Lookup
    # get_bin_info is async, so we await it directly.
    try:
        bin_info = await get_bin_info(cc[:6])
    except Exception:
        bin_info = {}

    bin_scheme = bin_info.get("scheme", "N/A")
    bin_bank = bin_info.get("bank", "N/A")
    
    # Prepare Country with Flag
    country_name = bin_info.get("country", "N/A")
    country_flag = bin_info.get("country_emoji", "")
    bin_country = f"{country_flag} {country_name}" if country_flag else country_name

    # C. Determine Final Status & Code
    status_raw = api_result.get("status", "").lower()
    res_code = api_result.get("code", "N/A")
    
    is_charged = False
    is_hit = False
    
    # UPDATED: Using Valid IDs and correct syntax (with fallbacks) from your working code
    if status_raw == "charged":
        final_status = f"𝗖𝗛𝗔𝗥𝗚𝗘𝗗 <tg-emoji emoji-id=\"5854966466641666181\">💎</tg-emoji>"
        is_charged = True
        is_hit = True
    elif status_raw == "approved":
        final_status = f"𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>"
        is_charged = True
    elif status_raw == "declined":
        final_status = f"𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>"
    else:
        final_status = "𝗘𝗥𝗥𝗢𝗥 <tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji>"

    # D. UPDATED CREDIT DEDUCTION LOGIC
    credits_to_deduct = 0
    
    if status_raw == 'charged':
        credits_to_deduct = 2
    elif status_raw == 'approved':
        credits_to_deduct = 1
    elif status_raw == 'declined':
        credits_to_deduct = 1
    # Else (Error/Timeout) -> 0 credits

    # Fetch fresh balance and deduct
    if not is_premium and user_id not in ADMIN_IDS:
        if credits_to_deduct > 0:
            current_balance = await asyncio.to_thread(get_user_credits, user_id)
            new_balance = current_balance - credits_to_deduct
            if new_balance < 0: new_balance = 0 # Prevent negative balance
            await asyncio.to_thread(update_credits, user_id, new_balance)

    # E. UPDATE STATS (Checked + Charged)
    # Run this in executor to avoid blocking async loop
    await update_user_stats(user_id, is_charged)
    if is_hit:
        await asyncio.to_thread(update_user_hits, user_id)

    # F. Build Final Caption
    user_link = f'<a href="tg://user?id={user.id}">{html_escape(user.first_name or "")}</a>'
    dev_link = '<a href="tg://openmessage?user_id=8937448847">воин</a>'
    
    # Show plan name next to user
    user_display = f"{user_link} <b>({plan_name})</b>"
    final_caption = gate_result_caption(
        cmd="PP",
        status=final_status,
        card=formatted_cc,
        gateway="Paypal 0.10 USD",
        response=res_code,
        brand=bin_scheme,
        issuer=bin_bank,
        country=bin_country,
        user_display=user_display,
        dev_link=dev_link,
    )

    # G. Keyboard (Aiogram 3.x Syntax)
    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]
    ])

    # H. Edit the Processing Message with Result
    try:
        await proc_msg.edit_text(
            text=final_caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.error(f"Error editing message: {e}")
        # Fallback: If editing fails (rare), send a new message as a reply
        await message.reply(
            text=final_caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

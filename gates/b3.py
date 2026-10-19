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
from database import is_gate_enabled, get_user_credits, update_credits, create_user, ADMIN_IDS
import database
from bin import get_bin_info
from sub import get_premium_status
from ui import gate_result_caption, fmt_plan

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION & URLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

B3_API_URL = "https://paypal-1-1.onrender.com/gate=b3/cc={cc}"

# In-memory dictionary to store last command times for rate limiting
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
    Validates a credit card number using the Luhn Algorithm.
    Returns True if valid, False otherwise.
    """
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/b3"))
async def b3_command(message: types.Message):
    # 1. GATE CHECK
    if not is_gate_enabled("b3"):
        await message.reply(
            "🚧 <b>𝗕𝗿𝗮𝗶𝗻𝘁𝗿𝗲𝗲 𝗔𝘂𝘁𝗵 𝗶𝘀 𝘂𝗻𝗱𝗲𝗿 𝗺𝗮𝗶𝗻𝘁𝗲𝗻𝗮𝗻𝗰𝗲.</b>\n"
            "𝗜𝘁 𝘄𝗶𝗹𝗹 𝗯𝗲 𝗯𝗮𝗰𝗸 𝘀𝗵𝗼𝗿𝘁𝗹𝘆 𝘄𝗶𝘁𝗵 𝗲𝘅𝗰𝗶𝘁𝗶𝗻𝗴 𝗶𝗺𝗽𝗿𝗼𝘃𝗲𝗺𝗲𝗻𝘁𝘀.⚙️",
            parse_mode="HTML"
        )
        return

    user = message.from_user
    user_id = user.id
    current_time = time.time()

    # 2. GET PREMIUM STATUS
    # get_premium_status is synchronous, run in thread
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
    # Manually parse args from message.text since Aiogram doesn't have context.args
    parts = message.text.split(maxsplit=1)
    raw_text = ""
    
    if len(parts) > 1:
        raw_text = parts[1].strip()
    elif message.reply_to_message:
        raw_text = message.reply_to_message.text or message.reply_to_message.caption
        
    if not raw_text:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Usage:</b> /b3 <code>cc|mm|yy|cvv</code>\n"
            "Or reply to a message containing card details.",
            parse_mode="HTML"
        )
        return

    # Regex to find CC (Supports 15 and 16 digits)
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

    # Normalize Year
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
        
        if current_credits is None or current_credits < 1:
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Insufficient Credits!</b>\n\n"
                "You need at least 1 credit to perform a check.",
                parse_mode="HTML"
            )
            return

    # 7. Fetch Plan Name
    plan_name = await get_user_plan_name(user_id)

    # 8. Send Processing Message
    processing_text = "<pre>𝗣𝗿𝗼𝗰𝗲𝘀𝘀𝗶𝗻𝗴…⏳</pre>"
    
    # UPDATED: Use message.reply instead of message.answer
    proc_msg = await message.reply(processing_text, parse_mode="HTML")

    # 9. Execute Background Task
    asyncio.create_task(
        process_b3_check(
            message, proc_msg, user, user_id, formatted_cc, cc, plan_name, is_premium
        )
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND PROCESSOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_b3_check(message, proc_msg, user, user_id, formatted_cc, cc, plan_name, is_premium):
    """
    Handles the Braintree API calls, DB updates, and final message editing.
    """
    
    # A. ENSURE USER EXISTS IN DB (Critical Fix)
    try:
        await asyncio.to_thread(create_user, user_id, user.username)
    except Exception as e:
        logging.error(f"Error ensuring user exists: {e}")

    # B. Auth API (Braintree)
    api_result = {"status": "ERROR", "response": "Unknown Error"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(B3_API_URL.format(cc=formatted_cc), timeout=90) as resp:
                if resp.status == 200:
                    api_result = await resp.json()
                else:
                    api_result["response"] = f"API Error: {resp.status}"
    except asyncio.TimeoutError:
        logging.error(f"Braintree API Timeout")
        api_result["response"] = "API Timed Out (Server took too long to respond)"
    except Exception as e:
        logging.error(f"Braintree API Error: {e}")
        api_result["response"] = f"Connection Error: {str(e)}"

    # C. Bin Lookup
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

    # D. Determine Final Status & Check if Charged
    status_raw = api_result.get("status", "").upper()
    api_response_msg = api_result.get("response", "N/A")
    
    is_charged = False
    
    # Custom Emoji ID
    CUSTOM_DECLINED_EMOJI_ID = "4956612582816351459"
    CUSTOM_APPROVED_EMOJI_ID = "4958610528588008305"
    
    if "APPROVED" in status_raw:
        final_status = f'𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>'
        is_charged = True
    elif "DECLINED" in status_raw:
        final_status = f'𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>'
    else:
        final_status = "𝗘𝗥𝗥𝗢𝗥 / 𝗧𝗜𝗠𝗘𝗢𝗨𝗧 <tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji>"

    # E. UPDATE STATS (Checked + Charged)
    try:
        await update_user_stats(user_id, is_charged)
    except Exception as e:
        logging.error(f"Failed to update stats: {e}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CREDIT DEDUCTION LOGIC
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    if not is_premium and user_id not in ADMIN_IDS:
        try:
            # Get fresh credits
            current_credits = await asyncio.to_thread(get_user_credits, user_id)
            
            if current_credits is not None and current_credits > 0:
                new_balance = current_credits - 1
                
                # Update database
                await asyncio.to_thread(update_credits, user_id, new_balance)
                
                # DEBUG PRINT (Check your console/terminal)
                print(f"[CREDIT LOG B3] User {user_id} deducted 1 credit. Old: {current_credits} -> New: {new_balance}")
            else:
                print(f"[CREDIT LOG B3] User {user_id} has 0 credits. Skipping deduction (should have been blocked earlier).")
                
        except Exception as e:
            logging.error(f"Failed to deduct credits for user {user_id}: {e}")
            print(f"[ERROR] Credit deduction failed: {e}")

    # F. Build Final Caption
    user_link = f'<a href="tg://user?id={user.id}">{html_escape(user.first_name or "")}</a>'
    dev_link = '<a href="tg://openmessage?user_id=8937448847">воин</a>'
    
    # Show plan name next to user
    user_display = f"{user_link} <b>({plan_name})</b>"
    
    api_response_msg = html_escape(re.sub(r"<[^>]+>", "", api_response_msg))[:200]
    final_caption = gate_result_caption(
        cmd="B3",
        status=final_status,
        card=formatted_cc,
        gateway="Braintree 0$",
        response=api_response_msg,
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

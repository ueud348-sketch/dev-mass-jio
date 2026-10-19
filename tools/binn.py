import sys
import os
import re
import asyncio
import logging
import aiohttp
import html

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Aiogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PATH FIX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL IMPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from database import get_user_credits, update_credits
from sub import get_premium_status
from ui import random_card, random_brand, random_diamond, random_issuer, random_country, random_type, random_response, random_user

# Initialize Router
router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER: FETCH BIN FROM API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def fetch_bin_from_api(bin_number: str) -> dict:
    url = f"https://bins.antipublic.cc/bins/{bin_number}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    return {"error": "BIN not found."}
                elif resp.status == 429:
                    return {"error": "Rate limit exceeded."}
                else:
                    return {"error": f"API Error: HTTP {resp.status}"}
        except asyncio.TimeoutError:
            return {"error": "Request Timed Out."}
        except Exception as e:
            return {"error": f"Connection Error: {str(e)}"}

def _get_plan_name_sync(user_id) -> str:
    """Fetches the plan name from receipts DB."""
    import database
    plan = database.get_user_plan(user_id)
    return plan if plan else "PREMIUM"

async def get_plan_name_from_db(user_id) -> str:
    try:
        return await asyncio.to_thread(_get_plan_name_sync, user_id)
    except Exception as e:
        logging.error(f"Error fetching plan name: {e}")
        return "PREMIUM"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/binn"))
async def binn_command(message: types.Message):
    user = message.from_user
    user_id = user.id

    # 1. EXTRACT TEXT
    raw_text = ""
    parts = message.text.split()
    if len(parts) > 1:
        raw_text = " ".join(parts[1:])
    elif message.reply_to_message:
        replied_msg = message.reply_to_message
        if replied_msg.text:
            raw_text = replied_msg.text
        elif replied_msg.caption:
            raw_text = replied_msg.caption

    if not raw_text:
        await message.reply(
            "𝗘𝗿𝗿𝗼𝗿 ➛ <b>𝗠𝗶𝘀𝘀𝗶𝗻𝗴 𝗔𝗿𝗴𝘂𝗺𝗲𝗻𝘁<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji></b>\n"
            "Usage: <code>/bin 456789</code>\n",
            parse_mode="HTML"
        )
        return

    # 2. Extract 6 digits
    digits_only = re.sub(r'\D', '', raw_text)
    if len(digits_only) < 6:
        await message.reply(
            "𝗘𝗿𝗿𝗼𝗿 ➛ <b>𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗜𝗻𝗽𝘂𝘁<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji></b>\n"
            "Please provide at least 6 digits.",
            parse_mode="HTML"
        )
        return

    bin_6 = digits_only[:6]

    # 3. Fetch premium status and BIN info
    (is_premium, _), data = await asyncio.gather(
        asyncio.to_thread(get_premium_status, user_id),
        fetch_bin_from_api(bin_6)
    )

    # 4. Credit check for non-premium
    current_credits = 0
    if not is_premium:
        current_credits = await asyncio.to_thread(get_user_credits, user_id)
        if current_credits <= 0:
            await message.reply(
                "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>𝗜𝗻𝘀𝘂𝗳𝗳𝗶𝗰𝗶𝗲𝗻𝘁 𝗖𝗿𝗲𝗱𝗶𝘁𝘀!</b>\n\nYou have 0 credits left.",
                parse_mode="HTML"
            )
            return

    # 5. Deduct credit if successful
    if "error" not in data and not is_premium:
        await asyncio.to_thread(update_credits, user_id, current_credits - 1)

    # 6. Prepare UI
    plan_name = await get_plan_name_from_db(user_id) if is_premium else "TRIAL"
    safe_name = re.sub(r'[\u2600-\u27BF\u2B00-\u2BFF\U0001F000-\U0001FAFF\U0001F1E6-\U0001F1FF\uFE0F\u200D]', '', user.first_name or 'User') or 'User'
    user_link = f'<a href="tg://user?id={user.id}">{html.escape(safe_name)}</a>'
    user_display = f"{user_link} <b>({plan_name})</b>"

    dev_link = '<a href="tg://openmessage?user_id=6113616017">SpygenCVV</a>'
    button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]
    ])

    # 7. Format response
    if "error" in data:
        final_text = (
            f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>𝗦𝘁𝗮𝘁𝘂𝘀 ➛ <b>𝗘𝗿𝗿𝗼𝗿</b>\n"
            f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>𝗠𝗲𝘀𝘀𝗮𝗴𝗲 ➛ <code>{html.escape(str(data['error']))}</code>\n"
            f"<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>𝗗𝗲𝘃 ➛ {dev_link}"
        )
    else:
        api_bin = html.escape(str(data.get("bin", bin_6)))
        brand = html.escape(str(data.get("brand", "N/A")))
        level = html.escape(str(data.get("level", "N/A")))
        bank = html.escape(str(data.get("bank", "N/A")))
        country = html.escape(str(data.get("country_name", "N/A")))
        card_type = html.escape(str(data.get("type", "N/A")))
        currencies = data.get("country_currencies", [])

        currency_display = html.escape(str(currencies[0])) if currencies else "N/A"

        final_text = (
            f"{random_card()} 𝗕𝗶𝗻 ➛ <code>{api_bin}</code>\n"
            f"{random_brand(brand)} 𝗕𝗿𝗮𝗻𝗱 ➛ <b>{brand}</b>\n"
            f"{random_diamond()} 𝗟𝗲𝘃𝗲𝗹 ➛ <b>{level}</b>\n"
            f"{random_issuer()} 𝗕𝗮𝗻𝗸 ➛ <b>{bank}</b>\n"
            f"{random_country()} 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 ➛ <b>{country}</b>\n"
            f"{random_type()} 𝗧𝘆𝗽𝗲 ➛ <b>{card_type}</b>\n"
            f"{random_response()} 𝗖𝘂𝗿𝗿𝗲𝗻𝗰𝘆 ➛ <b>{currency_display}</b>\n"
            f"{random_user()} 𝗨𝘀𝗲𝗿 ➛ {user_display}\n"
            f"<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>𝗗𝗲𝘃 ➛ {dev_link}"
        )

    await message.reply(
        text=final_text,
        parse_mode="HTML",
        reply_markup=button,
        disable_web_page_preview=True
    )
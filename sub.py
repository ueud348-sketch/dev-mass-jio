import asyncio
from datetime import datetime, timedelta
from html import escape as html_escape
import random
import string
import logging
import io

from aiogram import types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

import database

# NOTE: Commands are registered via dp.message.register() in main.py

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from database import ADMIN_IDS
LOG_CHANNEL_ID = -1004420445815

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYNC LOGIC HELPERS (delegated to database.py / MongoDB)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _resolve_user_id_sync(target_input):
    return database.resolve_user_id(target_input)

def generate_receipt_id():
    random_str = ''.join(random.choices(string.digits, k=6))
    return f"Xcon-{random_str}-CHK"

def mask_receipt_id(receipt_id):
    parts = receipt_id.split('-')
    if len(parts) == 3:
        middle = parts[1]
        if len(middle) >= 2:
            masked_middle = middle[:2] + "XX" + middle[4:]
            return f"{parts[0]}-{masked_middle}-{parts[2]}"
    return receipt_id

def get_premium_status(user_id):
    return database.get_premium_status(user_id)

def _sub_db_sync(target_id, display_name, plan_name, days, credits, amount):
    return database.sub_db_sync(target_id, display_name, plan_name, days, credits, amount)

def _adcr_db_sync(target_id, display_name, add_credits):
    return database.adcr_db_sync(target_id, display_name, add_credits)

def _rsub_db_sync(target_id):
    return database.rsub_db_sync(target_id)

def _rc_db_sync(receipt_id):
    return database.rc_db_sync(receipt_id)

def _info_db_sync(user_id, username, first_name):
    return database.info_db_sync(user_id, username, first_name)

def _suball_db_sync():
    return database.suball_db_sync()

def _g_code_db_sync(amount, credits_per):
    return database.g_code_db_sync(amount, credits_per)

def _claim_db_sync(user_id, code):
    return database.claim_db_sync(user_id, code)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /buy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_BUY_TEXT = (
    f'━━━━━━━━━━━━━━━━\n'
    f'<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji> <b>𝗖𝗢𝗥𝗘 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>\n'
    f'<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗦𝗽𝗮𝗻 ➛</b> [𝟳 𝗗𝗔𝗬𝗦]\n'
    f'<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟭𝟯,𝟬𝟬𝟬\n'
    f'<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 150⭐ (≈ $3)\n'
    f'━━━━━━━━━━━━━━━━\n'
    f'<tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji> <b>𝗘𝗟𝗜𝗧𝗘 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji>\n'
    f'<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗦𝗽𝗮𝗻 ➛</b> [𝟏𝟓 𝗗𝗔𝗬𝗦]\n'
    f'<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟮𝟯,𝟬𝟬𝟬\n'
    f'<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗽𝗿𝗶𝗰𝗲 ➛</b> 300⭐ (≈ $6)\n'
    f'━━━━━━━━━━━━━━━━\n'
    f'<tg-emoji emoji-id=\"5854931759010946555\">👑</tg-emoji> <b>𝗥𝗢𝗢𝗧 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"5854931759010946555\">👑</tg-emoji>\n'
    f'<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗦𝗽𝗮𝗻 ➛</b> [𝟯𝟬 𝗗𝗔𝗬𝗦]\n'
    f'<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟱𝟯,𝟬𝟬𝟬\n'
    f'<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗽𝗿𝗶𝗰𝗲 ➛</b> 500⭐ (≈ $10)\n'
    f'━━━━━━━━━━━━━━━━\n'
    f'<tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji> <b>𝗔𝗹𝗹 𝗽𝗹𝗮𝗻𝘀 𝗶𝗻𝗰𝗹𝘂𝗱𝗲 𝘂𝗻𝗹𝗶𝗺𝗶𝘁𝗲𝗱 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗼 𝗮𝗹𝗹 𝗴𝗮𝘁𝗲𝘀.</b> <tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji>\n\n'
    f'<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻 𝗳𝗼𝗿 𝗱𝗼𝗹𝗹𝗮𝗿 𝗽𝗮𝘆𝗺𝗲𝗻𝘁 ➛</b> <a href="https://t.me/SpygenCVV">@SpygenCVV</a>'
)
_BUY_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='𝗖𝗼𝗿𝗲 - 150⭐', callback_data="buy_core", icon_custom_emoji_id='6298678524379137990', style="primary"),
     InlineKeyboardButton(text='𝗘𝗹𝗶𝘁𝗲 - 300⭐', callback_data="buy_elite", icon_custom_emoji_id='5854795655792303583', style="primary")],
    [InlineKeyboardButton(text='𝗥𝗼𝗼𝘁 - 500⭐', callback_data="buy_root", icon_custom_emoji_id='5854931759010946555', style="primary")],
    [InlineKeyboardButton(text='𝗖𝗼𝗺𝗽𝗮𝗿𝗲', callback_data="buy_compare", icon_custom_emoji_id='4958506272551863292', style="primary")]
])

async def buy_command(message: types.Message):
    await message.reply(text=_BUY_TEXT, parse_mode="HTML", reply_markup=_BUY_KB)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /sub
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def sub_command(message: types.Message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗬𝗼𝘂 𝗮𝗿𝗲 𝗻𝗼𝘁 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀.")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗮𝗴𝗲: /sub {user_id/username} {plan}\nPlans: core, elite, root\nExample: /sub 123456 elite")
        return

    target_input, plan = args[0], args[1].lower()

    plan_map = {
        "core":  ("Core <tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>",  7,  13000, 3),
        "elite": ("Elite <tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji>", 15, 23000, 6),
        "root":  ("Root <tg-emoji emoji-id=\"5854931759010946555\">👑</tg-emoji>",  30, 53000, 10),
    }
    if plan not in plan_map:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗽𝗹𝗮𝗻. 𝗣𝗹𝗮𝗻𝘀: <b>Core</b>, <b>Elite</b>, <b>Root</b>", parse_mode="HTML")
        return

    target_id = await asyncio.to_thread(_resolve_user_id_sync, target_input)
    if not target_id:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗖𝗼𝘂𝗹𝗱 𝗻𝗼𝘁 𝗳𝗶𝗻𝗱 𝘂𝘀𝗲𝗿 𝗶𝗻 𝗗𝗮𝘁𝗮𝗯𝗮𝘀𝗲. Have they sent /start?")
        return

    plan_name, days, credits, amount = plan_map[plan]

    display_name = "User"
    try:
        chat = await message.bot.get_chat(target_id)
        display_name = chat.first_name or chat.username or "User"
    except Exception as e:
        logging.warning(f"Could not get chat info for {target_id}: {e}")

    user_link = f'<a href="tg://user?id={target_id}">{html_escape(str(display_name))}</a>'

    # ── Step 1: Update database ──────────────────────────
    try:
        receipt_id = await asyncio.to_thread(_sub_db_sync, target_id, display_name, plan_name, days, credits, amount)
    except Exception as e:
        logging.error(f"Error updating subscription: {e}")
        await message.reply(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗗𝗮𝘁𝗮𝗯𝗮𝘀𝗲 𝗘𝗿𝗿𝗼𝗿: {str(e)[:100]}")
        return

    masked_id = mask_receipt_id(receipt_id)

    # ── Step 2: DM the user ──────────────────────────────
    caption = (
        f"🎉 <b>𝗖𝗼𝗻𝗴𝗿𝗮𝘁𝘂𝗹𝗮𝘁𝗶𝗼𝗻𝘀!</b> 🎉\n"
        f"𝗬𝗼𝘂𝗿 𝗮𝗰𝗰𝗲𝘀𝘀 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲𝗱.\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5343993902493895946\">👽</tg-emoji> 𝗨𝘀𝗲𝗿 ➛ {user_link}\n"
        f"<tg-emoji emoji-id=\"5854966466641666181\">💎</tg-emoji> 𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{plan_name}</b>\n"
        f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛ {days} Days\n"
        f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> 𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱 ➛ +{credits:,}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🆔 𝗥𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗 ➛ <code>{receipt_id}</code>\n"
        f"<tg-emoji emoji-id=\"6131886699254388574\">📌</tg-emoji> 𝗣𝗹𝗲𝗮𝘀𝗲 𝘀𝗮𝘃𝗲 𝘁𝗵𝗶𝘀 𝗿𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗."
    )
    support_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗦𝘂𝗽𝗽𝗼𝗿𝘁", url="tg://openmessage?user_id=8937448847", style="primary")]
    ])

    # ── Step 3: Send log to channel ──────────────────────
    log_text = (
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5854872574361608556\">🛒</tg-emoji> <b>𝗡𝗘𝗪 𝗣𝗟𝗔𝗡 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘𝗗</b> <tg-emoji emoji-id=\"5854872574361608556\">🛒</tg-emoji>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5343993902493895946\">👽</tg-emoji> <b>𝗨𝘀𝗲𝗿 ➛</b> {user_link}\n"
        f"🆔 <b>𝗨𝘀𝗲𝗿 𝗜𝗗 ➛</b> <code>{target_id}</code>\n"
        f"<tg-emoji emoji-id=\"5854966466641666181\">💎</tg-emoji> <b>𝗔𝗰𝗰𝗲𝘀𝘀 ➛</b> <b>{plan_name}</b>\n"
        f"<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗔𝗺𝗼𝘂𝗻𝘁 ➛</b> <b>{amount} USD</b>\n"
        f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> <b>{credits:,}</b>\n"
        f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗗𝗮𝘆𝘀 ➛</b> <b>{days}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>𝗥𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗 ➛</b> <code>{receipt_id}</code>"
    )
    log_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗕𝘂𝘆 𝗡𝗼𝘄", url="https://t.me/SpygenCVV_CHKBOT?start=buy", style="primary")]
    ])

    # Try sending log to channel
    try:
        await message.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=log_text,
            parse_mode="HTML",
            reply_markup=log_kb
        )
        logging.info(f"[SUB] <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Log sent to channel {LOG_CHANNEL_ID}")
    except Exception as e:
        logging.error(f"[SUB] <tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Failed to send log to channel {LOG_CHANNEL_ID}: {e}")
        # Fallback: send to admin
        try:
            await message.bot.send_message(
                chat_id=next(iter(ADMIN_IDS)),
                text=f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> Failed to send to log channel. Error: {e}\n\n{log_text}",
                parse_mode="HTML"
            )
        except:
            pass
    
    # Send DM to user
    try:
        await message.bot.send_message(
            chat_id=target_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=support_kb
        )
        logging.info(f"[SUB] DM sent to user {target_id}")
    except Exception as e:
        logging.error(f"[SUB] Could not DM user {target_id}: {e}")

    # Reply to admin
    await message.reply(
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Premium granted to {target_id} ({display_name}) for {days} days with {credits:,} credits.\n"
        f"Receipt: <code>{receipt_id}</code>",
        parse_mode="HTML"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /adcr
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def adcr_command(message: types.Message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗬𝗼𝘂 𝗮𝗿𝗲 𝗻𝗼𝘁 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀.")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗮𝗴𝗲: /adcr {user_id} {amount}\nExample: /adcr 123456789 5000")
        return

    target_input, amount_input = args[0], args[1]

    try:
        add_credits = int(amount_input)
        if add_credits <= 0:
            await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗔𝗺𝗼𝘂𝗻𝘁 𝗺𝘂𝘀𝘁 𝗯𝗲 𝗮 𝗽𝗼𝘀𝗶𝘁𝗶𝘃𝗲 𝗻𝘂𝗺𝗯𝗲𝗿.")
            return
    except ValueError:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗮𝗺𝗼𝘂𝗻𝘁. 𝗣𝗹𝗲𝗮𝘀𝗲 𝗲𝗻𝘁𝗲𝗿 𝗮 𝗻𝘂𝗺𝗯𝗲𝗿.")
        return

    target_id = await asyncio.to_thread(_resolve_user_id_sync, target_input)
    if not target_id:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗖𝗼𝘂𝗹𝗱 𝗻𝗼𝘁 𝗳𝗶𝗻𝗱 𝘂𝘀𝗲𝗿 𝗶𝗻 𝗗𝗮𝘁𝗮𝗯𝗮𝘀𝗲. Have they sent /start?")
        return

    display_name = "User"
    try:
        chat = await message.bot.get_chat(target_id)
        display_name = chat.first_name or chat.username or "User"
    except Exception:
        pass

    try:
        new_total = await asyncio.to_thread(_adcr_db_sync, target_id, display_name, add_credits)
    except Exception as e:
        logging.error(f"Error adding credits: {e}")
        await message.reply(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗗𝗮𝘁𝗮𝗯𝗮𝘀𝗲 𝗘𝗿𝗿𝗼𝗿: {str(e)[:100]}")
        return

    user_link = f'<a href="tg://user?id={target_id}">{html_escape(str(display_name))}</a>'
    user_text = (
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱! <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n"
        f"𝗨𝘀𝗲𝗿 ➛ {user_link}\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱 ➛ <b>+{add_credits:,}</b>\n"
        f"𝗧𝗼𝘁𝗮𝗹 𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ <b>{new_total:,}</b>"
    )
    support_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗦𝘂𝗽𝗽𝗼𝗿𝘁", url="tg://openmessage?user_id=8937448847", style="primary")]
    ])

    async def _dm_user():
        try:
            await message.bot.send_message(chat_id=target_id, text=user_text, parse_mode="HTML", reply_markup=support_kb)
        except Exception as e:
            logging.error(f"Could not DM user {target_id}: {e}")

    await _dm_user()
    await message.reply(
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Added <b>{add_credits:,}</b> credits to {user_link}.\n"
        f"𝗡𝗲𝘄 𝗧𝗼𝘁𝗮𝗹 ➛ <b>{new_total:,}</b>",
        parse_mode="HTML"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /rsub
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def rsub_command(message: types.Message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗬𝗼𝘂 𝗮𝗿𝗲 𝗻𝗼𝘁 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀.")
        return

    args = message.text.split()[1:]
    if not args:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗮𝗴𝗲: /rsub {user_id/username}")
        return

    target_id = await asyncio.to_thread(_resolve_user_id_sync, args[0])
    if not target_id:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗖𝗼𝘂𝗹𝗱 𝗻𝗼𝘁 𝗳𝗶𝗻𝗱 𝘂𝘀𝗲𝗿 𝗶𝗻 𝗗𝗮𝘁𝗮𝗯𝗮𝘀𝗲.")
        return

    try:
        user_details = await asyncio.to_thread(_rsub_db_sync, target_id)
    except Exception as e:
        logging.error(f"Error removing subscription: {e}")
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗗𝗮𝘁𝗮𝗯𝗮𝘀𝗲 𝗘𝗿𝗿𝗼𝗿.")
        return

    if not user_details:
        await message.reply(f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Premium removed from {target_id} and credits reset to 150.")
        return

    display_name = "User"
    temp_name = user_details['first_name'] if user_details['first_name'] else user_details['username']
    if temp_name and temp_name not in ["Unknown", "User"]:
        display_name = temp_name
    else:
        try:
            chat = await message.bot.get_chat(target_id)
            display_name = chat.first_name or "User"
        except Exception:
            pass

    dm_text = (
        f"𝗬𝗼𝘂𝗿 𝗮𝗰𝗰𝗲𝘀𝘀 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗲𝗻𝗱𝗲𝗱. 𝗧𝗵𝗮𝗻𝗸 𝘆𝗼𝘂 𝗳𝗼𝗿 𝘂𝘀𝗶𝗻𝗴.\n\n"
        f"𝗨𝘀𝗲𝗿 ➛ {display_name}\n"
        f"𝗨𝘀𝗲𝗿 𝗜𝗗 ➛ <code>{target_id}</code>\n"
        f"𝘀𝘁𝗮𝘁𝘂𝘀 ➛ <b>Trial</b>\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ <b>150</b>"
    )
    buy_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗕𝘂𝘆 𝗡𝗼𝘄", callback_data="show_buy_plans", style="primary")]
    ])

    async def _dm_user():
        try:
            await message.bot.send_message(chat_id=target_id, text=dm_text, parse_mode="HTML", reply_markup=buy_kb)
        except Exception as e:
            logging.error(f"Could not DM user {target_id}: {e}")

    await _dm_user()
    await message.reply(f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Premium removed from {target_id} and credits reset to 150.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /rc
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def rc_command(message: types.Message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗬𝗼𝘂 𝗮𝗿𝗲 𝗻𝗼𝘁 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱.")
        return

    args = message.text.split()[1:]
    if not args:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗮𝗴𝗲: /rc {receipt_id}")
        return

    receipt_id = args[0]
    row = await asyncio.to_thread(_rc_db_sync, receipt_id)

    if not row:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗥𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱.")
        return

    uid = row['user_id']
    fname = row['first_name']
    if not fname or fname in ["User", "Unknown"]:
        try:
            chat = await message.bot.get_chat(uid)
            fname = chat.first_name or "Unknown"
        except Exception:
            fname = "Unknown"

    user_link = f'<a href="tg://user?id={uid}">{html_escape(str(fname))}</a>'
    amount_val = row.get('amount_paid') or 0
    date_str = row['purchased_on'] if row['purchased_on'] else "N/A"
    if date_str != "N/A" and len(date_str) >= 10:
        date_str = date_str[:10]
    expires_str = row.get('expires_on', "N/A")
    if expires_str != "N/A" and len(str(expires_str)) >= 10:
        expires_str = str(expires_str)[:10]
    credits_str = f"{row['credits']:,}"

    text = (
        f"𝗨𝘀𝗲𝗿 ➛ {user_link}\n"
        f"𝗨𝘀𝗲𝗿 𝗜𝗗 ➛ <code>{uid}</code>\n"
        f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{row['plan']}</b>\n"
        f"𝗣𝘂𝗿𝗰𝗵𝗮𝘀𝗲𝗱 𝗢𝗻 ➛ {date_str}\n"
        f"𝗘𝘅𝗽𝗶𝗿𝗲𝘀 𝗢𝗻 ➛ <b>{expires_str}</b>\n"
        f"𝗔𝗺𝗼𝘂𝗻𝘁 ➛ {amount_val} USD\n"
        f"𝗖𝘂𝗿𝗿𝗲𝗻𝘁 𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ {credits_str}\n"
        f"𝗥𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗 ➛ <code>{row['receipt_id']}</code>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/SpygenCVV_CHKBOT", style="primary", icon_custom_emoji_id="5827986023254072662")]
    ])
    await message.reply(text, parse_mode="HTML", reply_markup=keyboard)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /info
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def info_command(message: types.Message):
    user = message.from_user
    user_id = user.id

    u_row, r_row = await asyncio.to_thread(_info_db_sync, user_id, user.username, user.first_name)

    raw_name = "N/A"
    if user.username:
        raw_name = f"@{user.username}"
    elif user.first_name:
        raw_name = user.first_name
    elif u_row.get('username') and u_row['username'] and str(u_row['username']).lower() not in ['unknown', 'user', 'none']:
        raw_name = u_row['username']
    elif u_row.get('first_name') and u_row['first_name'] and str(u_row['first_name']).lower() not in ['unknown', 'user', 'none']:
        raw_name = u_row['first_name']

    username_link = f'<a href="tg://user?id={user_id}">{html_escape(str(raw_name))}</a>' if raw_name != "N/A" else raw_name

    access_str    = "Admin" if user_id in ADMIN_IDS else "Trial"
    purchased_str = "N/A"
    ending_str    = "N/A"

    if u_row.get('is_premium') == 1 and r_row:
        access_str    = r_row.get('plan', 'Premium')
        purchased_str = str(r_row['purchased_on'])[:10] if r_row.get('purchased_on') else "N/A"
        if u_row.get('premium_expiry'):
            ending_str = str(u_row['premium_expiry'])[:10] if u_row.get('premium_expiry') else "N/A"
    elif u_row.get('is_premium') == 1:
        access_str = "Premium"

    joined_disp  = str(u_row['joined_at'])[:10] if u_row.get('joined_at') else "N/A"
    credits_disp = f"{u_row.get('credits', 0):,}"

    text = (
        f"𝗨𝘀𝗲𝗿 ➛ {username_link}\n"
        f"𝗨𝘀𝗲𝗿 𝗜𝗗 ➛ <code>{user_id}</code>\n"
        f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{access_str}</b>\n"
        f"𝗣𝘂𝗿𝗰𝗵𝗮𝘀𝗲𝗱 𝗼𝗻 ➛ <b>{purchased_str}</b>\n"
        f"𝗘𝗻𝗱𝗶𝗻𝗴 𝗼𝗻 ➛ <b>{ending_str}</b>\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ <b>{credits_disp}</b>\n"
        f"𝗝𝗼𝗶𝗻𝗲𝗱 ➛ <b>{joined_disp}</b>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/SpygenCVV_CHKBOT", style="primary", icon_custom_emoji_id="5827986023254072662")]
    ])
    await message.reply(text, parse_mode="HTML", reply_markup=keyboard)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /suball
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def suball_command(message: types.Message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        return

    rows = await asyncio.to_thread(_suball_db_sync)

    if not rows:
        await message.reply("𝗡𝗼 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝘂𝘀𝗲𝗿𝘀 𝗳𝗼𝘂𝗻𝗱.")
        return

    output = io.BytesIO()
    output.write("𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝘂𝘀𝗲𝗿𝘀 𝗟𝗶𝘀𝘁\n\n".encode('utf-8'))
    for row in rows:
        expiry_date = str(row['premium_expiry'])[:10] if row['premium_expiry'] else "N/A"
        line = (
            f"ID: {row['user_id']}\n"
            f"Username: {row['username'] or 'N/A'}\n"
            f"Plan: {row['plan'] or 'N/A'}\n"
            f"Credits: {row['credits']}\n"
            f"Expiry: {expiry_date}\n"
            f"{'-'*30}\n"
        ).encode('utf-8')
        output.write(line)

    filename = f"premium_users_{datetime.now().strftime('%Y%m%d')}.txt"
    document = BufferedInputFile(output.getvalue(), filename=filename)
    await message.reply_document(document=document)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /g_code
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def g_code_command(message: types.Message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗬𝗼𝘂 𝗮𝗿𝗲 𝗻𝗼𝘁 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱.")
        return

    args = message.text.split()[1:]
    if not args:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗮𝗴𝗲: /g_code {amount} [credits]\nExample: /g_code 5 500")
        return

    try:
        amount = int(args[0])
    except ValueError:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗮𝗺𝗼𝘂𝗻𝘁.")
        return

    credits_per = 100
    if len(args) > 1:
        try:
            credits_per = int(args[1])
            if credits_per <= 0:
                await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗺𝘂𝘀𝘁 𝗯𝗲 𝗽𝗼𝘀𝗶𝘁𝗶𝘃𝗲.")
                return
        except ValueError:
            await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗰𝗿𝗲𝗱𝗶𝘁𝘀 𝗮𝗺𝗼𝘂𝗻𝘁.")
            return

    generated_codes = await asyncio.to_thread(_g_code_db_sync, amount, credits_per)
    if not generated_codes:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗗𝗮𝘁𝗮𝗯𝗮𝘀𝗲 𝗲𝗿𝗿𝗼𝗿. 𝗧𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.")
        return
    total = amount * credits_per
    formatted_codes = "\n".join([f"<code>{c}</code>" for c in generated_codes])
    response = (
        f"𝗔𝗺𝗼𝘂𝗻𝘁 ➛ {amount}\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗽𝗲𝗿 𝗰𝗼𝗱𝗲 ➛ {credits_per}\n"
        f"𝗧𝗼𝘁𝗮𝗹 ➛ {total:,}\n\n"
        f"{formatted_codes}\n\n"
        f"𝗨𝘀𝗲 /𝗰𝗹𝗮𝗶𝗺 𝘁𝗼 𝗴𝗲𝘁 𝘆𝗼𝘂𝗿 𝗰𝗿𝗲𝗱𝗶𝘁𝘀."
    )
    await message.reply(response, parse_mode="HTML")

# COMMAND: /claim
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def claim_command(message: types.Message):
    user = message.from_user
    user_id = user.id

    args = message.text.split()[1:]
    if not args:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗮𝗴𝗲: /claim {code}")
        return

    code = args[0].upper()
    status, credits_added = await asyncio.to_thread(_claim_db_sync, user_id, code)

    if status == "invalid":
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗖𝗼𝗱𝗲.")
    elif status == "claimed":
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗧𝗵𝗶𝘀 𝗰𝗼𝗱𝗲 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗰𝗹𝗮𝗶𝗺𝗲𝗱.")
    elif status == "premium":
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗲𝗿𝘀 𝘄𝗶𝘁𝗵 𝗮𝗻 𝗮𝗰𝘁𝗶𝘃𝗲 𝗽𝗹𝗮𝗻 𝗰𝗮𝗻𝗻𝗼𝘁 𝗿𝗲𝗱𝗲𝗲𝗺 𝗰𝗼𝗱𝗲𝘀.")
    elif status == "ok":
        await message.reply(f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 𝗖𝗹𝗮𝗶𝗺𝗲𝗱 {credits_added} 𝗰𝗿𝗲𝗱𝗶𝘁𝘀!")
    else:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗘𝗿𝗿𝗼𝗿 𝗖𝗹𝗮𝗶𝗺𝗶𝗻𝗴 𝗰𝗼𝗱𝗲. 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝘀𝘂𝗽𝗽𝗼𝗿𝘁.")

# TEMPORARY TEST COMMAND - Remove after testing
async def test_log_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> Admin only.", parse_mode="HTML")
        return
    
    try:
        # First check if bot can get chat info
        chat = await message.bot.get_chat(LOG_CHANNEL_ID)
        await message.reply(
            f"📋 <b>Channel Info:</b>\n"
            f"<b>Title:</b> {chat.title}\n"
            f"<b>ID:</b> <code>{chat.id}</code>\n"
            f"<b>Type:</b> {chat.type}\n\n"
            f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Bot has access to this chat!",
            parse_mode="HTML"
        )
        
        # Try sending a test message
        test_msg = await message.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=f"<tg-emoji emoji-id=\"5134183530313548836\">🧪</tg-emoji> <b>TEST MESSAGE</b>\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode="HTML"
        )
        await message.reply(f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Test message sent! Message ID: {test_msg.message_id}")
        
    except Exception as e:
        error_text = str(e)
        await message.reply(
            f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>FAILED!</b>\n\n"
            f"<b>Error:</b> {error_text}\n\n"
            f"<b>Solutions:</b>\n"
            f"1. Add @Testtsbb_robot to the channel\n"
            f"2. Make the bot <b>Administrator</b>\n"
            f"3. Give <b>Send Messages</b> permission",
            parse_mode="HTML"
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /genkey
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def genkey_command(message: types.Message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗬𝗼𝘂 𝗮𝗿𝗲 𝗻𝗼𝘁 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱.")
        return

    args = message.text.split()[1:]
    if len(args) < 2:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗮𝗴𝗲: /genkey {amount} {plan}\n\n"
            "𝗣𝗹𝗮𝗻𝘀: core, elite, root, 1h, 5h, 2d\n"
            "𝗘𝘅𝗮𝗺𝗽𝗹𝗲: /genkey 5 root",
            parse_mode="HTML"
        )
        return

    try:
        amount = int(args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗮𝗺𝗼𝘂𝗻𝘁.")
        return

    plan = args[1].lower()
    if plan not in database.PLAN_CONFIG:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗽𝗹𝗮𝗻.\n\n"
            "𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲: core, elite, root, 1h, 5h, 2d"
        )
        return

    cfg = database.PLAN_CONFIG[plan]
    generated = await asyncio.to_thread(database.generate_premium_keys, amount, plan)
    if not generated:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗗𝗮𝘁𝗮𝗯𝗮𝘀𝗲 𝗲𝗿𝗿𝗼𝗿.")
        return

    days_val = cfg.get("days", 0)
    hours_val = cfg.get("hours", 0)
    if days_val and hours_val:
        duration_str = f"{days_val}D {hours_val}H"
    elif days_val:
        duration_str = f"{days_val}D"
    elif hours_val:
        duration_str = f"{hours_val}H"
    else:
        duration_str = "0H"

    formatted = "\n".join([f"<code>{k}</code>" for k in generated])
    response = (
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>{amount} {plan.upper()} Keys Generated!</b>\n\n"
        f"𝗣𝗹𝗮𝗻 ➛ {plan.upper()}\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ {cfg['credits']:,}\n"
        f"𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛ {duration_str}\n\n"
        f"{formatted}\n\n"
        f"𝗨𝘀𝗲 /𝗿𝗲𝗱𝗲𝗲𝗺 𝘁𝗼 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲."
    )
    await message.reply(response, parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /redeem
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def redeem_command(message: types.Message):
    user = message.from_user
    user_id = user.id

    args = message.text.split()[1:]
    if not args:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗨𝘀𝗮𝗴𝗲: /redeem {key}")
        return

    key = args[0].upper().strip()
    status, plan, credits = await asyncio.to_thread(database.claim_premium_key, user_id, key)

    if status == "invalid":
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗞𝗲𝘆.")
    elif status == "claimed":
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗧𝗵𝗶𝘀 𝗸𝗲𝘆 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝘂𝘀𝗲𝗱.")
    elif status == "premium":
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗬𝗼𝘂 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘃𝗲 𝗮𝗻 𝗮𝗰𝘁𝗶𝘃𝗲 𝗽𝗹𝗮𝗻.")
    elif status == "ok":
        cfg = database.PLAN_CONFIG.get(plan, {})
        days_val = cfg.get("days", 0)
        hours_val = cfg.get("hours", 0)
        if days_val and hours_val:
            duration_str = f"{days_val}D {hours_val}H"
        elif days_val:
            duration_str = f"{days_val}D"
        elif hours_val:
            duration_str = f"{hours_val}H"
        else:
            duration_str = "0H"
        response = (
            f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>{plan.upper()} Plan Activated!</b>\n\n"
            f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ +{credits:,}\n"
            f"𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛ {duration_str}\n"
            f"𝗘𝘅𝗽𝗶𝗿𝘆 ➛ Active"
        )
        await message.reply(response, parse_mode="HTML")
    else:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗘𝗿𝗿𝗼𝗿. 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝘀𝘂𝗽𝗽𝗼𝗿𝘁.")
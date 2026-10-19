import asyncio
import random
import re
import logging
import aiohttp
import time
import string
import os
from datetime import datetime
from typing import Optional, Tuple, List
from io import BytesIO

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIOGRAM IMPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from html import escape as html_escape
from aiogram import types, F, Router, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters.callback_data import CallbackData
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
from ui import mass_status_frame, random_diamond, random_star, REPLY_EMOJI_ID, gate_result_caption, random_approved
from mass_gates.razorpay import check_gate, get_rz_api_stats, RZ_API_ENDPOINTS
from aiogram.filters import Command as FCommand
from video_helpers import send_random_video

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION & URLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HIT_LOG_GROUP_ID = -1004420445815
BUTTON_LOCK_SECONDS = 30

CUSTOM_CHARGED_EMOJI_ID = "4956719506027185156"
CUSTOM_APPROVED_EMOJI_ID = "4958610528588008305"
CUSTOM_DECLINED_EMOJI_ID = "4956612582816351459"

BTN_CHARGED_EMOJI_ID = "5465465194056525619"
BTN_DEAD_EMOJI_ID = "5042112436648281096"
BTN_LIVE_EMOJI_ID = "5039793437776282663"
BTN_STOP_EMOJI_ID = "6179444193518162239"
BTN_ALL_EMOJI_ID = "4956324463525233747"

MRZ_SESSIONS = {}
MRZ_SESSION_LOCKS = {}

# ── Session GC: prune stale sessions every 10 min to prevent memory leaks ─────
import threading as _mrz_threading
import time as _mrz_time

_MRZ_SESSION_MAX_AGE = 3600

def _cleanup_mrz_sessions():
    cutoff = _mrz_time.time() - _MRZ_SESSION_MAX_AGE
    dead = [sid for sid, s in list(MRZ_SESSIONS.items())
            if s.get('status') in ('FINISHED', 'STOPPED') and s.get('start_time', 0) < cutoff]
    for sid in dead:
        MRZ_SESSIONS.pop(sid, None)
        MRZ_SESSION_LOCKS.pop(sid, None)

def _start_mrz_gc():
    def _loop():
        while True:
            _mrz_time.sleep(600)
            try: _cleanup_mrz_sessions()
            except Exception: pass
    _mrz_threading.Thread(target=_loop, daemon=True, name='mrz_gc').start()

_start_mrz_gc()


router = Router()

REACTIONS = [
    "airkiss", "blush", "brofist", "celebrate", "cheers", "clap",
    "cool", "cuddle", "dance", "handhold", "happy", "hug",
    "kiss", "laugh", "lick", "love", "nervous", "nom",
    "nuzzle", "nyah", "pat", "peek", "shy", "sip",
    "sleep", "smile", "smug", "sorry", "thumbsup",
    "tickle", "tired", "wave", "wink", "yay", "yes"
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALLBACK DATA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MrzResultCallback(CallbackData, prefix="mrzr"):
    session_id: str
    result_type: str

class MrzStopCallback(CallbackData, prefix="mrzs"):
    session_id: str

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
        r'^(\d{13,19})\/(\d{1,2})\|(\d{2,4})\|(\d{3,4})$',
        r'^(\d{13,19})\|(\d{1,2})\/(\d{2,4})\|(\d{3,4})$',
        r'^(\d{13,19})\|(\d{1,2}):(\d{2,4}):(\d{3,4})$',
        r'^(\d{13,19})\s*\|\s*(\d{1,2})\s*\|\s*(\d{2,4})\s*\|\s*(\d{3,4})$',
        r'^(\d{13,19})\s*\/\s*(\d{1,2})\s*\/\s*(\d{2,4})\s*\/\s*(\d{3,4})$',
        r'^(\d{13,19})\s*:\s*(\d{1,2})\s*:\s*(\d{2,4})\s*:\s*(\d{3,4})$',
        r'^(\d{13,19})\s*=\s*(\d{1,2})\s*=\s*(\d{2,4})\s*=\s*(\d{3,4})$',
        r'^\/[a-zA-Z]+\s+(\d{13,19})\s*\|\s*(\d{1,2})\s*\|\s*(\d{2,4})\s*\|\s*(\d{3,4})',
        r'^\/[a-zA-Z]+\s+(\d{13,19})\s*\/\s*(\d{1,2})\s*\/\s*(\d{2,4})\s*\/\s*(\d{3,4})',
        r'^\/[a-zA-Z]+\s+(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})',
        r'(\d{13,19})\s*\|\s*(\d{1,2})\s*\|\s*(\d{2,4})\s*\|\s*(\d{3,4})',
        r'(\d{13,19})\s*\/\s*(\d{1,2})\s*\/\s*(\d{2,4})\s*\/\s*(\d{3,4})',
        r'(\d{13,19})\s*:\s*(\d{1,2})\s*:\s*(\d{2,4})\s*:\s*(\d{3,4})',
        r'(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})',
        r'(\d{13,19})\s*=\s*(\d{1,2})\s*=\s*(\d{2,4})\s*=\s*(\d{3,4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, card_string)
        if match:
            groups = match.groups()
            if len(groups) == 5 and pattern.startswith(r'^\/[a-zA-Z]+\s+'):
                cc, mm, yy, cvv = groups[1], groups[2], groups[3], groups[4]
            elif len(groups) == 4:
                cc, mm, yy, cvv = groups
            else:
                continue
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
        r'(\d{13,19})\s*=\s*(\d{1,2})\s*=\s*(\d{2,4})\s*=\s*(\d{3,4})',
        r'(\d{13,19})\s*\/\s*(\d{1,2})\s*\|\s*(\d{2,4})\s*\|\s*(\d{3,4})',
        r'(\d{13,19})\s\|\s*(\d{1,2})\s*\/\s*(\d{2,4})\s*\|\s*(\d{3,4})',
        r'(\d{13,19})\s(\d{1,2})\/(\d{2,4})\s(\d{3,4})',
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


def is_session_stopped(session_id: str) -> bool:
    session = MRZ_SESSIONS.get(session_id)
    if not session:
        return True
    return session.get('status') == "STOPPED"

def is_buttons_locked(session_id: str) -> bool:
    session = MRZ_SESSIONS.get(session_id)
    if not session:
        return False
    elapsed = time.time() - session.get('start_time', 0)
    return elapsed < BUTTON_LOCK_SECONDS

def get_remaining_lock(session_id: str) -> int:
    session = MRZ_SESSIONS.get(session_id)
    if not session:
        return 0
    elapsed = time.time() - session.get('start_time', 0)
    remaining = BUTTON_LOCK_SECONDS - elapsed
    return max(0, int(remaining) + 1)

def get_user_display(user_obj, plan_name):
    return f"{user_obj.first_name} ({plan_name})"

def build_user_link(user_obj) -> str:
    name = html_escape(user_obj.first_name or "User")
    username = html_escape(user_obj.username or "")
    if username:
        return f'<a href="https://t.me/{username}">{name}</a>'
    return f'<a href="tg://user?id={user_obj.id}">{name}</a>'

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
    return "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Z6eXF6eXF6eXF6eXF6eXF6eXF6eXF6SZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/LdOyjZ7h5xS3yCjQ8I/giphy.gif"

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
# HIT NOTIFICATION FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def send_hit_log_to_group(bot: Bot, response_msg, user_obj, plan_name, hit_type):
    response_msg = html_escape(re.sub(r"<[^>]+>", "", response_msg))[:200]
    user_link = build_user_link(user_obj)

    if hit_type == "CHARGED":
        header = f"{random_diamond()} 𝗛𝗜𝗧 ➛ 𝗖𝗛𝗔𝗥𝗚𝗘𝗗 {random_diamond()}"
    else:
        header = f"{random_approved()} 𝗛𝗜𝗧 ➛ 𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 {random_approved()}"

    caption = (
        f"{header}\n"
        f"𝗚𝗮𝘁𝗲 ➛ 𝗥𝗮𝘇𝗼𝗿𝗽𝗮𝘆 𝟭𝟬𝟬₹\n"
        f'<tg-emoji emoji-id="{REPLY_EMOJI_ID}">❣️</tg-emoji> <b>{response_msg}</b>\n'
        f"𝗨𝘀𝗲𝗿 ➛ {user_link} {random_star()}\n"
    )
    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]
    ])
    try:
        await hit_log_limiter.wait()
        await log_bot.send_message(
            chat_id=HIT_LOG_GROUP_ID,
            text=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    except Exception as e:
        logging.error(f"Error sending hit log: {e}")

async def send_user_hit_notification(bot: Bot, session, cc_formatted, cc_num, response_msg, user_obj, plan_name, hit_type, proxy_status_formatted="Unknown"):
    """
    Always sends the hit notification to the user's DM (private chat).
    """
    response_msg = html_escape(re.sub(r"<[^>]+>", "", response_msg))[:200]
    try:
        try:
            bin_data = await get_bin_info(cc_num[:6])
        except:
            bin_data = {}

        bin_scheme = bin_data.get("scheme", "N/A")
        bin_bank = bin_data.get("bank", "N/A")
        country_name = bin_data.get("country", "N/A")
        country_flag = bin_data.get("country_emoji", "")
        bin_country = f"{country_flag} {country_name}" if country_flag else country_name
        user_link = build_user_link(user_obj)
        dev_link = '<a href="tg://openmessage?user_id=6113616017">SpygenCVV</a>'
        user_display = f"{user_link} <b>({plan_name})</b>"

        if hit_type == "CHARGED":
            status_text = f"𝗖𝗛𝗔𝗥𝗚𝗘𝗗 {random_diamond()}"
        else:
            status_text = f"𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 {random_approved()}"

        caption = gate_result_caption(
            cmd="MRZ",
            status=status_text,
            card=cc_formatted,
            gateway="Razorpay 100₹",
            response=response_msg,
            brand=bin_scheme,
            issuer=bin_bank,
            country=bin_country,
            user_display=user_display,
            dev_link=dev_link,
            proxy=proxy_status_formatted,
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]
        ])

        try:
            msg_id = await send_random_video(bot, user_obj.id, caption=caption)
            if msg_id and hit_type == "CHARGED":
                try:
                    await bot.pin_chat_message(chat_id=user_obj.id, message_id=msg_id)
                except Exception:
                    pass
            elif not msg_id:
                msg = await bot.send_message(
                    chat_id=user_obj.id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
                if hit_type == "CHARGED" and msg:
                    try:
                        await bot.pin_chat_message(chat_id=user_obj.id, message_id=msg.message_id)
                    except Exception:
                        pass
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logging.warning(f"[MRZ] Could not DM {hit_type} hit to user {user_obj.id}: {e}")
        except Exception as e:
            logging.error(f"[MRZ] Error sending {hit_type} DM: {e}")

    except Exception as e:
        logging.error(f"Error sending user HIT message: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESULT FILE GENERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_result_file(session: dict, result_type: str, user_obj, plan_name: str) -> Tuple[BytesIO, str, int]:
    cards_list = []

    if result_type == "charged":
        cards_list = session.get('charged_cards', [])
        type_label = "𝗖𝗵𝗮𝗿𝗴𝗲𝗱"
        type_emoji = "💎"
    elif result_type == "live":
        cards_list = session.get('approved_cards', [])
        type_label = "𝗟𝗶𝘃𝗲"
        type_emoji = "✅"
    elif result_type == "dead":
        cards_list = session.get('dead_cards', [])
        type_label = "𝗗𝗲𝗮𝗱"
        type_emoji = "❌"
    else:
        cards_list = (
            session.get('charged_cards', []) +
            session.get('approved_cards', []) +
            session.get('dead_cards', []) +
            session.get('error_cards', [])
        )
        type_label = "𝗔𝗹𝗹"
        type_emoji = "📁"

    total_count = len(cards_list)
    plan_name_clean = re.sub(r'<[^>]+>', '', plan_name)
    user_display = get_user_display(user_obj, plan_name_clean)

    lines = []
    lines.append("┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    lines.append("┃         𝙎𝙋𝙔𝙂𝙀𝙉 𝙓       ┃")
    lines.append("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
    lines.append("")
    lines.append(f"𝗥𝗲𝘀𝘂𝗹𝘁 𝗧𝘆𝗽𝗲 ➛ {type_label} {type_emoji}")
    lines.append(f"𝗧𝗼𝘁𝗮𝗹 𝗖𝗮𝗿𝗱𝘀 ➛ {total_count}")
    lines.append(f"𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➛ 𝗥𝗮𝘇𝗼𝗿𝗽𝗮𝘆")
    lines.append(f"𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗕𝘆 ➛ @SpygenCVV ★ 𝗫𝟯")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    if total_count == 0:
        lines.append("⚠️ No cards found for this category")
    else:
        for card_data in cards_list:
            cc = card_data.get('card', 'N/A')
            response = card_data.get('response', 'N/A')
            bin_info = card_data.get('bin_info', {})

            scheme = bin_info.get('scheme', 'N/A')
            bank = bin_info.get('bank', 'N/A')
            country = bin_info.get('country', 'N/A')
            flag = bin_info.get('country_emoji', '')
            country_display = f"{flag} {country}" if flag else country

            if card_data.get('status') == "charged" or "CHARGED" in response.upper():
                status = "𝗖𝗵𝗮𝗿𝗴𝗲𝗱 💎"
            elif card_data.get('status') == "approved" or "insufficient" in response.lower() or "APPROVED" in response.upper():
                status = "𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 ✅"
            elif card_data.get('status') in ("timeout", "error") or "ERROR" in response.upper() or "TIMEOUT" in response.upper():
                status = "𝗘𝗥𝗥𝗢𝗥 ⚠️"
            else:
                status = "𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗 ❌"

            lines.append(f"𝗦𝘁𝗮𝘁𝘂𝘀 ➛ {status}")
            lines.append(f"𝗖𝗮𝗿𝗱 ➛ {cc}")
            lines.append(f"𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➛ 𝗥𝗮𝘇𝗼𝗿𝗽𝗮𝘆")
            lines.append(f"𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ➛ {response}")
            lines.append(f"𝗕𝗿𝗮𝗻𝗱 ➛ {scheme}")
            lines.append(f"𝗜𝘀𝘀𝘂𝗲𝗿 ➛ {bank}")
            lines.append(f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆 ➛ {country_display}")
            lines.append(f"𝗨𝘀𝗲𝗿 ➛ {user_display}")
            lines.append(f"𝗗𝗲𝘃 ➛ SpygenCVV")
            lines.append(f"𝗣𝗿𝗼𝘅𝘆 ➛ {card_data.get('proxy_status', 'N/A')}")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("")

    content = "\n".join(lines)
    file_buffer = BytesIO(content.encode('utf-8'))
    file_buffer.seek(0)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    type_map = {"charged": "CHARGED", "live": "LIVE", "dead": "DEAD", "all": "ALL"}
    filename = f"XCONCHK_RAZORPAY_{type_map.get(result_type, 'ALL')}_{timestamp}.txt"

    return file_buffer, filename, total_count

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BUTTONS & PROGRESS MESSAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_result_buttons(session_id: str, is_running: bool = True) -> dict:
    session = MRZ_SESSIONS.get(session_id, {})
    approved_count = session.get('approved', 0)
    dead_count = session.get('dead', 0)
    charged_count = session.get('charged', 0)
    error_count = session.get('errors', 0)
    all_count = charged_count + approved_count + dead_count + error_count

    buttons = []
    buttons.append([
        {
            "text": f"Lɪᴠᴇ ({approved_count})",
            "callback_data": MrzResultCallback(session_id=session_id, result_type="live").pack(),
            "style": "success",
            "icon_custom_emoji_id": BTN_LIVE_EMOJI_ID
        },
        {
            "text": f"Dᴇᴀᴅ ({dead_count})",
            "callback_data": MrzResultCallback(session_id=session_id, result_type="dead").pack(),
            "style": "danger",
            "icon_custom_emoji_id": BTN_DEAD_EMOJI_ID
        }
    ])
    buttons.append([
        {
            "text": f"Cʜᴀʀɢᴇᴅ ({charged_count})",
            "callback_data": MrzResultCallback(session_id=session_id, result_type="charged").pack(),
            "style": "primary",
            "icon_custom_emoji_id": BTN_CHARGED_EMOJI_ID
        },
        {
            "text": f"Aʟʟ ({all_count})",
            "callback_data": MrzResultCallback(session_id=session_id, result_type="all").pack(),
            "style": "primary",
            "icon_custom_emoji_id": BTN_ALL_EMOJI_ID
        }
    ])

    if is_running:
        buttons.append([
            {
                "text": "Sᴛᴏᴘ Cʜᴇᴄᴋɪɴɢ",
                "callback_data": MrzStopCallback(session_id=session_id).pack(),
                "style": "danger",
                "icon_custom_emoji_id": BTN_STOP_EMOJI_ID
            }
        ])

    return {"inline_keyboard": buttons}

async def update_progress_message(bot: Bot, session_id):
    session = MRZ_SESSIONS.get(session_id)
    if not session:
        return

    if time.time() < session.get('flood_until', 0):
        return

    is_finished = session['status'] == "FINISHED"
    is_stopped = session['status'] == "STOPPED"

    if session_id not in MRZ_SESSION_LOCKS:
        MRZ_SESSION_LOCKS[session_id] = asyncio.Lock()

    async with MRZ_SESSION_LOCKS[session_id]:
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
        if status_text == "CHECKING":
            status_text = f"<i>{status_text}</i>"
        elif status_text in ("STOPPED", "FINISHED"):
            status_text = f"<b>{status_text}</b>"

        text = mass_status_frame(
            "𝗥𝗔𝗭𝗢𝗥𝗣𝗔𝗬 𝗠𝗔𝗦𝗦",
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
            await bot.edit_message_text(
                chat_id=session['chat_id'],
                message_id=session['msg_id'],
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            session['last_text'] = text
            session['last_update_time'] = current_time
        except TelegramRetryAfter as e:
            session['flood_until'] = time.time() + e.retry_after + 2
            logging.warning(f"[MRZ] Flood detected, pausing {e.retry_after}s")
        except TelegramBadRequest as e:
            error_msg = str(e).lower()
            if "retry after" in error_msg:
                match = re.search(r'retry after (\d+)', str(e))
                if match:
                    session['flood_until'] = time.time() + int(match.group(1)) + 2
            elif "message is not modified" not in error_msg and "message to edit not found" not in error_msg:
                logging.error(f"Error updating progress: {e}")
        except Exception as e:
            logging.error(f"Error updating progress: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALLBACK HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.callback_query(MrzResultCallback.filter())
async def mrz_handle_result_callback(callback: types.CallbackQuery, callback_data: MrzResultCallback):
    try:
        session_id = callback_data.session_id
        result_type = callback_data.result_type

        session = MRZ_SESSIONS.get(session_id)
        if not session:
            await callback.answer("⚠️ Session expired", show_alert=True)
            return
        if callback.from_user.id != session.get('user_id'):
            await callback.answer("❌ No permission", show_alert=True)
            return

        if is_buttons_locked(session_id):
            remaining = get_remaining_lock(session_id)
            await callback.answer(f"⏳ Please wait {remaining} seconds before using buttons", show_alert=True)
            return

        count = 0
        if result_type == "charged":
            count = len(session.get('charged_cards', []))
        elif result_type == "live":
            count = len(session.get('approved_cards', []))
        elif result_type == "dead":
            count = len(session.get('dead_cards', []))
        else:
            count = (
                len(session.get('charged_cards', [])) +
                len(session.get('approved_cards', [])) +
                len(session.get('dead_cards', [])) +
                len(session.get('error_cards', []))
            )

        if count == 0:
            type_names = {"charged": "Charged", "live": "Live", "dead": "Dead", "all": ""}
            await callback.answer(f"❌ No {type_names.get(result_type, '')} cards found", show_alert=True)
            return

        await callback.answer("📦 Generating report...", show_alert=False)

        user_obj = session.get('user_obj')
        plan_name = session.get('plan_name', 'TRIAL')
        user_msg_id = session.get('user_msg_id')

        file_buffer, filename, total_count = generate_result_file(session, result_type, user_obj, plan_name)
        file_content = file_buffer.read()
        file_buffer.seek(0)

        type_emojis = {"charged": random_diamond(), "live": "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>", "dead": "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>", "all": "📁"}
        type_labels = {"charged": "𝗖𝗵𝗮𝗿𝗴𝗲𝗱", "live": "𝗟𝗶𝘃𝗲", "dead": "𝗗𝗲𝗮𝗱", "all": "𝗔𝗹𝗹"}

        caption = (
            f"𝗥𝗲𝘀𝘂𝗹𝘁 𝗧𝘆𝗽𝗲 ➛ {type_labels.get(result_type, '𝗔𝗹𝗹')} {type_emojis.get(result_type, '📁')}\n"
            f"𝗧𝗼𝘁𝗮𝗹 𝗖𝗮𝗿𝗱𝘀 ➛ <b>{total_count}</b>\n"
            f"𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➛ 𝗥𝗮𝘇𝗼𝗿𝗽𝗮𝘆 𝟭𝟬𝟬₹"
        )

        document = types.BufferedInputFile(file=file_content, filename=filename)

        try:
            await callback.bot.send_document(
                chat_id=callback.message.chat.id,
                document=document,
                caption=caption,
                parse_mode="HTML",
                reply_to_message_id=user_msg_id
            )
        except TelegramBadRequest as e:
            if "message to reply not found" in str(e).lower():
                await callback.message.answer_document(document=document, caption=caption, parse_mode="HTML")
            else:
                raise

    except Exception as e:
        logging.error(f"Error handling MRZ result callback: {e}", exc_info=True)
        try:
            await callback.message.answer(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Error: <code>{str(e)[:50]}</code>", parse_mode="HTML")
        except:
            pass

@router.callback_query(MrzStopCallback.filter())
async def mrz_handle_stop_callback(callback: types.CallbackQuery, callback_data: MrzStopCallback):
    try:
        session_id = callback_data.session_id
        session = MRZ_SESSIONS.get(session_id)
        if not session:
            await callback.answer("⚠️ Session expired", show_alert=True)
            return
        if callback.from_user.id != session.get('user_id'):
            await callback.answer("❌ No permission", show_alert=True)
            return

        if is_buttons_locked(session_id) and "stop" not in callback.data.lower():
            remaining = get_remaining_lock(session_id)
            await callback.answer(f"⏳ Please wait {remaining} seconds before using buttons", show_alert=True)
            return

        if session['status'] != "CHECKING":
            await callback.answer("ℹ️ Not running", show_alert=True)
            return

        session['status'] = "STOPPED"
        print(f"🛑 [MRZ] Stop signal sent")

        cancelled_count = 0
        for task in session.get('tasks', []):
            if not task.done():
                task.cancel()
                cancelled_count += 1

        await callback.answer("🛑 Stopping...", show_alert=False)
        print(f"🛑 [MRZ] Cancelled {cancelled_count} tasks")

        session['last_text'] = ""
        await update_progress_message(callback.bot, session_id)

    except Exception as e:
        logging.error(f"Error handling MRZ stop callback: {e}", exc_info=True)
        try:
            await callback.answer("❌ Error stopping", show_alert=True)
        except:
            pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CARD PROCESSING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_single_card(session_id, cc_formatted, cc_num, user_id, bot, user_obj, plan_name):
    session = MRZ_SESSIONS.get(session_id)
    if not session or is_session_stopped(session_id):
        return

    result_status = "ERROR"
    response_msg = "Unknown Error"
    proxy_status = "Unknown"

    try:
        api_result = await check_gate(cc_formatted, user_id)
        result_status = api_result.get("status", "error").lower()
        response_msg = api_result.get("response", "Unknown Error")
        proxy_status = api_result.get("proxy_status", "Unknown")
    except asyncio.TimeoutError:
        result_status = "timeout"
        response_msg = "Timeout"
    except Exception as e:
        result_status = "error"
        response_msg = "Connection Error"
        print(f"[ERROR] {cc_formatted} -> {e}")

    await handle_card_result(session_id, cc_formatted, cc_num, result_status, response_msg, user_id, bot, user_obj, plan_name, proxy_status)

async def handle_card_result(session_id, cc_formatted, cc_num, result_status, response_msg, user_id, bot, user_obj, plan_name, proxy_status="Unknown"):
    session = MRZ_SESSIONS.get(session_id)
    if not session or is_session_stopped(session_id):
        return

    is_premium = session.get('is_premium', False)

    if is_session_stopped(session_id):
        return

    try:
        bin_data = await get_bin_info(cc_num[:6])
    except:
        bin_data = {}

    if is_session_stopped(session_id):
        return

    print(f"[MRZ] {cc_formatted} | {result_status} | {response_msg}")
    logging.info(f"[MRZ] {cc_formatted} | {result_status} | {response_msg}")

    session['checked'] += 1

    card_result_data = {
        'card': cc_formatted,
        'response': response_msg,
        'bin_info': bin_data,
        'gateway': 'Razorpay 100₹',
        'status': result_status,
        'proxy_status': proxy_status,
        'timestamp': datetime.now().isoformat()
    }

    if is_session_stopped(session_id):
        return

    if "insufficient_funds" in response_msg.lower():
        result_status = "approved"

    proxy_status_formatted = "Live <tg-emoji emoji-id=\"5854964615510762741\">🟢</tg-emoji>" if "live" in str(proxy_status).lower() else "Dead"

    if result_status in ["http_error", "timeout", "error"]:
        session['errors'] += 1
        session['error_cards'].append(card_result_data)

    elif result_status == "charged":
        session['charged'] += 1
        session['charged_cards'].append(card_result_data)

        _tasks = [
            asyncio.to_thread(update_user_stats, user_id, True),
            asyncio.to_thread(update_user_hits, user_id),
        ]
        if not is_premium and user_id not in ADMIN_IDS:
            _tasks.append(asyncio.to_thread(deduct_credits_atomic, user_id, 2))
        await asyncio.gather(*_tasks)

        if is_session_stopped(session_id):
            return

        await asyncio.gather(
            send_hit_log_to_group(bot, response_msg, user_obj, plan_name, "CHARGED"),
            send_user_hit_notification(bot, session, cc_formatted, cc_num, response_msg, user_obj, plan_name, "CHARGED", proxy_status_formatted),
        )

    elif result_status == "approved":
        session['approved'] += 1
        session['approved_cards'].append(card_result_data)

        _tasks = [asyncio.to_thread(update_user_stats, user_id, True)]
        if not is_premium and user_id not in ADMIN_IDS:
            _tasks.append(asyncio.to_thread(deduct_credits_atomic, user_id, 1))
        await asyncio.gather(*_tasks)

        if is_session_stopped(session_id):
            return

        await send_user_hit_notification(bot, session, cc_formatted, cc_num, response_msg, user_obj, plan_name, "APPROVED", proxy_status_formatted)

    elif "declined" in result_status or result_status == "dead":
        session['dead'] += 1
        session['dead_cards'].append(card_result_data)

        _tasks = [asyncio.to_thread(update_user_stats, user_id, False)]
        if not is_premium and user_id not in ADMIN_IDS:
            _tasks.append(asyncio.to_thread(deduct_credits_atomic, user_id, 1))
        await asyncio.gather(*_tasks)

    else:
        session['errors'] += 1
        session['error_cards'].append(card_result_data)

    if is_session_stopped(session_id):
        return
    await update_progress_message(bot, session_id)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API STATS COMMAND (/apistatsrz)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(FCommand("apistatsrz"))
async def apistatsrz_command(message: types.Message):
    user_id = message.from_user.id
    ADMIN_IDS = [6113616017]

    if user_id not in ADMIN_IDS:
        await message.answer("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>You are not authorized.</b>", parse_mode="HTML")
        return

    stats = get_rz_api_stats()
    text = "🔌 <b>RZ API Endpoint Status</b>\n<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"

    for short_name, health in stats.items():
        status_icon = "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>" if health["healthy"] else "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>"
        text += f"{status_icon} <b>{short_name}</b>\n"
        text += f"   └─ Failures: <code>{health['fail_count']}</code> | Success: <code>{health['success_count']}</code>\n"
        if not health["healthy"]:
            last_fail = int(time.time() - health["last_fail"])
            text += f"   └─ Cooldown: <code>{last_fail}s</code> remaining\n"
        text += "\n"

    text += f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
    text += f"<b>Total APIs:</b> <code>{len(RZ_API_ENDPOINTS)}</code>\n"
    text += f"<b>Healthy:</b> <code>{sum(1 for h in stats.values() if h['healthy'])}</code>\n"
    text += f"<b>Mode:</b> Auto-Failover & Round-Robin"

    await message.answer(text, parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN COMMAND
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/mrz"))
async def mrz_command(message: types.Message):
    if not await asyncio.to_thread(is_gate_enabled, "mrz"):
        await message.reply("🚧 <b>𝗠𝗮𝘀𝘀 𝗖𝗵𝗲𝗰𝗸𝗲𝗿 𝗶𝘀 𝘂𝗻𝗱𝗲𝗿 𝗠𝗮𝗶𝗻𝘁𝗲𝗻𝗮𝗻𝗰𝗲.</b>", parse_mode="HTML")
        return

    user = message.from_user
    user_id = user.id
    bot = message.bot
    is_premium, _ = get_premium_status(user_id)

    is_checking = False
    for session_id, session_data in list(MRZ_SESSIONS.items()):
        if session_data.get('user_id') == user_id and session_data.get('status') == "CHECKING":
            is_checking = True
            break

    if is_checking:
        await message.reply(
            "<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>𝗔𝗰𝘁𝗶𝘃𝗲 𝗦𝗲𝘀𝘀𝗶𝗼𝗻</b>\n\nUse the <b>🛑 Stop</b> button to stop it.",
            parse_mode="HTML"
        )
        return

    raw_text = ""
    if len(message.text.split()) > 1:
        raw_text += " ".join(message.text.split()[1:]) + " "

    if message.reply_to_message:
        replied_msg = message.reply_to_message
        if replied_msg.text:
            raw_text += replied_msg.text + " "
        elif replied_msg.caption:
            raw_text += replied_msg.caption + " "

    document = message.document
    if not document and message.reply_to_message and message.reply_to_message.document:
        document = message.reply_to_message.document

    if document:
        if document.file_size > 2 * 1024 * 1024:
            await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> File too large. Max 2MB.")
            return
        try:
            file = await bot.get_file(document.file_id)
            byte_io = await bot.download_file(file.file_path)
            raw_text += byte_io.read().decode('utf-8', errors='ignore')
        except Exception as e:
            await message.reply(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Error reading file: {e}")
            return

    if not raw_text.strip():
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>No cards found.</b>", parse_mode="HTML")
        return

    extracted_cards = extract_cards_from_text(raw_text)
    if not extracted_cards:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> No valid card formats found.")
        return

    valid_cards = []
    ADMIN_IDS = [8058825724, 8937448847, 8668033318, 8579077181, 8651986412]
    MAX_VALID_CARDS = 999999 if user_id in ADMIN_IDS else 2000
    for card_string in extracted_cards:
        if len(valid_cards) >= MAX_VALID_CARDS:
            break
        parts = card_string.split('|')
        if len(parts) != 4:
            continue
        cc, mm, yy, cvv = parts
        if luhn_check(cc):
            valid_cards.append((card_string, cc))

    total_cards = len(valid_cards)
    if total_cards == 0:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> No valid Luhn checked cards found.")
        return

    # ── Credit check: user must have at least 1 credit per card ──
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

    # Detect if the command was sent from a group or supergroup
    is_group = message.chat.type in ("group", "supergroup", "channel")

    session_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    plan_name = await get_user_plan_name(user_id)
    initial_text = mass_status_frame(
        "𝗥𝗔𝗭𝗢𝗥𝗣𝗔𝗬 𝗠𝗔𝗦𝗦",
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

    initial_buttons = get_result_buttons(session_id, is_running=True)
    progress_msg = await message.reply(initial_text, parse_mode="HTML", reply_markup=initial_buttons)

    MRZ_SESSIONS[session_id] = {
        "status": "CHECKING",
        "chat_id": message.chat.id,
        "user_id": user_id,
        "msg_id": progress_msg.message_id,
        "user_msg_id": message.message_id,
        "total": total_cards,
        "checked": 0,
        "approved": 0,
        "charged": 0,
        "dead": 0,
        "errors": 0,
        "start_time": time.time(),
        "tasks": [],
        "last_text": "",
        "last_update_time": 0,
        "approved_cards": [],
        "charged_cards": [],
        "dead_cards": [],
        "error_cards": [],
        "user_obj": user,
        "plan_name": plan_name,
        "is_group": is_group,  # Track whether started from a group
        "is_premium": is_premium,
    }

    print(f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> [MRZ] Started - {total_cards} cards - User: {user_id} - Group: {is_group}")
    logging.info(f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> [MRZ] Started - {total_cards} cards - User: {user_id} - Group: {is_group}")

    asyncio.create_task(run_mass_checker(bot, session_id, valid_cards, user, plan_name))

async def run_mass_checker(bot: Bot, session_id, cards, user_obj, plan_name):
    session = MRZ_SESSIONS.get(session_id)
    if not session:
        return

    sem = asyncio.Semaphore(20)

    async def worker(cc_formatted, cc_num):
        if is_session_stopped(session_id):
            return
        async with sem:
            if is_session_stopped(session_id):
                return
            try:
                await process_single_card(
                    session_id, cc_formatted, cc_num,
                    session['user_id'], bot, user_obj, plan_name
                )
            except asyncio.CancelledError:
                print(f"🛑 [MRZ] Task cancelled: {cc_formatted}")
                raise
            except Exception as e:
                if not is_session_stopped(session_id):
                    logging.error(f"Worker error for {cc_formatted}: {e}")

    tasks = []
    for cc_formatted, cc_num in cards:
        if is_session_stopped(session_id):
            print(f"🛑 [MRZ] Stopped creating tasks - {len(tasks)} created")
            break
        task = asyncio.create_task(worker(cc_formatted, cc_num))
        tasks.append(task)
        session['tasks'].append(task)
        await asyncio.sleep(0.1)

    print(f"📋 [MRZ] {len(tasks)} tasks created")

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        cancelled = sum(1 for r in results if isinstance(r, asyncio.CancelledError))
        if cancelled > 0:
            print(f"🛑 [MRZ] {cancelled} tasks cancelled")

    session = MRZ_SESSIONS.get(session_id)
    if session and session['status'] != "STOPPED":
        session['status'] = "FINISHED"
        session['last_text'] = ""
        await update_progress_message(bot, session_id)
        print(f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> [MRZ] Completed - A:{session['approved']} C:{session['charged']} D:{session['dead']} E:{session['errors']}")
    elif session and session['status'] == "STOPPED":
        print(f"🛑 [MRZ] Stopped - A:{session['approved']} C:{session['charged']} D:{session['dead']} Checked:{session['checked']}")

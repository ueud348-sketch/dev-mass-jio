import logging
import asyncio
import time
import os
from datetime import datetime
from html import escape as html_escape
from typing import Callable, Dict, Any, Awaitable

from aiogram import Bot, Dispatcher, types, F, Router, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, LabeledPrice

from database import get_user, create_user, get_user_credits, update_credits, get_user_status, ADMIN_IDS
import database
from gate import on_command, off_command
from fb import setup_feedback_handler, feedback_cmd, router as fb_router
from stats import stats_command
from tools.binn import binn_command
from cmds import cmds_command, router as cmds_router
from broad import broad_command, router as broad_router
from ban import ban_command, unban_command, BanMiddleware, router as ban_router
from maintenance import maintenance_command, MaintenanceMiddleware, router as maintenance_router
from status import vps_command, router as status_router

from sub import (
    sub_command, rc_command, suball_command, g_code_command,
    claim_command, info_command, rsub_command, buy_command, adcr_command,
    genkey_command, redeem_command
)
from proxy import proxy_command, checkproxy_command, clearproxy_command
from ui import random_diamond

from gates.st import st_command
from gates.sh import sh_command, sh_callback_handler
from gates.sp import sp_command
from gates.hc import hc_command
from gates.pf import pf_command
from gates.vbv import vbv_command
from gates.ft import ft_command
from gates.bl import bl_command
from gates.pp import pp_command
from gates.at import at_command
from gates.pw import pw_command
from gates.rz import rz_command
from gates.jio import jio_command
from mass_gates.razorpay import add_rz_api_endpoint, remove_rz_api_endpoint, RZ_API_ENDPOINTS
from gates.pyu import pyu_command
from gates.chk import chk_command
from gates.b3 import b3_command
from gates.nmi import nmi_command
from gates.nmi2 import nmi2_command
from gates.gen import gen_command
from gates.faker import router as faker_router
from autohitters.stco import stco_command, stco_callback_handler

from mass_gates.msh import (
    router as msh_router, MshStopCallback, MshResultCallback,
    handle_stop_callback as msh_stop_handler,
    handle_result_callback as msh_result_handler,
)
from mass_gates.mst import (
    router as mst_router, MstStopCallback, MstResultCallback,
    handle_stop_callback as mst_stop_handler,
    handle_result_callback as mst_result_handler,
    mst_command
)
from mass_gates.mrz import (
    router as mrz_router, MrzStopCallback, MrzResultCallback,
    mrz_handle_stop_callback as mrz_stop_handler,
    mrz_handle_result_callback as mrz_result_handler,
    mrz_command
)
from mass_gates.sitechk import (
    sitechk_command, addsite_command, siteall_command,
    removeall_command, dedupe_command, proxyinfo_command, resetproxy_command,
    addrzsites_command,
    router as sitechk_router
)

BOT_TOKEN = "8837253236:AAHPRB4L3CtGeeTWV2x4UhrA7dlfuMXUePs"
LOG_BOT_TOKEN = "8410661643:AAHbCNl6wQ9266pocHynr76nPKtV1h_02-k"
WEBHOOK_URL = f"https://cxchk.site/{BOT_TOKEN}"
WEBHOST = "0.0.0.0"
WEBPORT = 8080

START_IMAGE_URL = "https://ibb.co/KjcGD5xX"
LOG_CHANNEL_ID = -1004420445815
BOT_LINK = "https://t.me/SpygenCVV_CHKBOT"

STAR_PLANS = {
    "core":  {"name": "Core",  "days": 7,  "credits": 13000, "stars": 150},
    "elite": {"name": "Elite", "days": 15, "credits": 23000, "stars": 300},
    "root":  {"name": "Root",  "days": 30, "credits": 53000, "stars": 500},
}

REQUIRED_CHANNEL_ID = -1004472043948
REQUIRED_GROUP_ID = -1004420445815
REQUIRED_CHANNEL_ID_3 = -1004314230958
CHANNEL_LINK = "https://t.me/SPYGENxFEEDBACK"
GROUP_LINK = "https://t.me/SPYGENxLOGS"
CHANNEL_LINK_3 = "https://t.me/SpygenCVV1"

JOIN_TEXT = (
    "<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>𝗔𝗰𝗰𝗲𝘀𝘀 𝗥𝗲𝘀𝘁𝗿𝗶𝗰𝘁𝗲𝗱!</b>\n\n"
    "𝗧𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁 𝘆𝗼𝘂 𝗺𝘂𝘀𝘁 𝗷𝗼𝗶𝗻 𝗼𝘂𝗿 𝗰𝗵𝗮𝗻𝗻𝗲𝗹𝘀 𝗮𝗻𝗱 𝗴𝗿𝗼𝘂𝗽𝘀 𝗳𝗶𝗿𝘀𝘁.\n\n"
    "𝗝𝗼𝗶𝗻 𝗮𝗹𝗹 𝗰𝗵𝗮𝗻𝗻𝗲𝗹𝘀 𝗮𝗻𝗱 𝗴𝗿𝗼𝘂𝗽𝘀, 𝘁𝗵𝗲𝗻 𝗰𝗹𝗶𝗰𝗸 𝗩𝗲𝗿𝗶𝗳𝘆."
)

PRICING_TEXT = (
    f'━━━━━━━━━━━━━━━━\n'
    f'<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji> <b>𝗖𝗢𝗥𝗘 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>\n'
    f'<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗦𝗽𝗮𝗻 ➛</b> [𝟳 𝗗𝗔𝗬𝗦]\n'
    f'<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟭𝟯,𝟬𝟬𝟬\n'
    f'<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 150⭐ (≈ $3)\n'
    f'━━━━━━━━━━━━━━━━\n'
    f'<tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji> <b>𝗘𝗟𝗜𝗧𝗘 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji>\n'
    f'<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗦𝗽𝗮𝗻 ➛</b> [𝟏𝟓 𝗗𝗔𝗬𝗦]\n'
    f'<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟮𝟯,𝟬𝟬𝟬\n'
    f'<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 300⭐ (≈ $6)\n'
    f'━━━━━━━━━━━━━━━━\n'
    f'<tg-emoji emoji-id=\"5854931759010946555\">👑</tg-emoji> <b>𝗥𝗢𝗢𝗧 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"5854931759010946555\">👑</tg-emoji>\n'
    f'<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗦𝗽𝗮𝗻 ➛</b> [𝟯𝟬 𝗗𝗔𝗬𝗦]\n'
    f'<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟱𝟯,𝟬𝟬𝟬\n'
    f'<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 500⭐ (≈ $10)\n'
    f'━━━━━━━━━━━━━━━━\n'
    f'<tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji> <b>𝗔𝗹𝗹 𝗽𝗹𝗮𝗻𝘀 𝗶𝗻𝗰𝗹𝘂𝗱𝗲 𝘂𝗻𝗹𝗶𝗺𝗶𝘁𝗲𝗱 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗼 𝗮𝗹𝗹 𝗴𝗮𝘁𝗲𝘀.</b> <tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji>\n\n'
    f'<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻 𝗳𝗼𝗿 𝗱𝗼𝗹𝗹𝗮𝗿 𝗽𝗮𝘆𝗺𝗲𝗻𝘁 ➛</b> <a href="https://t.me/orvexq">@orvexq</a>'
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
log_bot = Bot(token=LOG_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(msh_router)
dp.include_router(mst_router)
dp.include_router(mrz_router)
dp.include_router(sitechk_router)
dp.include_router(cmds_router)
dp.include_router(fb_router)
dp.include_router(ban_router)
dp.include_router(maintenance_router)
dp.include_router(broad_router)
dp.include_router(status_router)
dp.include_router(faker_router)

router = Router()
dp.include_router(router)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEMBERSHIP CACHE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_MEMBERSHIP_CACHE: Dict[int, tuple] = {}
_MEMBERSHIP_CACHE_TTL = 60
_MEMBERSHIP_LOCK: Dict[int, asyncio.Lock] = {}
_MEMBERSHIP_LOCK_MAP_LOCK = asyncio.Lock()
_VALID_STATUSES = {"member", "administrator", "creator"}

async def _get_user_lock(user_id: int) -> asyncio.Lock:
    async with _MEMBERSHIP_LOCK_MAP_LOCK:
        if user_id not in _MEMBERSHIP_LOCK:
            _MEMBERSHIP_LOCK[user_id] = asyncio.Lock()
        return _MEMBERSHIP_LOCK[user_id]

async def check_membership(user_id: int, bot_instance: Bot) -> bool:
    cached = _MEMBERSHIP_CACHE.get(user_id)
    if cached and (time.time() - cached[0]) < _MEMBERSHIP_CACHE_TTL:
        return cached[1]

    lock = await _get_user_lock(user_id)
    async with lock:
        cached = _MEMBERSHIP_CACHE.get(user_id)
        if cached and (time.time() - cached[0]) < _MEMBERSHIP_CACHE_TTL:
            return cached[1]

        try:
            ch_member = await bot_instance.get_chat_member(REQUIRED_CHANNEL_ID, user_id)
            gp_member = await bot_instance.get_chat_member(REQUIRED_GROUP_ID, user_id)
            ch3_member = await bot_instance.get_chat_member(REQUIRED_CHANNEL_ID_3, user_id)
            joined = (ch_member.status in _VALID_STATUSES and gp_member.status in _VALID_STATUSES
                      and ch3_member.status in _VALID_STATUSES)
        except Exception as e:
            logging.error(f"check_membership error for user {user_id}: {e}")
            joined = False

        _MEMBERSHIP_CACHE[user_id] = (time.time(), joined)
        return joined

_JOIN_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 Channel", url=CHANNEL_LINK, style="primary"),
     InlineKeyboardButton(text="🔥 Logs", url=CHANNEL_LINK_3, style="primary")],
    [InlineKeyboardButton(text="💬 Group", url=GROUP_LINK, style="primary")],
    [InlineKeyboardButton(text="𝗩𝗲𝗿𝗶𝗳𝘆", callback_data="verify_membership", style="primary")]
])


RZ_SITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rz_sites.txt")

@router.message(Command("addrzapi"))
async def addrzapi_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>Not authorized.</b>", parse_mode="HTML")
        return
    args = message.text.split(None, 1)
    if len(args) < 2:
        if RZ_API_ENDPOINTS:
            api_list = "\n".join(f"{i+1}. <code>{a}</code>" for i, a in enumerate(RZ_API_ENDPOINTS))
        else:
            api_list = "None"
        await message.reply(
            f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Usage:</b> <code>/addrzapi &lt;url&gt;</code>\n\n"
            f"<b>Current APIs:</b>\n{api_list}",
            parse_mode="HTML"
        )
        return
    api_url = args[1].strip()
    if add_rz_api_endpoint(api_url):
        await message.reply(
            f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>RZ API Added!</b>\n\n<b>New Endpoint:</b> <code>{api_url}</code>\n<b>Total APIs:</b> <code>{len(RZ_API_ENDPOINTS)}</code>",
            parse_mode="HTML"
        )
    else:
        await message.reply(f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>API already exists!</b>", parse_mode="HTML")

@router.message(Command("removeapirz"))
async def removeapirz_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>Not authorized.</b>", parse_mode="HTML")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Usage:</b> /removeapirz <code>index_number</code>", parse_mode="HTML")
        return
    try:
        index = int(parts[1].strip()) - 1
        removed = remove_rz_api_endpoint(index)
        if removed:
            await message.reply(
                f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>RZ API Removed!</b>\n\n<b>Removed:</b> <code>{removed}</code>\n<b>Remaining APIs:</b> <code>{len(RZ_API_ENDPOINTS)}</code>",
                parse_mode="HTML"
            )
        else:
            await message.reply(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid index!</b> Please enter a number between 1 and {len(RZ_API_ENDPOINTS)}", parse_mode="HTML")
    except ValueError:
        await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Please provide a valid number!</b>", parse_mode="HTML")

@router.message(Command("addrzsite"))
async def addrzsite_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>Not authorized.</b>", parse_mode="HTML")
        return

    doc = message.document
    if not doc and message.reply_to_message:
        doc = message.reply_to_message.document

    if doc:
        try:
            bot = message.bot
            file_info = await bot.get_file(doc.file_id)
            import io
            destination = io.BytesIO()
            await bot.download_file(file_info.file_path, destination)
            destination.seek(0)
            text = destination.read().decode('utf-8', errors='ignore')
            import re as _re
            urls = _re.findall(r'https?://\S+', text)
            urls = [u.rstrip('.,;:!?)\'"') for u in urls]
            urls = list(set(urls))
            if not urls:
                await message.reply("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> No valid URLs found in file.", parse_mode="HTML")
                return
            existing = []
            if os.path.exists(RZ_SITES_FILE):
                with open(RZ_SITES_FILE, "r", encoding="utf-8") as f:
                    existing = [l.strip() for l in f if l.strip()]
            new_urls = [u for u in urls if u not in existing]
            with open(RZ_SITES_FILE, "a", encoding="utf-8") as f:
                for u in new_urls:
                    f.write(u + "\n")
            await message.reply(
                f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Added <b>{len(new_urls)}</b> new site(s).\n"
                f"Total sites: <b>{len(existing) + len(new_urls)}</b>",
                parse_mode="HTML"
            )
            return
        except Exception as e:
            await message.reply(f"❌ Error: {e}", parse_mode="HTML")
            return

    args = message.text.split(None, 1)
    if len(args) < 2:
        await message.reply(
            "<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Usage:</b> <code>/addrzsite &lt;url&gt;</code>\n"
            "Or reply to a .txt file with URLs using <code>/addrzsite</code>\n"
            "Or upload a .txt file with caption <code>/addrzsite</code>",
            parse_mode="HTML"
        )
        return

    site_url = args[1].strip()
    existing = []
    if os.path.exists(RZ_SITES_FILE):
        with open(RZ_SITES_FILE, "r", encoding="utf-8") as f:
            existing = [l.strip() for l in f if l.strip()]
    if site_url in existing:
        await message.reply(f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> Site already exists.\nTotal: <b>{len(existing)}</b>", parse_mode="HTML")
        return
    with open(RZ_SITES_FILE, "a", encoding="utf-8") as f:
        f.write(site_url + "\n")
    await message.reply(
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> Added: <code>{site_url}</code>\n"
        f"Total sites: <b>{len(existing) + 1}</b>",
        parse_mode="HTML"
    )

@router.message(Command("siteallrz"))
async def siteallrz_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>Not authorized.</b>", parse_mode="HTML")
        return
    if not os.path.exists(RZ_SITES_FILE):
        await message.reply("📭 <b>rz_sites.txt is empty.</b>", parse_mode="HTML")
        return
    with open(RZ_SITES_FILE, "r", encoding="utf-8") as f:
        sites = list(set([l.strip() for l in f if l.strip()]))
    if not sites:
        await message.reply("📭 <b>rz_sites.txt is empty.</b>", parse_mode="HTML")
        return
    filename = f"full_rz_sites_list_{int(time.time())}.txt"
    try:
        def _write_file():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"Total Razorpay Sites: {len(sites)} (Deduplicated)\n\n")
                f.write("\n".join(sites))
        await asyncio.to_thread(_write_file)
        await message.answer_document(
            document=FSInputFile(filename),
            caption=f"📜 <b>Total RZ Sites:</b> <code>{len(sites)}</code> ✨ (No Duplicates)",
            parse_mode="HTML"
        )
        os.remove(filename)
    except Exception as e:
        await message.reply(f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error:</b> {e}", parse_mode="HTML")

@router.message(Command("removerzsites"))
async def removerzsites_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> <b>Not authorized.</b>", parse_mode="HTML")
        return
    with open(RZ_SITES_FILE, "w", encoding="utf-8") as f:
        f.write("")
    await message.reply("<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> All Razorpay sites cleared.", parse_mode="HTML")

class MembershipMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: Dict[str, Any]):
        user = event.from_user
        if not user:
            return await handler(event, data)
        if user.id in ADMIN_IDS:
            return await handler(event, data)
        if not await check_membership(user.id, data["bot"]):
            await event.reply(text=JOIN_TEXT, parse_mode="HTML", reply_markup=_JOIN_KB, disable_web_page_preview=True)
            return
        return await handler(event, data)

dp.message.middleware(BanMiddleware())
dp.message.middleware(MaintenanceMiddleware())
dp.message.middleware(MembershipMiddleware())

@router.callback_query(F.data == "verify_membership")
async def verify_membership_callback(callback: types.CallbackQuery):
    invalidate_membership_cache(callback.from_user.id)
    joined = await check_membership(callback.from_user.id, callback.bot)
    if joined:
        await callback.answer("Verified! You now have full access.", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer(
            "You haven't joined yet!\n\nPlease join all channels and groups first, then click Verify.",
            show_alert=True
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DB HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _ensure_user_sync(user_id, username):
    """Ensure user exists in database with initial credits"""
    try:
        user = get_user(user_id)
        if not user:
            create_user(user_id, username or "unknown")
            logging.info(f"Created new user: {user_id}")
    except Exception as e:
        logging.error(f"ensure_user {user_id}: {e}")

async def ensure_user_and_credits(user_id, username="unknown"):
    """Async wrapper for user initialization"""
    await asyncio.to_thread(_ensure_user_sync, user_id, username)

def _status_sync(user_id):
    """Get user status including actual premium plan"""
    return get_user_status(user_id)

async def _get_caption(user) -> str:
    credits_str, access_str, joined_str = await asyncio.to_thread(_status_sync, user.id)
    ul = f'<a href="tg://user?id={user.id}">{html_escape(user.first_name or "")}</a>'
    dl = '<a href="tg://openmessage?user_id=6113616017">SpygenCVV</a>'
    return (
        f"𝗨𝘀𝗲𝗿 ➛ {ul}\n"
        f"𝗨𝘀𝗲𝗿 𝗜𝗗 ➛ <code>{user.id}</code>\n"
        f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{access_str}</b>\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ <b>{credits_str}</b>\n"
        f"𝗝𝗼𝗶𝗻𝗲𝗱 ➛ <b>{joined_str}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"𝗗𝗲𝘃 ➛ {dl}"
    )

def _loading_caption(user) -> str:
    ul = f'<a href="tg://user?id={user.id}">{html_escape(user.first_name or "")}</a>'
    dl = '<a href="tg://openmessage?user_id=6113616017">SpygenCVV</a>'
    return (
        f"𝗨𝘀𝗲𝗿 ➛ {ul}\n"
        f"𝗨𝘀𝗲𝗿 𝗜𝗗 ➛ <code>{user.id}</code>\n"
        f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>Loading…</b>\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ <b>Loading…</b>\n"
        f"𝗝𝗼𝗶𝗻𝗲𝗱 ➛ <b>Loading…</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"𝗗𝗲𝘃 ➛ {dl}"
    )

def mask_receipt_id(receipt_id):
    parts = receipt_id.split('-')
    if len(parts) == 3:
        m = parts[1]
        if len(m) >= 2:
            return f"{parts[0]}-{m[:2]}XX{m[4:]}-{parts[2]}"
    return receipt_id

def invalidate_membership_cache(user_id: int):
    _MEMBERSHIP_CACHE.pop(user_id, None)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRE-BUILT KEYBOARDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_MAIN_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗖𝗵𝗲𝗰𝗸𝗲𝗿", callback_data="menu_gates", style="primary", icon_custom_emoji_id="5258476306152038031"),
     InlineKeyboardButton(text="𝗕𝘂𝘆 𝗡𝗼𝘄", callback_data="menu_pricing", style="primary", icon_custom_emoji_id="5854966466641666181")],
    [InlineKeyboardButton(text="𝗨𝗽𝗱𝗮𝘁𝗲𝘀", url="https://t.me/SpygenCVV1", style="primary", icon_custom_emoji_id="5886367294665265093"),
     InlineKeyboardButton(text="𝗚𝗿𝗼𝘂𝗽", url="https://t.me/SPYGENxLOGS", style="primary", icon_custom_emoji_id="5258513401784573443")]
])

def _back(target):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data=target, style="primary")]])

_KB_BACK_MAIN   = _back("back_main")
_KB_BACK_GATES  = _back("menu_gates")
_KB_BACK_MASS   = _back("menu_mass_in_gates")
_KB_BACK_AUTH   = _back("menu_auth")
_KB_BACK_CHARGE = _back("menu_charge")

_KB_PRICING = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗖𝗼𝗿𝗲 - 150⭐", callback_data="buy_core", style="primary", icon_custom_emoji_id="6298678524379137990"),
     InlineKeyboardButton(text="𝗘𝗹𝗶𝘁𝗲 - 300⭐", callback_data="buy_elite", style="primary", icon_custom_emoji_id="5854795655792303583")],
    [InlineKeyboardButton(text="𝗥𝗼𝗼𝘁 - 500⭐", callback_data="buy_root", style="primary", icon_custom_emoji_id="5854931759010946555")],
    [InlineKeyboardButton(text="𝗖𝗼𝗺𝗽𝗮𝗿𝗲", callback_data="buy_compare", style="primary", icon_custom_emoji_id="4958506272551863292")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="back_main", style="primary")]
])
_KB_GATES = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗔𝘂𝘁𝗵", callback_data="menu_auth", style="primary", icon_custom_emoji_id="5454386656628991407"),
     InlineKeyboardButton(text="𝗖𝗵𝗮𝗿𝗴𝗲", callback_data="menu_charge", style="primary", icon_custom_emoji_id="5855210601172705878")],
    [InlineKeyboardButton(text="𝗠𝗮𝘀𝘀", callback_data="menu_mass_in_gates", style="primary", icon_custom_emoji_id="5258134813302332906")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="back_main", style="primary")]
])
_KB_MASS = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝟬-𝟮𝟬$", callback_data="info_msh_gate", style="primary", icon_custom_emoji_id="5854872574361608556"),
     InlineKeyboardButton(text="𝗦𝘁𝗿𝗶𝗽𝗲 𝟬.𝟱𝟬$", callback_data="info_mst_gate", style="primary", icon_custom_emoji_id="5855210601172705878")],
    [InlineKeyboardButton(text="𝗦𝘁𝗿𝗶𝗽𝗲 𝗛𝗶𝘁𝘁𝗲𝗿", callback_data="info_stco_gate", style="primary", icon_custom_emoji_id="5879783483462655267")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_gates", style="primary")]
])
_KB_AUTH = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗦𝘁𝗿𝗶𝗽𝗲", callback_data="info_auth_stripe", style="primary", icon_custom_emoji_id="5855210601172705878"),
     InlineKeyboardButton(text="𝗕𝗿𝗮𝗶𝗻𝘁𝗿𝗲𝗲", callback_data="info_auth_braintree", style="primary", icon_custom_emoji_id="5854957696318447867")],
    [InlineKeyboardButton(text="𝗕𝗿𝗮𝗶𝗻𝘁𝗿𝗲𝗲 𝗩𝗕𝗩", callback_data="info_auth_braintree_vbv", style="primary", icon_custom_emoji_id="5854957696318447867")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_gates", style="primary")]
])
_KB_CHARGE = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗦𝘁𝗿𝗶𝗽𝗲", callback_data="info_charge_stripe", style="primary", icon_custom_emoji_id="5855210601172705878"),
     InlineKeyboardButton(text="🅿️ 𝗣𝗮𝘆𝗽𝗮𝗹", callback_data="info_charge_paypal", style="primary")],
    [InlineKeyboardButton(text="𝗦𝗵𝗼𝗽𝗶𝗳𝘆", callback_data="info_charge_shopify", style="primary", icon_custom_emoji_id="5854872574361608556"),
     InlineKeyboardButton(text="𝗣𝗮𝘆𝗙𝗮𝘀𝘁", callback_data="info_charge_payfast", style="primary", icon_custom_emoji_id="5879783483462655267")],
    [InlineKeyboardButton(text="𝗙𝗮𝘁𝗭𝗲𝗯𝗿𝗮", callback_data="info_charge_fatzebra", style="primary", icon_custom_emoji_id="5854957696318447867"),
     InlineKeyboardButton(text="🏛 𝗡𝗠𝗜", callback_data="info_charge_nmi", style="primary")],
    [InlineKeyboardButton(text="𝗕𝗹𝘂𝗲𝗽𝗮𝘆", callback_data="info_charge_bluepay", style="primary", icon_custom_emoji_id="6256052494384760637"),
     InlineKeyboardButton(text="🏛 𝗔𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲.𝗻𝗲𝘁", callback_data="info_charge_authnet", style="primary")],
    [InlineKeyboardButton(text="𝗣𝗮𝘆𝗪𝗮𝘆", callback_data="info_charge_payway", style="primary", icon_custom_emoji_id="5855210601172705878"),
     InlineKeyboardButton(text="𝗥𝗮𝘇𝗼𝗿𝗽𝗮𝘆", callback_data="info_charge_razorpay", style="primary", icon_custom_emoji_id="4958926882994127612")],
    [InlineKeyboardButton(text="𝗣𝗮𝘆𝗨", callback_data="info_charge_payu", style="primary", icon_custom_emoji_id="5855210601172705878")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_gates", style="primary")]
])

_SEP = "━━━━━━━━━━━━━━━━"

_PAYMENT_SELECT_TEXT = "<tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji> <b>𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝘃𝗶𝗮 𝗧𝗲𝗹𝗲𝗴𝗿𝗮𝗺 𝗦𝘁𝗮𝗿𝘀</b>\n\n𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗽𝗹𝗮𝗻 𝘁𝗼 𝗽𝘂𝗿𝗰𝗵𝗮𝘀𝗲."

STATIC_MENU_MAP: dict = {
    "menu_pricing": (PRICING_TEXT, _KB_PRICING),
    "menu_gates": (
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"6129731845442510016\">🔐</tg-emoji> <b>𝗚𝗮𝘁𝗲𝘀 𝗦𝘁𝗮𝘁𝘂𝘀</b> 🔐\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5454386656628991407\">🔑</tg-emoji> 𝗔𝘂𝘁𝗵 𝗚𝗮𝘁𝗲𝘀 ➛ <b>3</b>\n"
        f"<tg-emoji emoji-id=\"5258134813302332906\">📦</tg-emoji> 𝗠𝗮𝘀𝘀 𝗚𝗮𝘁𝗲𝘀 ➛ <b>2</b>\n"
        f"<tg-emoji emoji-id=\"5855210601172705878\">💳</tg-emoji> 𝗖𝗵𝗮𝗿𝗴𝗲 𝗚𝗮𝘁𝗲𝘀 ➛ <b>11</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5879783483462655267\">⚡</tg-emoji> <b><i>Select a Gate Category</i></b> <tg-emoji emoji-id=\"5879783483462655267\">⚡</tg-emoji>",
        _KB_GATES
    ),
    "menu_mass_in_gates": ("<b><i>Select a Mass Gate</i></b>", _KB_MASS),
    "menu_auth":          ("<b><i>Select Auth Method</i></b>", _KB_AUTH),
    "menu_charge":        ("<b><i>Select Charge Method</i></b>", _KB_CHARGE),
    "menu_payment_methods": (
        _PAYMENT_SELECT_TEXT,
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="𝗖𝗼𝗿𝗲 - 150⭐", callback_data="pay_stars_core", style="primary", icon_custom_emoji_id="6298678524379137990"),
             InlineKeyboardButton(text="𝗘𝗹𝗶𝘁𝗲 - 300⭐", callback_data="pay_stars_elite", style="primary", icon_custom_emoji_id="5854795655792303583")],
            [InlineKeyboardButton(text="𝗥𝗼𝗼𝘁 - 500⭐", callback_data="pay_stars_root", style="primary", icon_custom_emoji_id="5854931759010946555")],
            [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_pricing", style="primary")]
        ])
    ),
    "info_msh_gate": (
        f"{_SEP}\n<b><i>Gate ➛ Shopify 0-20$</i></b>\n<b><i>Command ➛ /msh</i></b>\n"
        f"<b><i>Limit ➛ 5000</i></b>\n<b><i>Type ➛ Mass Checker</i></b>\n<b><i>Stop ➛ 🛑 Button</i></b>\n"
        f"{_SEP}\n<b><i>Gate ➛ Shopify Mass</i></b>\n<b><i>Command ➛ /sh</i></b>\n"
        f"<b><i>Limit ➛ 50 cards</i></b>\n{_SEP}", _KB_BACK_MASS),
    "info_mst_gate": (
        f"{_SEP}\n<b><i>Gate ➛ Stripe 1$</i></b>\n<b><i>Command ➛ /mst</i></b>\n"
        f"<b><i>Limit ➛ 2000</i></b>\n<b><i>Type ➛ Mass Checker</i></b>\n<b><i>Stop ➛ 🛑 Button</i></b>\n{_SEP}",
        _KB_BACK_MASS),
    "info_stco_gate": (
        f"{_SEP}\n<b><i>Gate ➛ Stripe Hitter</i></b>\n<b><i>Command ➛ /hit</i></b>\n"
        f"<b><i>Type ➛ Auto Hitter</i></b>\n<b><i>Stop ➛ 🛑 Button</i></b>\n{_SEP}",
        _KB_BACK_MASS),
    "info_auth_stripe": (
        f"{_SEP}\n<b><i>Gate ➛ Stripe 0$</i></b>\n<b><i>Command ➛ /chk</i></b>\n"
        f"<b><i>Sites Loaded ➛ 16</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_AUTH),
    "info_auth_braintree": (
        f"{_SEP}\n<b><i>Gate ➛ Braintree 0$</i></b>\n<b><i>Command ➛ /b3</i></b>\n"
        f"<b><i>Sites Loaded ➛ 2</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_AUTH),
    "info_auth_braintree_vbv": (
        f"{_SEP}\n<b><i>Gate ➛ Braintree VBV</i></b>\n<b><i>Command ➛ /vbv</i></b>\n"
        f"<b><i>Sites Loaded ➛ 1</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_AUTH),
    "info_charge_stripe": (
        f"{_SEP}\n<b><i>Gate ➛ Stripe 1$</i></b>\n<b><i>Command ➛ /st</i></b>\n"
        f"<b><i>Sites Loaded ➛ 4</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_paypal": (
        f"{_SEP}\n<b><i>Gate ➛ PayPal 0.10$</i></b>\n<b><i>Command ➛ /pp</i></b>\n"
        f"<b><i>Sites Loaded ➛ 7</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_shopify": (
        f"{_SEP}\n<b><i>Gate ➛ Shopify 5$</i></b>\n<b><i>Command ➛ /hc</i></b>\n"
        f"<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}\n<b><i>Gate ➛ Shopify 1$</i></b>\n"
        f"<b><i>Command ➛ /sp</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_payfast": (
        f"{_SEP}\n<b><i>Gate ➛ PayFast 0.30$</i></b>\n<b><i>Command ➛ /pf</i></b>\n"
        f"<b><i>Sites Loaded ➛ 1</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_fatzebra": (
        f"{_SEP}\n<b><i>Gate ➛ FatZebra 4$</i></b>\n<b><i>Command ➛ /ft</i></b>\n"
        f"<b><i>Sites Loaded ➛ 1</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_nmi": (
        f"{_SEP}\n<b><i>Gate ➛ NMI 1$</i></b>\n<b><i>Command ➛ /nmi</i></b>\n"
        f"<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}\n<b><i>Gate ➛ NMI2 1$</i></b>\n"
        f"<b><i>Command ➛ /nmi2</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_bluepay": (
        f"{_SEP}\n<b><i>Gate ➛ BluePay 20$</i></b>\n<b><i>Command ➛ /bl</i></b>\n"
        f"<b><i>Sites Loaded ➛ 1</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_authnet": (
        f"{_SEP}\n<b><i>Gate ➛ Authorize.net 1$</i></b>\n<b><i>Command ➛ /at</i></b>\n"
        f"<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_payway": (
        f"{_SEP}\n<b><i>Gate ➛ PayWay 1$</i></b>\n<b><i>Command ➛ /pw</i></b>\n"
        f"<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_razorpay": (
        f"{_SEP}\n<b><i>Gate ➛ Razorpay 100₹</i></b>\n<b><i>Command ➛ /rz</i></b>\n"
        f"<b><i>Sites Loaded ➛ 5</i></b>\n<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
    "info_charge_payu": (
        f"{_SEP}\n<b><i>Gate ➛ PayU 1$</i></b>\n<b><i>Command ➛ /pyu</i></b>\n"
        f"<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}", _KB_BACK_CHARGE),
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FAST INLINE EDIT HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _edit(msg: types.Message, text: str, kb: InlineKeyboardMarkup):
    try:
        if msg.caption is not None:
            await msg.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await msg.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    except TypeError:
        pass
    except Exception as e:
        if "Message is not modified" not in str(e):
            logging.warning(f"_edit: {e}")

async def _safe_answer(cb: types.CallbackQuery, text: str = "", **kw):
    try:
        await cb.answer(text, **kw)
    except Exception:
        pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /start
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.message(Command("start"))
async def start(message: types.Message):
    user = message.from_user
    asyncio.create_task(ensure_user_and_credits(user.id, user.username))

    if message.text and len(message.text.split()) > 1 and message.text.split()[1] == "buy":
        await buy_command(message)
        return

    quick = _loading_caption(user)
    caption_task = asyncio.create_task(_get_caption(user))

    sent = await message.reply_photo(photo=START_IMAGE_URL, caption=quick, reply_markup=_MAIN_KB, parse_mode="HTML")

    try:
        full = await caption_task
        await sent.edit_caption(caption=full, reply_markup=_MAIN_KB, parse_mode="HTML")
    except Exception:
        pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DOT COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOT_COMMAND_MAP = {
    "chk": chk_command, "st": st_command, "sh": sh_command,
    "sp": sp_command, "hc": hc_command, "pf": pf_command,
    "vbv": vbv_command, "ft": ft_command, "bl": bl_command,
    "pp": pp_command, "at": at_command, "pw": pw_command,
    "rz": rz_command, "pyu": pyu_command, "b3": b3_command,
    "jio": jio_command,
    "nmi": nmi_command, "nmi2": nmi2_command, "gen": gen_command, "hit": stco_command,
    "mst": mst_command, "mrz": mrz_command, "bin": binn_command, "binn": binn_command,
    "sub": sub_command, "rc": rc_command, "suball": suball_command,
    "g_code": g_code_command, "claim": claim_command, "info": info_command,
    "rsub": rsub_command, "buy": buy_command, "adcr": adcr_command,
    "genkey": genkey_command, "redeem": redeem_command,
    "on": on_command, "off": off_command, "stats": stats_command,
    "proxy": proxy_command, "checkproxy": checkproxy_command,
    "clearproxy": clearproxy_command, "sitechk": sitechk_command,
    "addsite": addsite_command, "siteall": siteall_command,
    "addrzsites": addrzsites_command,
    "removeall": removeall_command, "dedupe": dedupe_command,
    "proxyinfo": proxyinfo_command, "resetproxy": resetproxy_command,
    "cmds": cmds_command, "fb": feedback_cmd, "broad": broad_command,
    "ban": ban_command, "unban": unban_command, "vps": vps_command,
    "maintenance": maintenance_command,
}

@router.message(F.text.regexp(r'^\.\w+'))
async def dot_command_handler(message: types.Message):
    cmd = message.text.strip().split()[0][1:].lower()
    h = DOT_COMMAND_MAP.get(cmd)
    if h:
        await h(message)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALLBACK HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_MASS_PREFIXES = ("mshs_", "mshr_", "msts_", "mstr_", "stco_", "fb_", "cmds_")

@router.callback_query()
async def button_handler(callback: types.CallbackQuery):
    data = callback.data or ""

    if data.startswith(_MASS_PREFIXES):
        return

    msg = callback.message
    if not isinstance(msg, types.Message):
        await _safe_answer(callback, "❌ Message expired. Please use /start again.", show_alert=True)
        return

    user_id = callback.from_user.id

    # ── PLAN SELECTION BUTTONS ──────────────────────────
    if data == "buy_core":
        asyncio.create_task(_safe_answer(callback))
        text = (
            f"━━━━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji> <b>𝗖𝗢𝗥𝗘 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛</b> 𝟳 𝗗𝗮𝘆𝘀\n"
            f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟭𝟯,𝟬𝟬𝟬\n"
            f"<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 150⭐ (≈ $3)\n\n"
            f"<tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji> <b>𝗙𝘂𝗹𝗹 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗼 𝗮𝗹𝗹 𝗴𝗮𝘁𝗲𝘀.</b> <tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="𝗣𝗮𝘆 150⭐", callback_data="pay_stars_core", style="primary", icon_custom_emoji_id="5854795655792303583")],
            [InlineKeyboardButton(text="💬 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻", url="https://t.me/orvexq", style="primary")],
            [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_pricing", style="primary")]
        ])
        asyncio.create_task(_edit(msg, text, kb))
        return

    if data == "buy_elite":
        asyncio.create_task(_safe_answer(callback))
        text = (
            f"━━━━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji> <b>𝗘𝗟𝗜𝗧𝗘 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛</b> 𝟭𝟱 𝗗𝗮𝘆𝘀\n"
            f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟮𝟯,𝟬𝟬𝟬\n"
            f"<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 300⭐ (≈ $6)\n\n"
            f"<tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji> <b>𝗙𝘂𝗹𝗹 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗼 𝗮𝗹𝗹 𝗴𝗮𝘁𝗲𝘀.</b> <tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="𝗣𝗮𝘆 300⭐", callback_data="pay_stars_elite", style="primary", icon_custom_emoji_id="5854795655792303583")],
            [InlineKeyboardButton(text="💬 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻", url="https://t.me/SpygenCVV", style="primary")],
            [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_pricing", style="primary")]
        ])
        asyncio.create_task(_edit(msg, text, kb))
        return

    if data == "buy_root":
        asyncio.create_task(_safe_answer(callback))
        text = (
            f"━━━━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id=\"5854931759010946555\">👑</tg-emoji> <b>𝗥𝗢𝗢𝗧 𝗣𝗟𝗔𝗡</b> <tg-emoji emoji-id=\"5854931759010946555\">👑</tg-emoji>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛</b> 𝟯𝟬 𝗗𝗮𝘆𝘀\n"
            f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟱𝟯,𝟬𝟬𝟬\n"
            f"<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗽𝗿𝗶𝗰𝗲 ➛</b> 500⭐ (≈ $10)\n\n"
            f"<tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji> <b>𝗙𝘂𝗹𝗹 𝗮𝗰𝗰𝗲𝘀𝘀 𝘁𝗼 𝗮𝗹𝗹 𝗴𝗮𝘁𝗲𝘀.</b> <tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="𝗣𝗮𝘆 500⭐", callback_data="pay_stars_root", style="primary", icon_custom_emoji_id="5854795655792303583")],
            [InlineKeyboardButton(text="💬 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻", url="https://t.me/SpygenCVV", style="primary")],
            [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_pricing", style="primary")]
        ])
        asyncio.create_task(_edit(msg, text, kb))
        return

    if data == "buy_compare":
        asyncio.create_task(_safe_answer(callback))
        text = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id=\"4958506272551863292\">📊</tg-emoji> <b>𝗣𝗟𝗔𝗡 𝗖𝗢𝗠𝗣𝗔𝗥𝗜𝗦𝗢𝗡</b> <tg-emoji emoji-id=\"4958506272551863292\">📊</tg-emoji>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji> <b>𝗖𝗢𝗥𝗘</b>\n"
            f"  ├ <tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> 𝟳 𝗗𝗮𝘆𝘀\n"
            f"  ├ <tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> 𝟭𝟯,𝟬𝟬𝟬 𝗖𝗿𝗲𝗱𝗶𝘁𝘀\n"
f"  └ <tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> 150⭐ (≈ $3)\n\n"
            f"<tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji> <b>𝗘𝗟𝗜𝗧𝗘</b>\n"
            f"  ├ <tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> 𝟏𝟓 𝗗𝗮𝘆𝘀\n"
            f"  ├ <tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> 𝟮𝟯,𝟬𝟬𝟬 𝗖𝗿𝗲𝗱𝗶𝘁𝘀\n"
            f"  └ <tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> 300⭐ (≈ $6)\n\n"
            f"<tg-emoji emoji-id=\"5854931759010946555\">👑</tg-emoji> <b>𝗥𝗢𝗢𝗧</b> (𝗕𝗲𝘀𝘁 𝗩𝗮𝗹𝘂𝗲) <tg-emoji emoji-id=\"5861556273618623389\">🔥</tg-emoji>\n"
            f"  ├ <tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> 𝟯𝟬 𝗗𝗮𝘆𝘀\n"
            f"  ├ <tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> 𝟱𝟯,𝟬𝟬𝟬 𝗖𝗿𝗲𝗱𝗶𝘁𝘀\n"
            f"  └ <tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> 500⭐ (≈ $10)\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{random_diamond()} <b>𝗔𝗹𝗹 𝗽𝗹𝗮𝗻𝘀 𝗶𝗻𝗰𝗹𝘂𝗱𝗲 𝘂𝗻𝗹𝗶𝗺𝗶𝘁𝗲𝗱 𝗮𝗰𝗰𝗲𝘀𝘀.</b> {random_diamond()}\n\n"
            f"<tg-emoji emoji-id=\"4958926882994127612\">💰</tg-emoji> <b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻 𝗳𝗼𝗿 𝗱𝗼𝗹𝗹𝗮𝗿 𝗽𝗮𝘆𝗺𝗲𝗻𝘁 ➛</b> <a href=\"https://t.me/SpygenCVV\">@SpygenCVV</a>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗖𝗼𝗿𝗲 - 150⭐", callback_data="buy_core", style="primary", icon_custom_emoji_id="6298678524379137990"),
             InlineKeyboardButton(text="𝗘𝗹𝗶𝘁𝗲 - 300⭐", callback_data="buy_elite", style="primary", icon_custom_emoji_id="5854795655792303583")],
            [InlineKeyboardButton(text="𝗥𝗼𝗼𝘁 - 500⭐", callback_data="buy_root", style="primary", icon_custom_emoji_id="5854931759010946555")],
            [InlineKeyboardButton(text="💬 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻", url="https://t.me/orvexq", style="primary")],
            [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_pricing", style="primary")]
        ])
        asyncio.create_task(_edit(msg, text, kb))
        return

    # ── TELEGRAM STARS PAYMENT ──────────────────────────
    if data.startswith("pay_stars_"):
        plan_key = data[len("pay_stars_"):]
        plan = STAR_PLANS.get(plan_key)
        if not plan:
            await _safe_answer(callback, "Invalid plan.", show_alert=True)
            return
        user_id = callback.from_user.id
        try:
            await bot.send_invoice(
                chat_id=user_id,
                title=f"{plan['name']} Plan",
                description=f"{plan['days']} days access\n{plan['credits']:,} credits\nFull access to all gates",
                payload=f"stars_{plan_key}_{user_id}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=f"{plan['name']} Plan", amount=plan['stars'])],
            )
            await _safe_answer(callback, "Invoice sent — check your chat ⭐")
        except Exception as e:
            logging.error(f"send_invoice error: {e}")
            await _safe_answer(callback, "Failed to send invoice. Please try again.", show_alert=True)
        return

    # ── STATIC MENU ─────────────────────────────────────
    static = STATIC_MENU_MAP.get(data)
    if static is not None:
        text, kb = static
        asyncio.create_task(_safe_answer(callback))
        asyncio.create_task(_edit(msg, text, kb))
        return

    # ── BACK TO MAIN ────────────────────────────────────
    if data == "back_main":
        user = callback.from_user
        quick = _loading_caption(user)
        caption_task = asyncio.create_task(_get_caption(user))
        asyncio.create_task(_safe_answer(callback))
        try:
            if msg.caption is not None:
                await msg.edit_caption(caption=quick, reply_markup=_MAIN_KB, parse_mode="HTML")
            else:
                await msg.answer_photo(photo=START_IMAGE_URL, caption=quick, reply_markup=_MAIN_KB, parse_mode="HTML")
        except TypeError:
            pass
        except Exception as e:
            if "Message is not modified" not in str(e):
                logging.warning(f"back_main load: {e}")
        try:
            full = await caption_task
            await msg.edit_caption(caption=full, reply_markup=_MAIN_KB, parse_mode="HTML")
        except TypeError:
            pass
        except Exception:
            pass
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXPLICIT CALLBACK REGISTRATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
dp.callback_query.register(msh_stop_handler, MshStopCallback.filter())
dp.callback_query.register(msh_result_handler, MshResultCallback.filter())
dp.callback_query.register(mst_stop_handler, MstStopCallback.filter())
dp.callback_query.register(mst_result_handler, MstResultCallback.filter())
dp.callback_query.register(mrz_stop_handler, MrzStopCallback.filter())
dp.callback_query.register(mrz_result_handler, MrzResultCallback.filter())
dp.callback_query.register(sh_callback_handler, F.data.startswith("sh_"))
dp.callback_query.register(stco_callback_handler, F.data.startswith("stco_"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TELEGRAM STARS PAYMENT HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _pre_checkout_handler(query: types.PreCheckoutQuery):
    payload = query.invoice_payload or ""
    parts = payload.split("_")
    if len(parts) == 3 and parts[0] == "stars" and parts[1] in STAR_PLANS:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Invalid payment. Please try again.")

dp.pre_checkout_query.register(_pre_checkout_handler)

@router.message(F.successful_payment)
async def _successful_payment_handler(message: types.Message):
    payment = message.successful_payment
    payload = payment.invoice_payload or ""
    parts = payload.split("_")
    if len(parts) != 3 or parts[0] != "stars":
        return
    plan_key = parts[1]
    payer_id = int(parts[2])
    plan = STAR_PLANS.get(plan_key)
    if not plan or payer_id != message.from_user.id:
        return

    display_name = message.from_user.first_name or "User"

    try:
        receipt_id = await asyncio.to_thread(
            database.sub_db_sync,
            payer_id,
            display_name,
            plan["name"],
            plan["days"],
            plan["credits"],
            plan["stars"],
        )
    except Exception as e:
        logging.error(f"Stars payment activation error for user {payer_id}: {e}")
        await message.reply(
            "<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Payment received but activation failed.</b>\n"
            "Please contact support with your payment receipt.",
            parse_mode="HTML"
        )
        return

    user_link = f'<a href="tg://user?id={payer_id}">{html_escape(str(display_name))}</a>'

    confirmation = (
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹!</b>\n"
        f"<tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji> 𝗣𝗮𝗶𝗱 ➛ <b>{plan['stars']} Stars</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{random_diamond()} 𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{plan['name']}</b>\n"
        f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛ {plan['days']} Days\n"
        f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> 𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ +{plan['credits']:,}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🆔 𝗥𝗲𝗰𝗲𝗶𝗽𝘁 ➛ <code>{receipt_id}</code>"
    )
    await message.reply(confirmation, parse_mode="HTML")

    log_text = (
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5854872574361608556\">🛒</tg-emoji> <b>𝗡𝗘𝗪 𝗦𝗧𝗔𝗥𝗦 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘</b> <tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5343993902493895946\">👽</tg-emoji> <b>𝗨𝘀𝗲𝗿 ➛</b> {user_link}\n"
        f"🆔 <b>𝗨𝘀𝗲𝗿 𝗜𝗗 ➛</b> <code>{payer_id}</code>\n"
        f"{random_diamond()} <b>𝗔𝗰𝗰𝗲𝘀𝘀 ➛</b> <b>{plan['name']}</b>\n"
        f"<tg-emoji emoji-id=\"5854795655792303583\">⭐</tg-emoji> <b>𝗔𝗺𝗼𝘂𝗻𝘁 ➛</b> <b>{plan['stars']} Stars</b>\n"
        f"<tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji> <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> <b>{plan['credits']:,}</b>\n"
        f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗗𝗮𝘆𝘀 ➛</b> <b>{plan['days']}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>𝗥𝗲𝗰𝗲𝗶𝗽𝘁 ➛</b> <code>{receipt_id}</code>"
    )
    try:
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Stars log to channel failed: {e}")

    logging.info(f"[STARS] Plan {plan['name']} activated for user {payer_id}, receipt: {receipt_id}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND REGISTRATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
for _cmd, _fn in [
    ("pp", pp_command), ("pw", pw_command), ("at", at_command), ("pf", pf_command),
    ("b3", b3_command), ("chk", chk_command), ("sh", sh_command), ("st", st_command),
    ("hc", hc_command), ("sp", sp_command), ("gen", gen_command), ("hit", stco_command), ("vbv", vbv_command),
    ("ft", ft_command), ("nmi", nmi_command), ("nmi2", nmi2_command), ("bl", bl_command),
    ("rz", rz_command), ("pyu", pyu_command), ("sub", sub_command), ("rc", rc_command),
    ("jio", jio_command),
    ("suball", suball_command), ("g_code", g_code_command), ("claim", claim_command),
    ("info", info_command), ("rsub", rsub_command), ("buy", buy_command),
    ("adcr", adcr_command), ("on", on_command), ("off", off_command),
    ("mst", mst_command), ("mrz", mrz_command), ("sitechk", sitechk_command), ("addsite", addsite_command),
    ("siteall", siteall_command), ("addrzsites", addrzsites_command),
    ("removeall", removeall_command), ("dedupe", dedupe_command),
    ("proxyinfo", proxyinfo_command), ("resetproxy", resetproxy_command),
    ("stats", stats_command), ("proxy", proxy_command), ("checkproxy", checkproxy_command),
    ("clearproxy", clearproxy_command), ("bin", binn_command), ("binn", binn_command),
    ("genkey", genkey_command), ("redeem", redeem_command),
]:
    dp.message.register(_fn, Command(_cmd))

# Proxy document handlers — support .txt file with /proxy or .proxy in caption
dp.message.register(proxy_command, F.document, F.caption.startswith("/proxy"))
dp.message.register(proxy_command, F.document, F.caption.startswith(".proxy"))

# Razorpay site document handler — support .txt file with /addrzsite in caption
dp.message.register(addrzsite_command, F.document, F.caption.startswith("/addrzsite"))

setup_feedback_handler(dp)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def main():
    logging.info("Bot starting via Polling…")
    await bot.delete_webhook()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped.")
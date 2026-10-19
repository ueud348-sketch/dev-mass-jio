import asyncio
import logging
import aiohttp
import time

from html import escape as html_escape
from aiogram import types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import is_gate_enabled, get_user_credits, update_credits, ADMIN_IDS
import database
from sub import get_premium_status

logger = logging.getLogger(__name__)
router = Router()

user_last_command_time = {}

COUNTRY_NAMES = {
    'AU': 'Australia', 'BR': 'Brazil', 'CA': 'Canada', 'CH': 'Switzerland',
    'DE': 'Germany', 'DK': 'Denmark', 'ES': 'Spain', 'FI': 'Finland',
    'FR': 'France', 'GB': 'United Kingdom', 'IE': 'Ireland', 'IN': 'India',
    'IR': 'Iran', 'MX': 'Mexico', 'NL': 'Netherlands', 'NO': 'Norway',
    'NZ': 'New Zealand', 'RS': 'Serbia', 'TR': 'Turkey', 'UA': 'Ukraine',
    'US': 'United States'
}

VALID_NATS = list(COUNTRY_NAMES.keys())


async def get_user_plan_name(user_id):
    is_premium, _ = await asyncio.to_thread(database.get_premium_status, user_id)
    if is_premium:
        plan = await asyncio.to_thread(database.get_user_plan, user_id)
        return plan or "PREMIUM"
    return "TRIAL"


@router.message(F.text.startswith("/fake"))
async def faker_command(message: types.Message):
    user = message.from_user
    user_id = user.id
    current_time = time.time()

    if not await asyncio.to_thread(is_gate_enabled, "fk"):
        await message.reply(
            "🚧 <b>𝗙𝗮𝗸𝗲𝗿 𝗧𝗼𝗼𝗹 𝗶𝘀 𝘂𝗻𝗱𝗲𝗿 𝗺𝗮𝗶𝗻𝘁𝗲𝗻𝗮𝗻𝗰𝗲.</b>\n"
            "𝗜𝘁 𝘄𝗶𝗹𝗹 𝗯𝗲 𝗯𝗮𝗰𝗸 𝘀𝗵𝗼𝗿𝘁𝗹𝘆.⚙️",
            parse_mode="HTML"
        )
        return

    is_premium, _ = await asyncio.to_thread(get_premium_status, user_id)

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

    args = message.text.split(maxsplit=1)
    nationality = "US"
    if len(args) > 1:
        nationality = args[1].strip().upper()
        if nationality not in VALID_NATS:
            await message.reply(
                f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Country Code!</b>\n\n"
                f"<b>Valid codes:</b> <code>{' | '.join(VALID_NATS)}</code>\n\n"
                f"<b>Usage:</b> <code>.fk US</code> or <code>.fk GB</code>",
                parse_mode="HTML"
            )
            return

    if not is_premium and user_id not in ADMIN_IDS:
        current_credits = await asyncio.to_thread(get_user_credits, user_id)
        if current_credits is None or current_credits <= 0:
            await message.reply(
                f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Insufficient Credits!</b>\n\n"
                f"𝗬𝗼𝘂𝗿 𝗰𝗿𝗲𝗱𝗶𝘁𝘀: <code>{current_credits if current_credits is not None else 0}</code>\n"
                f"𝗨𝘀𝗲 <code>/buy</code> 𝘁𝗼 𝗽𝘂𝗿𝗰𝗵𝗮𝘀𝗲 𝗺𝗼𝗿𝗲.",
                parse_mode="HTML"
            )
            return

        new_balance = current_credits - 1
        if new_balance < 0:
            new_balance = 0
        await asyncio.to_thread(update_credits, user_id, new_balance)

    proc_msg = await message.reply(
        f"<tg-emoji emoji-id=\"5879783483462655267\">⚡</tg-emoji> <b>𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗶𝗻𝗴 𝗙𝗮𝗸𝗲 𝗜𝗱𝗲𝗻𝘁𝗶𝘁𝘆</b> <tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji>\n"
        f"<tg-emoji emoji-id=\"5852982548233199026\">🌍</tg-emoji> <b>𝗖𝗼𝘂𝗻𝘁𝗿𝘆</b> ➛ <code>{nationality}</code>\n\n"
        f"<i>Please wait...</i>",
        parse_mode="HTML"
    )

    result = await generate_fake_identity(nationality)

    if not result.get('success'):
        await proc_msg.edit_text(
            f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error</b> → <i>{result.get('error', 'Unknown error')}</i>",
            parse_mode="HTML"
        )
        return

    plan_name = await get_user_plan_name(user_id)
    user_link = f'<a href="tg://user?id={user.id}">{html_escape(user.first_name or "")}</a>'
    user_display = f"{user_link} <b>({plan_name})</b>"
    dev_link = '<a href="tg://openmessage?user_id=8937448847">воин</a>'

    data = result['data']
    country_name = COUNTRY_NAMES.get(data['country_code'], data['country_code'])

    text = (
        f"<tg-emoji emoji-id=\"5879783483462655267\">⚡</tg-emoji> <b>𝗙𝗮𝗸𝗲 𝗜𝗱𝗲𝗻𝘁𝗶𝘁𝘆</b> <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5343993902493895946\">👽</tg-emoji> <b>𝗡𝗮𝗺𝗲</b> ➛ <code>{data['title']}</code>. <code>{data['first_name']}</code> <code>{data['last_name']}</code>\n\n"
        f"<tg-emoji emoji-id=\"4956560549287560231\">🌐</tg-emoji> <b>𝗘𝗺𝗮𝗶𝗹</b> ➛ <code>{data['email']}</code>\n"
        f"<tg-emoji emoji-id=\"5855024182412188879\">💬</tg-emoji> <b>𝗣𝗵𝗼𝗻𝗲</b> ➛ <code>{data['phone']}</code>\n"
        f"<tg-emoji emoji-id=\"5855024182412188879\">💬</tg-emoji> <b>𝗖𝗲𝗹𝗹</b> ➛ <code>{data['cell']}</code>\n\n"
        f"<tg-emoji emoji-id=\"5854957696318447867\">🏦</tg-emoji> <b>𝗦𝘁𝗿𝗲𝗲𝘁</b> ➛ <code>{data['street']}</code>\n"
        f"<tg-emoji emoji-id=\"5854957696318447867\">🏦</tg-emoji> <b>𝗖𝗶𝘁𝘆</b> ➛ <code>{data['city']}</code>\n"
        f"<tg-emoji emoji-id=\"5854957696318447867\">🏦</tg-emoji> <b>𝗦𝘁𝗮𝘁𝗲</b> ➛ <code>{data['state']}</code>\n"
        f"<tg-emoji emoji-id=\"5258134813302332906\">📦</tg-emoji> <b>𝗣𝗼𝘀𝘁𝗮𝗹</b> ➛ <code>{data['postcode']}</code>\n"
        f"<tg-emoji emoji-id=\"5852982548233199026\">🌍</tg-emoji> <b>𝗖𝗼𝘂𝗻𝘁𝗿𝘆</b> ➛ <code>{country_name}</code> [<code>{data['country_code']}</code>]\n\n"
        f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> <b>𝗔𝗴𝗲</b> ➛ <code>{data['age']}</code>\n"
        f"<tg-emoji emoji-id=\"5343993902493895946\">👽</tg-emoji> <b>𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲</b> ➛ <code>{data['username']}</code>\n"
        f"<tg-emoji emoji-id=\"5454386656628991407\">🔑</tg-emoji> <b>𝗣𝗮𝘀𝘀𝘄𝗼𝗿𝗱</b> ➛ <code>{data['password']}</code>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5343993902493895946\">👽</tg-emoji>𝗨𝘀𝗲𝗿 ➛ {user_display}\n"
        f"<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>𝗗𝗲𝘃 ➛ {dev_link}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]
    ])

    try:
        await proc_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await message.reply(text, parse_mode="HTML", reply_markup=kb)


async def generate_fake_identity(nationality: str = 'US'):
    try:
        url = f"https://randomuser.me/api/1.4/?nat={nationality.upper()}"
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {'success': False, 'error': 'Failed to fetch data from API'}

                data = await response.json()

                if not data.get('results') or len(data['results']) == 0:
                    return {'success': False, 'error': 'Country code not found or invalid'}

                user = data['results'][0]

                name = user.get('name', {}) if isinstance(user.get('name'), dict) else {}
                location = user.get('location', {}) if isinstance(user.get('location'), dict) else {}
                street_raw = location.get('street', '')

                if isinstance(street_raw, dict):
                    street_number = street_raw.get('number', '')
                    street_name = street_raw.get('name', '')
                    street_address = f"{street_number} {street_name}".strip()
                else:
                    street_address = str(street_raw) if street_raw else ''

                dob = user.get('dob', {}) if isinstance(user.get('dob'), dict) else {}
                login = user.get('login', {}) if isinstance(user.get('login'), dict) else {}
                picture = user.get('picture', {}) if isinstance(user.get('picture'), dict) else {}

                return {
                    'success': True,
                    'data': {
                        'title': str(name.get('title', '')).capitalize() if name else '',
                        'first_name': str(name.get('first', '')).capitalize() if name else '',
                        'last_name': str(name.get('last', '')).capitalize() if name else '',
                        'email': str(user.get('email', '')),
                        'phone': str(user.get('phone', '')),
                        'cell': str(user.get('cell', '')),
                        'street': street_address,
                        'city': str(location.get('city', '')).capitalize() if location else '',
                        'state': str(location.get('state', '')).capitalize() if location else '',
                        'postcode': str(location.get('postcode', '')) if location else '',
                        'country_code': str(user.get('nat', nationality.upper())),
                        'dob': str(dob.get('date', '')).split('T')[0] if dob else '',
                        'age': str(dob.get('age', '')) if dob else '',
                        'username': str(login.get('username', '')) if login else '',
                        'password': str(login.get('password', '')) if login else '',
                        'picture': str(picture.get('large', '')) if picture else ''
                    }
                }

    except asyncio.TimeoutError:
        return {'success': False, 'error': 'Request timed out'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}

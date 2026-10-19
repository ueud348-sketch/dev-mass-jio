import re
import random
import time
import io
import asyncio
import logging
from datetime import datetime
from typing import List, Tuple

from aiogram import Router, F, types
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from gates.bin import get_bin_info
from database import get_user_credits, update_credits, ADMIN_IDS
from sub import get_premium_status

logger = logging.getLogger(__name__)
router = Router()


def luhn_check(card_number: str) -> bool:
    digits = [int(d) for d in card_number]
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] = (digits[i] // 10) + (digits[i] % 10)
    return sum(digits) % 10 == 0


def generate_luhn_card(prefix: str, length: int = 16) -> str:
    card = prefix
    while len(card) < length - 1:
        card += str(random.randint(0, 9))
    for i in range(10):
        test_card = card + str(i)
        if luhn_check(test_card):
            return test_card
    return card + "0"


async def gen_command(message: types.Message):
    user_id = message.from_user.id
    user = message.from_user

    # GET PREMIUM STATUS
    is_premium, _ = await asyncio.to_thread(get_premium_status, user_id)

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply(
            f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Invalid Format!</b>\n\n"
            f"<b>Examples:</b>\n"
            f"<code>/gen 486732</code> — 10 cards with random dates\n"
            f"<code>/gen 486732|01|29|123</code> — specified details\n"
            f"<code>/gen 486732 01 29 123 50</code> — 50 cards\n"
            f"<code>/gen 486732|rnd|rnd|rnd|10000</code> — up to 10000 random cards",
            parse_mode="HTML"
        )
        return

    input_text = args[1].strip()

    try:
        bin_pattern, month, year, amount, cvv = parse_gen_input(input_text)
    except ValueError as e:
        await message.reply(
            f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error: {e}</b>",
            parse_mode="HTML"
        )
        return

    # Cap max generation
    if amount > 10000:
        amount = 10000

    # Deduct credit (Only if NOT Premium)
    if not is_premium and user_id not in ADMIN_IDS:
        credits_deducted = await deduct_gen_credit(user_id)
        if not credits_deducted:
            await message.reply(
                f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Insufficient credits.</b>\n\n"
                f"Use <code>/buy</code> to purchase more.",
                parse_mode="HTML"
            )
            return

    # Start generation in background
    asyncio.create_task(process_generation(message, user, user_id, bin_pattern, month, year, amount, cvv))


def parse_gen_input(input_text: str) -> Tuple[str, str, str, int, str]:
    bin_pattern = ""
    month = "rnd"
    year = "rnd"
    amount = 10
    cvv = "rnd"

    if "|" in input_text:
        parts = input_text.split("|")
        if len(parts) > 0:
            bin_pattern = parts[0].strip()
        if len(parts) > 1:
            month = parts[1].strip()
        if len(parts) > 2:
            year = parts[2].strip()
            if len(year) == 4:
                year = year[2:]
        if len(parts) > 3:
            part4 = parts[3].strip()
            if part4.lower() == "rnd":
                cvv = "rnd"
            else:
                try:
                    test_amount = int(part4)
                    if test_amount > 0:
                        amount = test_amount
                    else:
                        cvv = part4
                except ValueError:
                    cvv = part4
        if len(parts) > 4:
            try:
                test_amount = int(parts[4].strip())
                if test_amount > 0:
                    amount = test_amount
            except ValueError:
                pass
    else:
        parts = input_text.split()
        if len(parts) > 0:
            bin_pattern = parts[0].strip()
        if len(parts) > 1:
            try:
                test_amount = int(parts[1].strip())
                if test_amount > 0:
                    amount = test_amount
                else:
                    month = parts[1].strip()
            except ValueError:
                month = parts[1].strip()
        if len(parts) > 2 and month != "rnd":
            year = parts[2].strip()
            if len(year) == 4:
                year = year[2:]
        if len(parts) > 3 and month != "rnd" and year != "rnd":
            cvv = parts[3].strip()
        if len(parts) > 4:
            try:
                test_amount = int(parts[4].strip())
                if test_amount > 0:
                    amount = test_amount
            except ValueError:
                pass

    if not bin_pattern or len(bin_pattern) < 6:
        raise ValueError("BIN must be at least 6 digits long")

    return bin_pattern, month, year, amount, cvv


async def deduct_gen_credit(user_id: int) -> bool:
    try:
        current = await asyncio.to_thread(get_user_credits, user_id)
        if current is None or current == 0:
            return False
        if current == float('inf'):
            return True
        new_balance = current - 1
        if new_balance < 0:
            new_balance = 0
        await asyncio.to_thread(update_credits, user_id, new_balance)
        return True
    except Exception as e:
        logger.error(f"Credit deduct error for {user_id}: {e}")
        return False


async def process_generation(message: types.Message, user, user_id: int, bin_pattern: str, month: str, year: str, amount: int, cvv: str):
    try:
        status_msg = await message.reply(
            f"<tg-emoji emoji-id=\"5879783483462655267\">⚡</tg-emoji><b>𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗶𝗻𝗴</b> <tg-emoji emoji-id=\"6129639980387015660\">🚀</tg-emoji>\n\n"
            f"<tg-emoji emoji-id=\"5855210601172705878\">💳</tg-emoji><b>𝗕𝗜𝗡</b> ➛ <code>{bin_pattern[:6]}</code>\n"
            f"<tg-emoji emoji-id=\"4958689671950369798\">🔗</tg-emoji><b>𝗔𝗺𝗼𝘂𝗻𝘁</b> ➛ <code>{amount}</code> <b>cards</b>\n\n"
            f"<i>Generating...</i>",
            parse_mode="HTML"
        )

        cards, bin_info = await generate_cards_with_bin_info(bin_pattern, month, year, amount, cvv)

        if amount > 10:
            file_content = "\n".join(cards)
            file = BufferedInputFile(file=file_content.encode('utf-8'), filename=f"ChkX_{bin_pattern[:6]}.txt")

            caption = build_caption(bin_info, bin_pattern, amount)

            await message.reply_document(document=file, caption=caption, parse_mode="HTML",
                reply_markup=gen_keyboard())

            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass
        else:
            await status_msg.delete()

            result = format_cards_inline(cards, bin_info)
            await message.reply(result, parse_mode="HTML", reply_markup=gen_keyboard())

    except Exception as e:
        logger.error(f"Generation error for {user_id}: {e}")
        try:
            await message.reply(
                f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error generating cards.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass


async def generate_cards_with_bin_info(bin_pattern: str, month: str, year: str, amount: int, cvv: str) -> Tuple[List[str], dict]:
    bin_number = bin_pattern[:6]
    bin_info = await get_bin_info(bin_number)

    is_amex = bin_info.get("scheme", "").lower() == "american express" or bin_pattern.startswith(("34", "37"))

    cards = []
    for _ in range(amount):
        card_month = str(random.randint(1, 12)).zfill(2) if month.lower() == "rnd" else month

        if year.lower() == "rnd":
            current = int(time.strftime("%y"))
            card_year = str(random.randint(current, current + 7)).zfill(2)
        else:
            card_year = year

        card_length = 15 if is_amex else 16
        card_number = generate_luhn_card(bin_pattern, card_length)

        if cvv.lower() == "rnd":
            card_cvv = str(random.randint(1000, 9999)) if is_amex else str(random.randint(100, 999))
        else:
            card_cvv = cvv
            if is_amex and len(card_cvv) == 3:
                card_cvv += str(random.randint(0, 9))
            elif not is_amex and len(card_cvv) == 4:
                card_cvv = card_cvv[:3]

        card = f"{card_number}|{card_month}|{card_year}|{card_cvv}"
        cards.append(card)

    return cards, bin_info


def build_caption(bin_info: dict, bin_pattern: str, amount: int) -> str:
    brand = (bin_info.get("scheme") or "N/A").title()
    bank = bin_info.get("bank") or "N/A"
    country = bin_info.get("country") or "Unknown"
    card_type = bin_info.get("type", "N/A")
    country_flag = bin_info.get("country_emoji", "")
    country_display = f"{country_flag} {country}" if country_flag else country

    return (
        f"<tg-emoji emoji-id=\"5879783483462655267\">⚡</tg-emoji><b>𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱</b> <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n\n"
        f"<tg-emoji emoji-id=\"4958689671950369798\">🔗</tg-emoji><b>𝗔𝗺𝗼𝘂𝗻𝘁</b> ➛ <code>{amount}</code> <b>cards</b>\n"
        f"<tg-emoji emoji-id=\"5855210601172705878\">💳</tg-emoji><b>𝗕𝗜𝗡</b> ➛ <code>{bin_pattern[:6]}</code>\n\n"
        f"<tg-emoji emoji-id=\"5854776663446920778\">🏷</tg-emoji><b>𝗕𝗿𝗮𝗻𝗱</b> ➛ <b>{brand}</b>\n"
        f"<tg-emoji emoji-id=\"5854957696318447867\">🏦</tg-emoji><b>𝗕𝗮𝗻𝗸</b> ➛ <b>{bank}</b>\n"
        f"<tg-emoji emoji-id=\"5852982548233199026\">🌍</tg-emoji><b>𝗖𝗼𝘂𝗻𝘁𝗿𝘆</b> ➛ <b>{country_display}</b>\n"
        f"<tg-emoji emoji-id=\"5855024182412188879\">💬</tg-emoji><b>𝗧𝘆𝗽𝗲</b> ➛ <b>{card_type}</b>"
    )


def format_cards_inline(cards: List[str], bin_info: dict) -> str:
    brand = (bin_info.get("scheme") or "N/A").title()
    bank = bin_info.get("bank") or "N/A"
    country = bin_info.get("country") or "Unknown"
    card_type = bin_info.get("type", "N/A")
    country_flag = bin_info.get("country_emoji", "")
    country_display = f"{country_flag} {country}" if country_flag else country

    header = (
        f"<tg-emoji emoji-id=\"5879783483462655267\">⚡</tg-emoji><b>𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱</b> <tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>\n\n"
    )

    card_lines = "\n".join(f"<code>{c}</code>" for c in cards)

    footer = (
        f"\n\n"
        f"<tg-emoji emoji-id=\"5854776663446920778\">🏷</tg-emoji><b>𝗕𝗿𝗮𝗻𝗱</b> ➛ <b>{brand}</b>\n"
        f"<tg-emoji emoji-id=\"5854957696318447867\">🏦</tg-emoji><b>𝗕𝗮𝗻𝗸</b> ➛ <b>{bank}</b>\n"
        f"<tg-emoji emoji-id=\"5852982548233199026\">🌍</tg-emoji><b>𝗖𝗼𝘂𝗻𝘁𝗿𝘆</b> ➛ <b>{country_display}</b>\n"
        f"<tg-emoji emoji-id=\"5855024182412188879\">💬</tg-emoji><b>𝗧𝘆𝗽𝗲</b> ➛ <b>{card_type}</b>"
    )

    return header + card_lines + footer


def gen_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]
    ])

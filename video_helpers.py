import json
import random
import os
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

VIDEOS_CHANNEL = -1004400210635
_video_ids = []

def load_video_ids():
    global _video_ids
    path = os.path.join(os.path.dirname(__file__), "video_ids.json")
    try:
        with open(path) as f:
            _video_ids = json.load(f)
    except Exception:
        _video_ids = []

load_video_ids()

def get_random_video_id():
    if not _video_ids:
        return None
    return random.choice(_video_ids)

XCON_BUTTON = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗫𝗖𝗢𝗡 ★ 𝗫𝟯", url="https://t.me/Xconcc_bot", style="primary", icon_custom_emoji_id="5827986023254072662")]
])

async def send_random_video(bot, chat_id, caption=None, parse_mode="HTML", reply_markup=None):
    vid = get_random_video_id()
    if not vid:
        return None
    try:
        kwargs = {
            "chat_id": chat_id,
            "from_chat_id": VIDEOS_CHANNEL,
            "message_id": vid,
        }
        if caption:
            kwargs["caption"] = caption
            kwargs["parse_mode"] = parse_mode
        msg = await bot.copy_message(**kwargs)
        try:
            await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=reply_markup or XCON_BUTTON
            )
        except Exception:
            pass
        return msg.message_id
    except Exception as e:
        logging.warning(f"Failed to copy video {vid}: {e}")
        return None

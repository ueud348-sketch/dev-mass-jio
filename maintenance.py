import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import Router, types, BaseMiddleware
from aiogram.filters import Command
from database import is_gate_enabled, set_gate_status

ADMIN_IDS = [6113616017]

router = Router()

_maintenance_on = is_gate_enabled("maintenance")

MAINTENANCE_MSG = (
    "<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji> <b>𝗕𝗢𝗧 𝗨𝗡𝗗𝗘𝗥 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘</b>\n\n"
    "<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> 𝗣𝗹𝗲𝗮𝘀𝗲 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻 𝗹𝗮𝘁𝗲𝗿."
)

def is_maintenance_on() -> bool:
    return _maintenance_on

@router.message(Command("maintenance"))
async def maintenance_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("<tg-emoji emoji-id=\"5213415377593185638\">⛔</tg-emoji> Admin only.", parse_mode="HTML")
        return

    global _maintenance_on
    parts = message.text.split()
    if len(parts) < 2 or parts[1].lower() not in ("on", "off"):
        status = "ON" if _maintenance_on else "OFF"
        await message.reply(f"Usage: /maintenance [on|off]\nCurrent: {status}")
        return

    mode = parts[1].lower()
    _maintenance_on = (mode == "on")
    set_gate_status("maintenance", _maintenance_on)
    icon = "<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji>" if _maintenance_on else "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji>"
    await message.reply(
        f"{icon} Maintenance mode is now <b>{'ON' if _maintenance_on else 'OFF'}</b>.",
        parse_mode="HTML"
    )

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.Message, Dict[str, Any]], Awaitable[Any]],
        event: types.Message,
        data: Dict[str, Any]
    ) -> Any:
        if not _maintenance_on:
            return await handler(event, data)

        user = event.from_user
        if not user or user.id in ADMIN_IDS:
            return await handler(event, data)

        try:
            await event.reply(MAINTENANCE_MSG, parse_mode="HTML")
        except Exception:
            pass
        return

from aiogram import types, Router
from database import set_gate_status

# <tg-emoji emoji-id=\"5868424587749891806\">🔴</tg-emoji> Replace with your Telegram user ID(s)
ADMINS = [6113616017]

router = Router()

@router.message(lambda message: message.text and message.text.startswith("/on"))
async def on_command(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Usage: /on &lt;gate&gt;\nExample: /on au"
        )
        return

    gate = parts[1].lower()
    set_gate_status(gate, True)

    await message.reply(
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> <b>{gate.upper()}</b> gate is now <b>ENABLED</b>",
        parse_mode="HTML"
    )


@router.message(lambda message: message.text and message.text.startswith("/off"))
async def off_command(message: types.Message):
    if message.from_user.id not in ADMINS:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> Usage: /off &lt;gate&gt;\nExample: /off au"
        )
        return

    gate = parts[1].lower()
    set_gate_status(gate, False)

    await message.reply(
        f"🚧 <b>{gate.upper()}</b> gate is now <b>UNDER MAINTENANCE</b>",
        parse_mode="HTML"
    )

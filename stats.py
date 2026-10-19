import asyncio
import os
import collections
import logging
from html import escape as html_escape

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import types, F, Router

# Router for this module
router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_leaderboard_data():
    """
    Queries the database cc_hits column to count CHARGED cards per user.
    Returns a sorted list of top users.
    """
    import database

    top_users = []
    user_details = {}

    try:
        docs = database.get_top_users_by_hits(10)
        for d in docs:
            user_id = str(d["user_id"])
            count = d["cc_hits"]
            username = d.get("username") if d.get("username") and d.get("username") != 'None' else None
            first_name = d.get("first_name", "Unknown")

            top_users.append((user_id, count))
            user_details[user_id] = {
                "username": username,
                "first_name": first_name
            }
    except Exception as e:
        logging.error(f"Error querying leaderboard from DB: {e}")

    return top_users, user_details

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/stats"))
async def stats_command(message: types.Message):
    """
    Displays the top 10 users ranked by total Charged cards.
    Pulls data from DB cc_hits column.
    """
    
    # Create a status message while fetching
    status_msg = await message.answer("⏳ <b>Fetching Leaderboard...</b>", parse_mode="HTML")

    try:
        # Run file reading in thread to prevent blocking
        top_users, user_details = await asyncio.to_thread(get_leaderboard_data)

        # 1. Format the Message
        if not top_users:
            text = (
                "<b><tg-emoji emoji-id=\"6156436440260549720\">🏆</tg-emoji> 𝗟𝗲𝗮𝗱𝗲𝗿𝗯𝗼𝗮𝗿𝗱 (𝗖𝗵𝗮𝗿𝗴𝗲𝗱)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "No charged cards found yet.\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji> 𝗗𝗲𝘃 ➛ <a href='tg://openmessage?user_id=6113616017'>SpygenCVV</a>"
            )
        else:
            header = (
                "<b><tg-emoji emoji-id=\"6156436440260549720\">🏆</tg-emoji> 𝗟𝗲𝗮𝗱𝗲𝗿𝗯𝗼𝗮𝗿𝗱 (𝗖𝗵𝗮𝗿𝗴𝗲𝗱)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
            )
            
            list_text = ""
            for index, (user_id, count) in enumerate(top_users, 1):
                # Get details safely
                details = user_details.get(user_id, {})
                fname = details.get('first_name', 'Unknown')
                uname = details.get('username')

                # Create a clickable link to the user's profile
                if uname:
                    user_link = f'<a href="https://t.me/{uname}">{html_escape(str(fname))}</a>'
                else:
                    user_link = f'<a href="tg://user?id={user_id}">{html_escape(str(fname))}</a>'

                # Rank Medal
                medal = "🥇" if index == 1 else ("🥈" if index == 2 else ("🥉" if index == 3 else f"{index}."))

                list_text += f"{medal} {user_link} ➛ <b>{count} <tg-emoji emoji-id=\"5854966466641666181\">💎</tg-emoji></b>\n"

            footer = (
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji> 𝗗𝗲𝘃 ➛ <a href='tg://openmessage?user_id=8937448847'>воин</a>"
            )
            
            text = header + list_text + footer

        # 2. Edit the original message with the result
        await status_msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logging.error(f"Error in /stats command: {e}")
        await status_msg.edit_text("<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> <b>Error fetching stats.</b>", parse_mode="HTML")

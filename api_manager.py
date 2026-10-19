import os
import time
import logging
import asyncio

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHARED API MANAGER — copied from msh.py
# Used by hc.py, sp.py, sh.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

API_ENDPOINTS = []
API_HEALTH = {}
CURRENT_API_INDEX = 0
API_FAIL_COOLDOWN = 120


def load_api_endpoints():
    global API_ENDPOINTS, API_HEALTH
    try:
        if os.path.exists("api_endpoints.txt"):
            with open("api_endpoints.txt", "r", encoding="utf-8") as f:
                loaded = [line.strip() for line in f if line.strip()]
                if loaded:
                    API_ENDPOINTS = loaded
                    API_HEALTH.clear()
                    for endpoint in API_ENDPOINTS:
                        API_HEALTH[endpoint] = {"healthy": True, "last_fail": 0, "fail_count": 0, "success_count": 0}
                    logging.info(f"[API_MGR] Loaded {len(API_ENDPOINTS)} endpoints")
    except Exception as e:
        logging.error(f"[API_MGR] Error loading endpoints: {e}")


def get_next_healthy_api():
    global CURRENT_API_INDEX
    current_time = time.time()
    healthy_endpoints = []

    if not API_ENDPOINTS:
        return None

    for endpoint, health in API_HEALTH.items():
        if health["healthy"]:
            healthy_endpoints.append(endpoint)
        elif current_time - health["last_fail"] > API_FAIL_COOLDOWN:
            health["healthy"] = True
            health["fail_count"] = 0
            healthy_endpoints.append(endpoint)
            logging.info(f"[API_MGR] Recovered endpoint: {endpoint}")

    if not healthy_endpoints:
        logging.warning("[API_MGR] All endpoints unhealthy, resetting")
        for endpoint in API_ENDPOINTS:
            API_HEALTH[endpoint]["healthy"] = True
            API_HEALTH[endpoint]["fail_count"] = 0
        healthy_endpoints = API_ENDPOINTS.copy()

    start_idx = CURRENT_API_INDEX % len(healthy_endpoints)
    CURRENT_API_INDEX = (CURRENT_API_INDEX + 1) % len(healthy_endpoints)
    return healthy_endpoints[start_idx]


def mark_api_failure(endpoint: str):
    if endpoint in API_HEALTH:
        API_HEALTH[endpoint]["healthy"] = False
        API_HEALTH[endpoint]["last_fail"] = time.time()
        API_HEALTH[endpoint]["fail_count"] += 1
        logging.warning(f"[API_MGR] Marked as FAILED: {endpoint}")


def mark_api_success(endpoint: str):
    if endpoint in API_HEALTH:
        API_HEALTH[endpoint]["success_count"] += 1
        if not API_HEALTH[endpoint]["healthy"]:
            API_HEALTH[endpoint]["healthy"] = True
            API_HEALTH[endpoint]["fail_count"] = 0
            logging.info(f"[API_MGR] Recovered endpoint: {endpoint}")


def get_api_stats() -> dict:
    stats = {}
    for endpoint, health in API_HEALTH.items():
        short_name = endpoint.replace("https://", "").replace("http://", "").replace("/shopify", "")
        stats[short_name] = {
            "healthy": health["healthy"],
            "fail_count": health["fail_count"],
            "success_count": health["success_count"],
        }
    return stats


# ─── Proxy loading from database ───────────────────────

def normalize_proxy(proxy: str) -> str:
    """Convert 'user pass ip port' → 'ip:port:user:pass'"""
    if not proxy or not proxy.strip():
        return proxy
    parts = proxy.strip().split()
    if len(parts) == 4:
        user, pw, host, port = parts
        return f"{host}:{port}:{user}:{pw}"
    return proxy


async def get_user_proxies(user_id: int) -> list:
    import database
    proxies = []
    try:
        def _sync_fetch():
            docs = database.get_user_proxies(user_id)
            return [d["proxy"] for d in docs]
        raw = await asyncio.to_thread(_sync_fetch)
        proxies = [normalize_proxy(p) for p in raw]
    except Exception as e:
        logging.error(f"[API_MGR] Error fetching proxies for user {user_id}: {e}")
    return proxies


load_api_endpoints()

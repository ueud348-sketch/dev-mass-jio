import time
import random as _random
from datetime import datetime
from pymongo import MongoClient, ReturnDocument
import logging
from pymongo.errors import DuplicateKeyError, BulkWriteError

MONGO_URI = "mongodb+srv://xcon:xcon%40148@shein.dit627e.mongodb.net/?retryWrites=true&w=majority&appName=shein"
MONGO_DB = "ccc"

ADMIN_IDS = {6113616017}

_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
_db = _client[MONGO_DB]

_users        = _db["users"]
_proxies      = _db["proxies"]
_gate_status  = _db["gate_status"]
_receipts     = _db["receipts"]
_codes        = _db["codes"]
_banned_users = _db["banned_users"]

def init_all_tables():
    try:
        try:
            _codes.drop_index("code_1")
        except Exception:
            pass
        _proxies.create_index("user_id")
        _receipts.create_index("receipt_id", unique=True)
        _receipts.create_index("user_id")
        try:
            _users.drop_index("user_id_1")
        except Exception:
            pass
        _users.create_index([("cc_hits", -1)])
        print("[DB] MongoDB collections + indexes ready!")
    except Exception as e:
        print(f"[DB] Index creation note: {e}")

init_all_tables()

_gate_cache = {}
_gate_cache_ttl = 30
_credits_cache = {}
_credits_cache_ttl = 5

def get_user(user_id: int):
    doc = _users.find_one({"_id": user_id})
    if not doc:
        return None
    return {
        "user_id": doc["_id"],
        "username": doc.get("username"),
        "first_name": doc.get("first_name", "User"),
        "credits": doc.get("credits", 0),
        "is_premium": doc.get("is_premium", 0),
        "premium_expiry": doc.get("premium_expiry"),
        "cc_checked": doc.get("cc_checked", 0),
        "cc_charged": doc.get("cc_charged", 0),
        "cc_hits": doc.get("cc_hits", 0),
        "joined_at": doc.get("joined_at"),
    }

def create_user(user_id: int, username: str):
    _users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {
            "username": username,
            "first_name": username or "User",
            "credits": 25000,
            "is_premium": 0,
            "premium_expiry": None,
            "cc_checked": 0,
            "cc_charged": 0,
            "cc_hits": 0,
            "joined_at": datetime.now().isoformat(),
        }},
        upsert=True,
    )

def get_user_credits(user_id: int) -> int:
    now = time.monotonic()
    cached = _credits_cache.get(user_id)
    if cached and now < cached[1]:
        return cached[0]
    doc = _users.find_one({"_id": user_id}, {"credits": 1})
    credits = doc.get("credits", 0) if doc else 0
    _credits_cache[user_id] = (credits, now + _credits_cache_ttl)
    return credits

def update_credits(user_id: int, new_credits: int):
    _users.update_one({"_id": user_id}, {"$set": {"credits": new_credits}})
    _credits_cache.pop(user_id, None)

def deduct_credits_atomic(user_id: int, amount: int) -> int:
    doc = _users.find_one_and_update(
        {"_id": user_id, "credits": {"$gte": amount}},
        {"$inc": {"credits": -amount}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        doc = _users.find_one({"_id": user_id}, {"credits": 1})
        new_credits = doc.get("credits", 0) if doc else 0
    else:
        new_credits = doc.get("credits", 0)
    _credits_cache.pop(user_id, None)
    return new_credits

def update_user_stats(user_id: int, is_charged: bool):
    inc = {"cc_checked": 1}
    if is_charged:
        inc["cc_charged"] = 1
    _users.update_one({"_id": user_id}, {"$inc": inc})

def update_user_stats_bulk(user_id: int, checked_count: int, charged_count: int = 0):
    inc = {"cc_checked": checked_count}
    if charged_count > 0:
        inc["cc_charged"] = charged_count
    _users.update_one({"_id": user_id}, {"$inc": inc})

def update_user_hits(user_id: int, count: int = 1):
    _users.update_one({"_id": user_id}, {"$inc": {"cc_hits": count}})

def is_gate_enabled(gate: str) -> bool:
    now = time.monotonic()
    cached = _gate_cache.get(gate)
    if cached and now < cached[1]:
        return cached[0]
    doc = _gate_status.find_one({"_id": gate})
    status = True
    if doc is None:
        _gate_status.update_one(
            {"_id": gate},
            {"$setOnInsert": {"is_enabled": 1, "updated_at": datetime.now().isoformat()}},
            upsert=True,
        )
    else:
        status = bool(doc.get("is_enabled", 1))
    _gate_cache[gate] = (status, now + _gate_cache_ttl)
    return status

def set_gate_status(gate: str, enabled: bool):
    _gate_status.update_one(
        {"_id": gate},
        {"$set": {"is_enabled": 1 if enabled else 0, "updated_at": datetime.now().isoformat()}},
        upsert=True,
    )
    _gate_cache.pop(gate, None)

def get_random_proxy(user_id: int) -> str | None:
    docs = list(_proxies.find({"user_id": user_id}, {"proxy": 1}))
    if not docs:
        return None
    raw = _random.choice([d["proxy"] for d in docs])
    parts = raw.split()
    if len(parts) == 4:
        user, pw, host, port = parts
        return f"{host}:{port}:{user}:{pw}"
    return raw

def get_user_plan(user_id: int) -> str | None:
    doc = _receipts.find_one(
        {"user_id": user_id},
        sort=[("purchased_on", -1)],
    )
    return doc.get("plan") if doc else None

def get_all_user_ids() -> list[int]:
    return [doc["_id"] for doc in _users.find({}, {"_id": 1})]

def get_top_users_by_hits(limit: int = 10) -> list[dict]:
    docs = _users.find(
        {"cc_hits": {"$gt": 0}},
        {"_id": 1, "username": 1, "first_name": 1, "cc_hits": 1},
        sort=[("cc_hits", -1)],
        limit=limit,
    )
    return [{
        "user_id": d["_id"],
        "username": d.get("username"),
        "first_name": d.get("first_name"),
        "cc_hits": d.get("cc_hits", 0),
    } for d in docs]

def add_proxy(user_id: int, proxy_str: str):
    _proxies.insert_one({
        "user_id": user_id,
        "proxy": proxy_str,
        "added_at": datetime.now().isoformat(),
    })

def get_user_proxies(user_id: int) -> list[dict]:
    return list(_proxies.find({"user_id": user_id}))

def delete_proxies_by_ids(proxy_oids: list) -> int:
    if not proxy_oids:
        return 0
    result = _proxies.delete_many({"_id": {"$in": proxy_oids}})
    return result.deleted_count

def count_proxies(user_id: int) -> int:
    return _proxies.count_documents({"user_id": user_id})

def delete_all_proxies(user_id: int) -> int:
    result = _proxies.delete_many({"user_id": user_id})
    return result.deleted_count

def is_banned(user_id: int) -> bool:
    return _banned_users.find_one({"_id": user_id}) is not None

def ban_user(user_id: int):
    _banned_users.update_one(
        {"_id": user_id},
        {"$set": {"banned_at": datetime.now().isoformat()}},
        upsert=True,
    )

def unban_user(user_id: int):
    _banned_users.delete_one({"_id": user_id})

def init_banned_collection():
    pass

def insert_receipt(receipt_id: str, user_id: int, plan: str, amount_paid: float,
                   purchased_on: str, expires_on: str):
    _receipts.insert_one({
        "receipt_id": receipt_id,
        "user_id": user_id,
        "plan": plan,
        "amount_paid": amount_paid,
        "purchased_on": purchased_on,
        "expires_on": expires_on,
    })

def get_receipt(receipt_id: str) -> dict | None:
    receipt = _receipts.find_one({"receipt_id": receipt_id})
    if not receipt:
        return None
    user = _users.find_one({"_id": receipt.get("user_id")})
    return {
        "receipt_id": receipt["receipt_id"],
        "user_id": receipt["user_id"],
        "plan": receipt.get("plan"),
        "amount_paid": receipt.get("amount_paid", 0),
        "purchased_on": receipt.get("purchased_on"),
        "expires_on": receipt.get("expires_on"),
        "first_name": user.get("first_name", "User") if user else "User",
        "is_premium": user.get("is_premium", 0) if user else 0,
        "credits": user.get("credits", 0) if user else 0,
    }

def get_all_premium_users() -> list[dict]:
    now = datetime.now().isoformat()
    users = list(_users.find({"is_premium": 1, "premium_expiry": {"$gt": now}}))
    result = []
    for u in users:
        uid = u["_id"]
        receipt = _receipts.find_one(
            {"user_id": uid},
            sort=[("purchased_on", -1)],
        )
        result.append({
            "user_id": uid,
            "username": u.get("username"),
            "plan": receipt.get("plan") if receipt else None,
            "receipt_id": receipt.get("receipt_id") if receipt else None,
            "purchased_on": receipt.get("purchased_on") if receipt else None,
            "premium_expiry": u.get("premium_expiry"),
            "credits": u.get("credits", 0),
        })
    return result

def generate_codes(amount: int, credits_per: int = 100) -> list[str]:
    import string
    from pymongo.errors import BulkWriteError
    docs = []
    for _ in range(amount):
        code = "XCON-" + "".join(_random.choices(string.ascii_uppercase + string.digits, k=8))
        docs.append({"_id": code, "credits": credits_per, "claimed_by": None, "claimed_at": None})
    inserted_ids = set()
    try:
        result = _codes.insert_many(docs, ordered=False)
        inserted_ids = set(result.inserted_ids)
    except BulkWriteError as bwe:
        inserted_ids = set(bwe.details.get("insertedIds", {}).values())
    except Exception as e:
        logging.error(f"[DB] generate_codes failed: {e}")
        return []
    return [doc["_id"] for doc in docs if doc["_id"] in inserted_ids]

def claim_code(user_id: int, code: str) -> tuple[str, int | None]:
    doc = _codes.find_one_and_update(
        {"_id": code, "claimed_by": None},
        {"$set": {"claimed_by": user_id, "claimed_at": datetime.now().isoformat()}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        existing = _codes.find_one({"_id": code})
        if not existing:
            return "invalid", None
        return "claimed", None
    credits = doc.get("credits", 0)
    _users.update_one({"_id": user_id}, {"$inc": {"credits": credits}}, upsert=True)
    return "ok", credits

def set_user_premium(user_id: int, expiry_date: str):
    _users.update_one(
        {"_id": user_id},
        {"$set": {"is_premium": 1, "premium_expiry": expiry_date}},
    )

def remove_premium(user_id: int):
    _users.update_one(
        {"_id": user_id},
        {"$set": {"is_premium": 0, "premium_expiry": None, "credits": 150}},
    )

def add_credits(user_id: int, amount: int) -> int:
    doc = _users.find_one_and_update(
        {"_id": user_id},
        {"$inc": {"credits": amount}},
        return_document=ReturnDocument.AFTER,
    )
    return doc.get("credits", 0) if doc else 0

def get_user_status(user_id: int) -> tuple[str, str, str]:
    user = get_user(user_id)
    if not user:
        return "0", "Trial", "N/A"
    credits_str = str(user.get("credits", 0))
    plan = "Trial"
    if user_id in ADMIN_IDS:
        plan = "Admin"
    joined_str = "N/A"
    if user.get("joined_at"):
        joined_str = user["joined_at"][:10] if len(user["joined_at"]) >= 10 else user["joined_at"]
    if user.get("is_premium") == 1:
        expiry = user.get("premium_expiry")
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry) if isinstance(expiry, str) else expiry
                if datetime.now() < expiry_date:
                    plan = get_user_plan(user_id) or "Premium"
            except Exception:
                plan = "Premium"
        else:
            plan = "Premium"
    return credits_str, plan, joined_str

def get_premium_status(user_id: int) -> tuple[bool, str | None]:
    user = get_user(user_id)
    if not user:
        return False, None
    is_prem = user.get("is_premium", 0)
    expiry = user.get("premium_expiry")
    if is_prem == 1:
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry) if isinstance(expiry, str) else expiry
            except Exception:
                expiry_date = expiry
            if datetime.now() < expiry_date:
                return True, expiry
            else:
                remove_premium(user_id)
                return False, None
        else:
            _users.update_one({"_id": user_id}, {"$set": {"is_premium": 0}})
            return False, None
    elif expiry:
        try:
            expiry_date = datetime.fromisoformat(expiry) if isinstance(expiry, str) else expiry
        except Exception:
            expiry_date = expiry
        if datetime.now() > expiry_date:
            _users.update_one({"_id": user_id}, {"$set": {"premium_expiry": None, "credits": 150}})
            return False, None
    return False, None

def resolve_user_id(target_input: str) -> int | None:
    if target_input.isdigit():
        uid = int(target_input)
        if _users.find_one({"_id": uid}):
            return uid
        return None
    username = target_input.lstrip("@")
    doc = _users.find_one({"username": username})
    return doc["_id"] if doc else None

def ensure_user_exists(user_id: int, name: str = "User"):
    _users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {
            "username": name,
            "first_name": name,
            "credits": 0,
            "is_premium": 0,
            "premium_expiry": None,
            "joined_at": datetime.now().isoformat(),
        }},
        upsert=True,
    )
    _users.update_one({"_id": user_id}, {"$set": {"first_name": name}})

def get_user_info(user_id: int, username: str, first_name: str) -> tuple[dict, dict | None]:
    get_premium_status(user_id)
    user = get_user(user_id)
    if not user:
        create_user(user_id, username or first_name)
        user = get_user(user_id)
    receipt_row = None
    if user and user.get("is_premium") == 1:
        doc = _receipts.find_one(
            {"user_id": user_id},
            sort=[("purchased_on", -1)],
        )
        if doc:
            receipt_row = {
                "plan": doc.get("plan"),
                "purchased_on": doc.get("purchased_on"),
            }
    return user or {}, receipt_row

def sub_db_sync(target_id: int, display_name: str, plan_name: str,
                days: int, credits: int, amount: float, hours: int = 0) -> str:
    from datetime import timedelta
    import random as _rand
    import string as _str
    expiry_date = (datetime.now() + timedelta(days=days, hours=hours)).isoformat()
    receipt_id = f"Xcon-{''.join(_rand.choices(_str.digits, k=6))}-CHK"
    purchased_on = datetime.now().isoformat()
    ensure_user_exists(target_id, display_name)
    _users.update_one({"_id": target_id}, {"$set": {"first_name": display_name}})
    set_user_premium(target_id, expiry_date)
    add_credits(target_id, credits)
    insert_receipt(receipt_id, target_id, plan_name, amount, purchased_on, expiry_date)
    return receipt_id

def adcr_db_sync(target_id: int, display_name: str, add_credits_amount: int) -> int:
    ensure_user_exists(target_id, display_name)
    return add_credits(target_id, add_credits_amount)

def rsub_db_sync(target_id: int) -> dict | None:
    remove_premium(target_id)
    user = get_user(target_id)
    if not user:
        return None
    return {
        "first_name": user.get("first_name"),
        "username": user.get("username"),
    }

def rc_db_sync(receipt_id: str) -> dict | None:
    return get_receipt(receipt_id)

def info_db_sync(user_id: int, username: str, first_name: str) -> tuple[dict, dict | None]:
    return get_user_info(user_id, username, first_name)

def suball_db_sync() -> list[dict]:
    return get_all_premium_users()

def g_code_db_sync(amount: int, credits_per: int = 100) -> list[str]:
    return generate_codes(amount, credits_per=credits_per)

def claim_db_sync(user_id: int, code: str) -> tuple[str, int | None]:
    user = get_user(user_id)
    if user and user.get("is_premium") == 1:
        return "premium", None
    return claim_code(user_id, code)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PREMIUM KEY SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_premium_keys = _db["premium_keys"]

PLAN_CONFIG = {
    "core":  {"days": 7,  "hours": 0,  "credits": 13000},
    "elite": {"days": 15, "hours": 0,  "credits": 23000},
    "root":  {"days": 30, "hours": 0,  "credits": 53000},
    "1h":    {"days": 0,  "hours": 1,  "credits": 2000},
    "5h":    {"days": 0,  "hours": 5,  "credits": 8000},
    "2d":    {"days": 2,  "hours": 0,  "credits": 5000},
}

def generate_premium_keys(amount: int, plan: str) -> list[str]:
    import string as _string
    plan = plan.lower()
    if plan not in PLAN_CONFIG:
        return []
    cfg = PLAN_CONFIG[plan]
    docs = []
    for _ in range(amount):
        suffix = "".join(_random.choices(_string.ascii_uppercase + _string.digits, k=8))
        key = f"XCON-{plan.upper()}-{suffix}"
        docs.append({
            "_id": key,
            "plan": plan,
            "days": cfg["days"],
            "hours": cfg.get("hours", 0),
            "credits": cfg["credits"],
            "claimed_by": None,
            "claimed_at": None,
        })
    inserted_ids = set()
    try:
        result = _premium_keys.insert_many(docs, ordered=False)
        inserted_ids = set(result.inserted_ids)
    except BulkWriteError as bwe:
        inserted_ids = set(bwe.details.get("insertedIds", {}).values())
    except Exception as e:
        logging.error(f"[DB] generate_premium_keys failed: {e}")
        return []
    return [doc["_id"] for doc in docs if doc["_id"] in inserted_ids]

def claim_premium_key(user_id: int, key: str) -> tuple[str, str | None, int | None]:
    key = key.upper().strip()
    doc = _premium_keys.find_one({"_id": key})
    if not doc:
        return "invalid", None, None
    if doc.get("claimed_by") is not None:
        return "claimed", None, None
    user = get_user(user_id)
    if user and user.get("is_premium") == 1:
        return "premium", None, None
    from datetime import timedelta
    days = doc.get("days", 0)
    hours = doc.get("hours", 0)
    credits = doc.get("credits", 0)
    plan = doc.get("plan", "core")
    now = datetime.now()
    expiry = now + timedelta(days=days, hours=hours)
    _premium_keys.update_one(
        {"_id": key},
        {"$set": {"claimed_by": user_id, "claimed_at": now.isoformat()}}
    )
    ensure_user_exists(user_id)
    _users.update_one(
        {"_id": user_id},
        {"$set": {
            "is_premium": 1,
            "premium_expiry": expiry.isoformat(),
            "premium_plan": plan,
        }, "$inc": {"credits": credits}},
        upsert=True,
    )
    return "ok", plan, credits

def list_unclaimed_keys(plan: str = None) -> list[dict]:
    query = {"claimed_by": None}
    if plan:
        query["plan"] = plan.lower()
    docs = list(_premium_keys.find(query))
    return [{"key": d["_id"], "plan": d["plan"], "days": d["days"], "hours": d.get("hours", 0), "credits": d["credits"]} for d in docs]
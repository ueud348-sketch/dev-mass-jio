from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

# Each page will be padded to this many entry slots so all pages are the same height.
ENTRIES_PER_PAGE = 5

PAGES = [
    {
        "title": "Auth Gates",
        "entries": [
            {"gate": "Stripe Auth 0$",     "cmd": "/chk",  "limit": None,   "premium": False},
            {"gate": "Braintree 0$",       "cmd": "/b3",   "limit": None,   "premium": False},
            {"gate": "Braintree VBV 0$",   "cmd": "/vbv",  "limit": None,   "premium": False},
        ],
    },
    {
        "title": "Charge Gates I",
        "entries": [
            {"gate": "Stripe 0.50$",       "cmd": "/st",   "limit": None,   "premium": False},
            {"gate": "PayPal 0.10$",       "cmd": "/pp",   "limit": None,   "premium": False},
            {"gate": "Shopify 5$",         "cmd": "/hc",   "limit": None,   "premium": False},
            {"gate": "Shopify 1$",         "cmd": "/sp",   "limit": None,   "premium": False},
            {"gate": "PayFast 0.30$",      "cmd": "/pf",   "limit": None,   "premium": False},
        ],
    },
    {
        "title": "Charge Gates II",
        "entries": [
            {"gate": "FatZebra 4$",        "cmd": "/ft",   "limit": None,   "premium": False},
            {"gate": "NMI 1$",             "cmd": "/nmi",  "limit": None,   "premium": False},
            {"gate": "NMI2 1$",            "cmd": "/nmi2", "limit": None,   "premium": False},
            {"gate": "BluePay 20$",        "cmd": "/bl",   "limit": None,   "premium": False},
        ],
    },
    {
        "title": "Charge Gates III",
        "entries": [
            {"gate": "Authorize.net 1$",   "cmd": "/at",   "limit": None,   "premium": False},
            {"gate": "PayWay 1$",          "cmd": "/pw",   "limit": None,   "premium": False},
            {"gate": "Razorpay 100₹",        "cmd": "/rz",   "limit": None,   "premium": False},
            {"gate": "PayU 1$",            "cmd": "/pyu",  "limit": None,   "premium": True},
            {"gate": "Jio Recharge 19₹",   "cmd": "/jio",  "limit": None,   "premium": False},
        ],
    },
    {
        "title": "Mass Gates",
        "entries": [
            {"gate": "Shopify Mass 0-20$", "cmd": "/msh",  "limit": "5000", "premium": True},
            {"gate": "Stripe Mass 0.50$",  "cmd": "/mst",  "limit": "2000", "premium": True},
            {"gate": "Shopify 1$",         "cmd": "/sh",   "limit": "50",   "premium": False},
            {"gate": "Stripe 3DS Hitter",  "cmd": "/hit",  "limit": None,   "premium": False},
        ],
    },
    {
        "title": "Tools",
        "entries": [
            {"gate": "BIN Lookup",         "cmd": "/bin",        "limit": None, "premium": False},
            {"gate": "Set Proxy",          "cmd": "/proxy",      "limit": None, "premium": False},
            {"gate": "Check Proxy",        "cmd": "/checkproxy", "limit": None, "premium": False},
            {"gate": "Clear Proxy",        "cmd": "/clearproxy", "limit": None, "premium": False},
        ],
    },
    {
        "title": "Account",
        "entries": [
            {"gate": "Statistics",         "cmd": "/stats",    "limit": None, "premium": False},
            {"gate": "Account Info",       "cmd": "/info",     "limit": None, "premium": False},
            {"gate": "Buy Plan",           "cmd": "/buy",      "limit": None, "premium": False},
            {"gate": "Claim Code",         "cmd": "/claim",    "limit": None, "premium": False},
            {"gate": "Redeem Key",         "cmd": "/redeem",   "limit": None, "premium": False},
            {"gate": "Give Feedback",      "cmd": "/fb",       "limit": None, "premium": False},
        ],
    },
]

TOTAL_PAGES = len(PAGES)
_SEP = "━━━━━━━━━━━━━━━━"
_SP  = "\u00a0"  # non-breaking space used as invisible filler line

def _build_text(i: int) -> str:
    page = PAGES[i]
    lines = [_SEP, f"<b>{page['title']}  ·  {i + 1} / {TOTAL_PAGES}</b>", _SEP]
    for e in page["entries"]:
        lines.append(f"<b>Gate  ➛  {e['gate']}</b>")
        lines.append(f"<b>Cmd   ➛  {e['cmd']}</b>")
        if e["limit"] is not None:
            lines.append(f"<b>Limit ➛  {e['limit']}</b>")
        lines.append(f"<b>Type  ➛  {'Premium' if e['premium'] else 'Free'}</b>")
        lines.append(_SEP)
    # Pad shorter pages so every page has the same visual height
    pad = ENTRIES_PER_PAGE - len(page["entries"])
    for _ in range(pad):
        lines.append(f"<b>{_SP}</b>")
        lines.append(f"<b>{_SP}</b>")
        lines.append(f"<b>{_SP}</b>")
        lines.append(_SEP)
    return "\n".join(lines)

def _build_kb(i: int) -> InlineKeyboardMarkup:
    nav = []
    if i > 0:
        nav.append(InlineKeyboardButton(text="« Prev", callback_data=f"cmds_page_{i - 1}", style="primary"))
    nav.append(InlineKeyboardButton(text=f"{i + 1} / {TOTAL_PAGES}", callback_data="cmds_noop", style="primary"))
    if i < TOTAL_PAGES - 1:
        nav.append(InlineKeyboardButton(text="Next »", callback_data=f"cmds_page_{i + 1}", style="primary"))
    return InlineKeyboardMarkup(inline_keyboard=[nav])

# Only keyboard is cached — text is rebuilt each time for random emojis
_KB_CACHE: list[InlineKeyboardMarkup] = [_build_kb(i) for i in range(TOTAL_PAGES)]

@router.message(Command("cmds"))
async def cmds_command(message: types.Message):
    text = _build_text(0)
    await message.reply(text=text, parse_mode="HTML", reply_markup=_KB_CACHE[0], disable_web_page_preview=True)

@router.callback_query(F.data.startswith("cmds_page_"))
async def cmds_page_callback(callback: types.CallbackQuery):
    await callback.answer()
    try:
        idx = int(callback.data[10:])
    except ValueError:
        return
    if not (0 <= idx < TOTAL_PAGES):
        return
    text = _build_text(idx)
    try:
        await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=_KB_CACHE[idx], disable_web_page_preview=True)
    except Exception:
        pass

@router.callback_query(F.data == "cmds_noop")
async def cmds_noop(callback: types.CallbackQuery):
    await callback.answer()

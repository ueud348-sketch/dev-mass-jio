# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UI HELPERS — Double Rule theme with premium tg-emoji
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import re
import random

_DIAMOND_IDS = [
    "5285221724634239278",
    "5287777298894835685",
    "5285024405246725814",
    "5285373878145667586",
    "5287360712836928126",
    "5287547831677112267",
    "5287658362660474522",
    "5285186510197381130",
]

def random_diamond():
    """Return a random premium diamond tg-emoji tag"""
    eid = random.choice(_DIAMOND_IDS)
    return f'<tg-emoji emoji-id="{eid}">💎</tg-emoji>'

_STATUS_IDS = [
    "5343528160535270636", "5343672411306875017", "5343819952023428595",
    "5042334757040423886", "5879783483462655267", "5042334757040423886",
    "6125139082294072249",
]

_CARD_IDS = [
    "5954273871531086941", "5960605709887345250", "5962804544164338396",
    "6075850883713736026", "5424925715009118244", "5976566856331305746",
    "5855210601172705878",
]

_GATEWAY_IDS = [
    "6105016735310547954", "5215441850537618106", "6305349287194662922",
    "6044275465269547247", "4967826519087907994", "5215441850537618106",
    "6019171647712401866", "5877738786971979125",
]

_RESPONSE_IDS = [
    "5285450204009483872", "5285138483873074677", "5285390413769758368",
    "5285239703367341870", "6100598489568253573", "5040036030414062506",
    "6318614147659468549", "6044204572539361013", "6206495649895028694",
]

_BRAND_VISA = "5125199987738674893"
_BRAND_MASTERCARD = "5136474341315184612"
_BRAND_OTHER_IDS = [
    "5210935111289159311", "5210708311246126137", "5208536350579506258",
    "5211001816426232662", "5208621167593667859", "5211212613421121581",
    "5211053042501172685", "5208959082735616282", "5210903345711037271",
    "5211052376781241550", "5208957046921116374",
]

_ISSUER_IDS = ["5039834781131474002", "5039865760730579942"]

_COUNTRY_IDS = [
    "4967844098389050235", "5125258236085143187", "5224450179368767019",
    "5303440357428586778", "5278430152978628144",
]

_USER_IDS = ["5195035460186970394"]

_APPROVED_IDS = [
    "5211157547645421280", "5208467510843686607", "5211051938694577290",
    "5208573171334135523", "5210903100897902475", "5210729536974503652",
    "5208858619155594626", "5211089128816393626",
]

def random_status():
    eid = random.choice(_STATUS_IDS)
    return f'<tg-emoji emoji-id="{eid}">⚡</tg-emoji>'

def random_card():
    eid = random.choice(_CARD_IDS)
    return f'<tg-emoji emoji-id="{eid}">💳</tg-emoji>'

def random_gateway():
    eid = random.choice(_GATEWAY_IDS)
    return f'<tg-emoji emoji-id="{eid}">🔗</tg-emoji>'

def random_response():
    eid = random.choice(_RESPONSE_IDS)
    return f'<tg-emoji emoji-id="{eid}">💬</tg-emoji>'

def random_brand(scheme):
    s = str(scheme).lower()
    if "visa" in s:
        return f'<tg-emoji emoji-id="{_BRAND_VISA}">📱</tg-emoji>'
    if "master" in s:
        return f'<tg-emoji emoji-id="{_BRAND_MASTERCARD}">💸</tg-emoji>'
    eid = random.choice(_BRAND_OTHER_IDS)
    return f'<tg-emoji emoji-id="{eid}">🔘</tg-emoji>'

def random_issuer():
    eid = random.choice(_ISSUER_IDS)
    return f'<tg-emoji emoji-id="{eid}">🍽</tg-emoji>'

def random_country():
    eid = random.choice(_COUNTRY_IDS)
    return f'<tg-emoji emoji-id="{eid}">🌍</tg-emoji>'

def random_user():
    eid = random.choice(_USER_IDS)
    return f'<tg-emoji emoji-id="{eid}">💋</tg-emoji>'

def random_approved():
    eid = random.choice(_APPROVED_IDS)
    return f'<tg-emoji emoji-id="{eid}">🤔</tg-emoji>'

_TYPE_IDS = [
    "5861556273618623389", "5211089128816393626", "5208858619155594626",
    "5210729536974503652", "5210903100897902475", "5208573171334135523",
    "5211051938694577290", "5208467510843686607", "5211157547645421280",
    "5211052376781241550", "5208957046921116374",
]

def random_type():
    eid = random.choice(_TYPE_IDS)
    return f'<tg-emoji emoji-id="{eid}">🔥</tg-emoji>'

_STAR_IDS = [
    "6023898164732366954", "5192722817866574644", "6147524086768604985",
    "6235355429237430006", "6235234890980269200", "6300694612092653346",
    "5350377396421797635", "5352792254668873738", "5350339119673254559",
    "5352547909684437924", "5350313358459412048", "5350492952516895018",
    "5350501108659790021", "5370784581341422520", "5267500801240092311",
    "5895551854594496069", "5895479518755294875", "5895429198918454389",
    "5895547297634192988", "5895371337119043741", "5897674509036556202",
    "5895594409130462864", "5897890679035530534", "5897902017749192455",
    "5895632423885999782", "5895276233658207402", "5895351575974514024",
    "5895557811714133547", "5895591338228846213", "5895465280938709039",
    "5895544351286628104", "5895362317687723000", "5895229289665662952",
    "5895565366561606879", "5895665142946859880", "5895578414672252671",
    "5895651600914975891", "5895706503481921737", "5895318023689998340",
    "5895342101276659067", "5895654500017901480", "5895516167711231784",
    "5895623189706313871", "5895475262442704718", "5895217654599257520",
    "5895372986386485114", "5800688138833629633", "5866080574988358459",
    "5891044423856296980", "5913546328750690522", "5913265296155611115",
    "5931592939514892319", "5931458000232386501", "5931266229942620658",
    "5931408616698416937",
]

def random_star():
    """Return a random premium star tg-emoji tag"""
    eid = random.choice(_STAR_IDS)
    return f'<tg-emoji emoji-id="{eid}">⭐</tg-emoji>'

REPLY_EMOJI_ID = "6127408113516551181"

_SANS_UPPER = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭"
_SANS_LOWER = "𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"
_ITAL_UPPER = "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡"
_ITAL_LOWER = "𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻"
_DIGITS = "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"

def sans(s):
    """ASCII letters/digits to bold sans Unicode — preserves HTML tags"""
    out = []
    in_tag = False
    for ch in str(s):
        if ch == '<':
            in_tag = True
            out.append(ch)
        elif ch == '>':
            in_tag = False
            out.append(ch)
        elif in_tag:
            out.append(ch)
        elif 'A' <= ch <= 'Z':
            out.append(_SANS_UPPER[ord(ch) - ord('A')])
        elif 'a' <= ch <= 'z':
            out.append(_SANS_LOWER[ord(ch) - ord('a')])
        elif '0' <= ch <= '9':
            out.append(_DIGITS[int(ch)])
        else:
            out.append(ch)
    return ''.join(out)

def ital(s):
    """ASCII letters to italic bold sans Unicode — preserves HTML tags"""
    out = []
    in_tag = False
    for ch in str(s):
        if ch == '<':
            in_tag = True
            out.append(ch)
        elif ch == '>':
            in_tag = False
            out.append(ch)
        elif in_tag:
            out.append(ch)
        elif 'A' <= ch <= 'Z':
            out.append(_ITAL_UPPER[ord(ch) - ord('A')])
        elif 'a' <= ch <= 'z':
            out.append(_ITAL_LOWER[ord(ch) - ord('a')])
        else:
            out.append(ch)
    return ''.join(out)

def fw(s):
    """Digits to bold sans Unicode digits"""
    out = []
    for ch in str(s):
        if '0' <= ch <= '9':
            out.append(_DIGITS[int(ch)])
        else:
            out.append(ch)
    return ''.join(out)

def _sentence(s):
    s = re.sub(r'[_\-]+', ' ', str(s))
    s = re.sub(r'\s+', ' ', s).strip()
    if not s:
        return s
    if len(s) == 1:
        return s.upper()
    return s[0].upper() + s[1:].lower()

def fmt_response(msg):
    """Clean API response to sentence case bold sans"""
    return sans(_sentence(msg))

def fmt_brand(scheme):
    """VISA -> Visa"""
    return sans(_sentence(scheme))

_DROP_WORDS = {"bank", "banking", "ltd", "llc", "inc", "n.a.", "na", "s.a.", "co."}

def fmt_issuer(bank):
    """CHASE BANK -> Chase"""
    s = str(bank)
    words = [w for w in re.split(r'\s+', s) if w.strip('.').lower() not in _DROP_WORDS]
    return sans(_sentence(' '.join(words)))

_COUNTRY_CODES = {
    "UNITED STATES": "US", "USA": "US", "INDIA": "IN", "UNITED KINGDOM": "UK",
    "CANADA": "CA", "GERMANY": "DE", "FRANCE": "FR", "BRAZIL": "BR", "MEXICO": "MX",
    "AUSTRALIA": "AU", "NETHERLANDS": "NL", "ITALY": "IT", "SPAIN": "ES", "RUSSIA": "RU",
    "CHINA": "CN", "JAPAN": "JP", "TURKEY": "TR", "INDONESIA": "ID", "PHILIPPINES": "PH",
    "MALAYSIA": "MY", "SINGAPORE": "SG", "THAILAND": "TH", "VIETNAM": "VN",
    "PAKISTAN": "PK", "BANGLADESH": "BD", "NIGERIA": "NG", "SOUTH AFRICA": "ZA",
    "EGYPT": "EG", "SAUDI ARABIA": "SA", "UNITED ARAB EMIRATES": "AE", "UAE": "AE",
    "ISRAEL": "IL", "POLAND": "PL", "UKRAINE": "UA", "ROMANIA": "RO",
    "CZECH REPUBLIC": "CZ", "CZECHIA": "CZ", "SWEDEN": "SE", "NORWAY": "NO",
    "DENMARK": "DK", "FINLAND": "FI", "IRELAND": "IE", "BELGIUM": "BE",
    "SWITZERLAND": "CH", "AUSTRIA": "AT", "PORTUGAL": "PT", "GREECE": "GR",
    "HUNGARY": "HU", "ARGENTINA": "AR", "CHILE": "CL", "COLOMBIA": "CO",
    "PERU": "PE", "VENEZUELA": "VE", "ECUADOR": "EC", "NEW ZEALAND": "NZ",
    "HONG KONG": "HK", "SOUTH KOREA": "KR", "KOREA": "KR", "TAIWAN": "TW",
    "KENYA": "KE", "GHANA": "GH", "MOROCCO": "MA", "ALGERIA": "DZ", "TUNISIA": "TN",
    "SRI LANKA": "LK", "NEPAL": "NP", "IRAN": "IR", "IRAQ": "IQ", "JORDAN": "JO",
    "LEBANON": "LB", "KUWAIT": "KW", "QATAR": "QA", "BAHRAIN": "BH", "OMAN": "OM",
    "KAZAKHSTAN": "KZ", "UZBEKISTAN": "UZ", "AZERBAIJAN": "AZ", "GEORGIA": "GE",
    "SERBIA": "RS", "CROATIA": "HR", "SLOVENIA": "SI", "SLOVAKIA": "SK",
    "BULGARIA": "BG", "LITHUANIA": "LT", "LATVIA": "LV", "ESTONIA": "EE",
    "BELARUS": "BY", "MACEDONIA": "MK", "ALBANIA": "AL", "ICELAND": "IS",
    "LUXEMBOURG": "LU", "MALTA": "MT", "CYPRUS": "CY", "DOMINICAN REPUBLIC": "DO",
    "PUERTO RICO": "PR", "JAMAICA": "JM", "GUATEMALA": "GT", "PANAMA": "PA",
    "COSTA RICA": "CR", "URUGUAY": "UY", "PARAGUAY": "PY", "BOLIVIA": "BO",
}

def fmt_country(country):
    """UNITED STATES -> US (ISO code, bold sans)"""
    key = str(country).strip().upper()
    if not key:
        return sans("?")
    if len(key) == 2:
        return sans(key)
    code = _COUNTRY_CODES.get(key)
    if code:
        return sans(code)
    return sans(_sentence(country))

def fmt_plan(plan_name):
    """PREMIUM -> premium (bold sans lowercase)"""
    return sans(str(plan_name).lower())

_RULE = "═══════════════"

def _status_display(status):
    """Map gate final_status (bold sans + tg-emoji) to icon + italic value"""
    s = re.sub(r"<[^>]+>", "", str(status))
    if "𝗖𝗛𝗔𝗥𝗚𝗘𝗗" in s:
        return "\U0001f48e", "𝘊𝘩𝘢𝘳𝘨𝘦𝘥"
    if "𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗" in s:
        return "\u26a1", "𝘈𝘱𝘱𝘳𝘰𝘷𝘦𝘥"
    if "𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗" in s:
        return "\u274c", "𝘋𝘦𝘤𝘭𝘪𝘯𝘦𝘥"
    if "𝗧𝗜𝗠𝗘𝗢𝗨𝗧" in s:
        return "\u23f1", "𝘛𝘪𝘮𝘦𝘰𝘶𝘵"
    if "𝗘𝗥𝗥𝗢𝗥" in s:
        return "⚠️", "𝘌𝘳𝘳𝘰𝘳"
    return "\u274c", ital(s)

def gate_result_caption(cmd, status, card, gateway, response, brand, issuer,
                        country, user_display, dev_link, proxy=None):
    """Build the old-style gate result caption with random premium emojis"""
    import re as _re
    # Replace hardcoded ✅ emoji with random approved emoji
    status = _re.sub(r'<tg-emoji emoji-id="5870702999180942496">✅</tg-emoji>', random_approved(), str(status))
    lines = [
        f"{random_status()} 𝗦𝘁𝗮𝘁𝘂𝘀 ➛ {status}\n"
        f"{random_card()} 𝗖𝗮𝗿𝗱 ➛ <code>{card}</code>\n"
        f"{random_gateway()} 𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➛ {gateway}\n"
        f"{random_response()} 𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ➛ <b>{response}</b>\n"
        f"{random_brand(brand)} 𝗕𝗿𝗮𝗻𝗱 ➛ <b>{brand}</b>\n"
        f"{random_issuer()} 𝗜𝘀𝘀𝘂𝗲𝗿 ➛ <b>{issuer}</b>\n"
        f"{random_country()} 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 ➛ <b>{country}</b>"
    ]
    if proxy:
        lines.append(f"{random_user()} 𝗨𝘀𝗲𝗿 ➛ {user_display}")
        lines.append(f"<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>𝗗𝗲𝘃 ➛ {dev_link} / 𝗣𝗿𝗼𝘅𝘆 ➛ {proxy}")
    else:
        lines.append(f"{random_user()} 𝗨𝘀𝗲𝗿 ➛ {user_display}")
        lines.append(f"<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji>𝗗𝗲𝘃 ➛ {dev_link}")
    return "\n".join(lines)

_DEV_LINK = "<a href='tg://openmessage?user_id=6113616017'>SpygenCVV</a>"

def mass_status_frame(title, status, checked, total, approved, charged,
                      dead, errors, time_str, session_id, apis=None):
    """Build the Double Rule mass checker status text with premium emojis"""
    s = str(status).upper()
    if "CHECKING" in s:
        status_val = "𝗖𝗛𝗘𝗖𝗞𝗜𝗡𝗚"
    elif "STOPPED" in s:
        status_val = "𝗦𝗧𝗢𝗣𝗣𝗘𝗗"
    elif "FINISHED" in s:
        status_val = "𝗖𝗢𝗠𝗣𝗟𝗘𝗧𝗘𝗗"
    else:
        status_val = sans(status)
    lines = [
        f"『 {title} 』",
        f"{_RULE}",
        f"<tg-emoji emoji-id=\"5163643969422231511\">🔄</tg-emoji> 𝗦𝘁𝗮𝘁𝘂𝘀 ➠ {status_val}",
        f"<tg-emoji emoji-id=\"5125433831528072732\">📊</tg-emoji> 𝗖𝗵𝗲𝗰𝗸𝗲𝗱 ➠ <code>{fw(checked)}/{fw(total)}</code>",
        f"<tg-emoji emoji-id=\"5870702999180942496\">✅</tg-emoji> 𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱 ➠ {fw(approved)}",
        f"{random_diamond()} 𝗖𝗵𝗮𝗿𝗴𝗲𝗱 ➠ {fw(charged)}",
        f"<tg-emoji emoji-id=\"4956612582816351459\">❌</tg-emoji> 𝗗𝗲𝗮𝗱 ➠ {fw(dead)}",
        f"<tg-emoji emoji-id=\"5213205860498549992\">⚠️</tg-emoji> 𝗘𝗿𝗿𝗼𝗿𝘀 ➠ {fw(errors)}",
        f"<tg-emoji emoji-id=\"5382194935057372936\">⏱</tg-emoji> 𝗧𝗶𝗺𝗲 ➠ {fw(time_str)}",
        f"{_RULE}",
    ]
    if apis is not None:
        lines.append(f"🔌 𝗔𝗣𝗜𝘀 ➠ {fw(apis)}")
    lines.append(f"<tg-emoji emoji-id=\"5888781182249738113\">🆔</tg-emoji> 𝗦𝗲𝘀𝘀𝗶𝗼𝗻 ➠ <code>{session_id}</code>")
    lines.append(f"<tg-emoji emoji-id=\"6298678524379137990\">🌚</tg-emoji> 𝗗𝗲𝘃 ➠ {_DEV_LINK}")
    return "\n".join(lines)

import os, time, json, requests, urllib3
from datetime import datetime, timedelta, timezone
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]          # Лолка: только RU-сегмент
ROLE_MENTION = os.environ.get("ROLE_MENTION", "")

MAX_BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "")

CHECK_INTERVAL = 30
MSK = timezone(timedelta(hours=3))

# ===== НОВОЕ: настройки меню =====
ADMIN_USER_ID = "46656348"          # ваш user_id из пробы
USER_CHAT = {}   # запоминаем chat_id тех, кто писал боту
MAX_API = "https://platform-api2.max.ru"

# Тексты меню — ЗАМЕНИТЕ НА СВОИ, это заглушки:
SUPPORT_TEXT = "🧑‍🔧 Поддержка проекта: напишите админу в личку — тут вставьте свой контакт."
STREAMS_TEXT = "📺 Стримы: тут вставьте ссылку на ваш Twitch/YouTube."
TICKET_NOTICE = "🛠 Напишите суть тикета одним сообщением — я перешлю его в Лолку."

MAX_HEADERS = {
    "Authorization": MAX_BOT_TOKEN,
    "Content-Type": "application/json",
}

CHANNEL_LINKS = {
    "RU":  "[RU](https://max.ru/channel_EmissionRU)",
    "EU":  "[EU](https://max.ru/channel_EmissionEU)",
    "NA":  "[NA](https://max.ru/channel_EmissionNA)",
    "SEA": "[SEA](https://max.ru/channel_EmissionSEA)",
}

# Сегменты: какой MAX-чат слушает какую зону, флажок «слать ли в Лолку»
REGIONS = [
    {"code": "RU",  "max_chat": os.environ.get("MAX_CHAT_ID", ""),     "lolka": True},
    {"code": "EU",  "max_chat": os.environ.get("MAX_CHAT_ID_EU", ""),  "lolka": False},
    {"code": "NA",  "max_chat": os.environ.get("MAX_CHAT_ID_NA", ""),  "lolka": False},
    {"code": "SEA", "max_chat": os.environ.get("MAX_CHAT_ID_CEA", ""), "lolka": False},
]

# ===== НОВОЕ: единый запрос к MAX с запасным вариантом по SSL =====
def max_request(method, path, **kwargs):
    url = f"{MAX_API}{path}"
    try:
        return requests.request(method, url, headers=MAX_HEADERS, timeout=20, **kwargs)
    except requests.exceptions.SSLError:
        # сервер MAX отдаёт неполную цепочку сертификата — как в пробе с curl -k
        return requests.request(method, url, headers=MAX_HEADERS, timeout=20,
                                verify=False, **kwargs)

def send_to_lolka(text):
    r = requests.post(WEBHOOK_URL, json={"content": text})
    print("Лолка:", r.status_code, "-", text[:60])

def send_to_max(chat_id, text):
    if not MAX_BOT_TOKEN or not chat_id:
        return
    try:
        r = max_request("POST", "/messages", params={"chat_id": chat_id},
                        json={"text": text, "format": "markdown"})
        print(f"MAX({chat_id}):", r.status_code, "-", text[:60])
        if r.status_code != 200:
            print("MAX ответ:", r.text[:200])
    except Exception as e:
        print("MAX ошибка:", e)

# ===== НОВОЕ: меню с кнопками =====
def send_menu(chat_id):
    r = max_request("POST", "/messages", params={"chat_id": chat_id}, json={
        "text": "Главное меню — выберите кнопку:",
        "format": "markdown",
        "attachments": [{
            "type": "inline_keyboard",
            "payload": {"buttons": [[
                {"type": "callback", "text": "🛠 Отправить тикет", "payload": "ticket"},
                {"type": "callback", "text": "🧑‍🔧 Поддержка проекта", "payload": "support"},
            ], [
                {"type": "callback", "text": "📺 Стримы", "payload": "streams"},
            ]]}
        }]
    })
    print("Меню:", r.status_code)

def handle_menu_action(payload, chat_id, uid):
    if payload == "ticket":
        TICKET_MODE.add(uid)
        send_to_max(chat_id, TICKET_NOTICE)
    elif payload == "support":
        send_to_max(chat_id, SUPPORT_TEXT)
    elif payload == "streams":
        send_to_max(chat_id, STREAMS_TEXT)
    else:
        send_to_max(chat_id, "Не понял кнопку, открываю меню заново")
        send_menu(chat_id)

def poll_max_updates():
    global MARKER
    if not MAX_BOT_TOKEN:
        return
    try:
        params = {"timeout": 2}
        if MARKER:
            params["marker"] = MARKER
        r = max_request("GET", "/updates", params=params)
        if r.status_code != 200:
            print("updates:", r.status_code, r.text[:150])
            return
        data = r.json()
        for u in data.get("updates", []):
            ut = u.get("update_type")
            if ut == "message_created":
                msg = u.get("message", {})
                sender = msg.get("sender") or {}
                uid = str(sender.get("user_id", ""))
                uname = sender.get("name", "")
                chat_id = (msg.get("recipient") or {}).get("chat_id")
                if uid and chat_id is not None:
                    USER_CHAT[uid] = chat_id   # запоминаем, куда ему отвечать
                text = ((msg.get("body") or {}).get("text") or "").strip()
                low = text.lower()
                if uid in TICKET_MODE and text:
                    fwd = (f"🛠 НОВЫЙ ТИКЕТ\n"
                           f"От: {uname} (id {uid})\n"
                           "\n"
                           f"{text}")
                    send_to_max(ADMIN_CHAT_ID, fwd)
                    TICKET_MODE.discard(uid)
                    send_to_max(chat_id, "✅ Тикет отправлен администрации")
                elif "тикет" in low:
                    handle_menu_action("ticket", chat_id, uid)
                elif "поддержка" in low:
                    send_to_max(chat_id, SUPPORT_TEXT)
                elif "стрим" in low:
                    send_to_max(chat_id, STREAMS_TEXT)
                elif "привет" in low or "меню" in low or text == "/start":
                    send_menu(chat_id)
            elif ut == "message_callback":
                print("CALLBACK FULL:", json.dumps(u, ensure_ascii=False)[:1200])
                cb = u.get("callback") or {}
                payload = cb.get("payload", "")
                cb_id = cb.get("callback_id", "")
                msg = cb.get("message") or {}
                uid = str(((cb.get("user") or {}).get("user_id", "")) or
                          ((msg.get("sender") or {}).get("user_id", "")))
                chat_id = (((msg.get("recipient") or {}).get("chat_id")) or
                           msg.get("chat_id") or cb.get("chat_id"))
                if chat_id is None and uid in USER_CHAT:
                    chat_id = USER_CHAT[uid]
                print(f"CALLBACK: payload={payload!r} chat_id={chat_id} uid={uid}")
                if cb_id:
                    ans = max_request("POST", "/answers",
                                      params={"callback_id": cb_id},
                                      json={"notification": "Принято"})
                    print("answers:", ans.status_code)
                if chat_id is not None:
                    handle_menu_action(payload, chat_id, uid)
                else:
                    print("Чат неизвестен — пришлите строку CALLBACK FULL целиком")
        new_marker = data.get("marker")
        if new_marker and new_marker != MARKER:
            max_request("POST", "/updates", json={"marker": new_marker})
            MARKER = new_marker
    except Exception as e:
        print("poll ошибка:", e)


def get_emission(region):
    r = requests.get(
        f"https://eapi.stalcraft.net/{region}/emission",
        headers={"Client-Id": CLIENT_ID, "Client-Secret": CLIENT_SECRET},
    )
    if r.status_code != 200:
        print(f"Ошибка API {region}:", r.status_code)
        return None
    return r.json()

def fmt_duration(start_dt, end_dt):
    mins = round((end_dt - start_dt).total_seconds() / 60)
    h, m = divmod(mins, 60)
    if h:
        return f"{h} ч {m} мин"
    return f"{m} мин"

def build_message(region, data):
    start_dt = datetime.fromisoformat(data["previousStart"].replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(data["previousEnd"].replace("Z", "+00:00"))
    dur = fmt_duration(start_dt, end_dt)

    start_msk = start_dt.astimezone(MSK).strftime("%H:%M")
    f_start = (start_dt + timedelta(hours=2)).astimezone(MSK).strftime("%H:%M")
    f_end = (start_dt + timedelta(hours=4)).astimezone(MSK).strftime("%H:%M")

    timers = " · ".join(
        r if r == region else CHANNEL_LINKS[r]
        for r in CHANNEL_LINKS
    )

    max_msg = (
        "✅ **ВЫБРОС ЗАКОНЧЕН**\n"
        "\n"
        f"**Начался:** {start_msk} МСК\n"
        f"**Длился:** {dur}\n"
        f"**Ожидается:** с {f_start} по {f_end}\n"
        "\n"
        "Зона вновь безопасна\n"
        "\n"
        f"Таймеры: {timers}"
    )

    lolka_msg = (
        f"✅ {ROLE_MENTION} ЗАКОНЧЕН\n"
        "\n"
        f"**Начался:** {start_msk} МСК\n"
        f"**Длился:** {dur}\n"
        f"**Ожидается:** с {f_start} по {f_end}\n"
        "\n"
        "Зона вновь безопасна"
    )

    return {
        "max": max_msg,
        "lolka": lolka_msg,
    }

MARKER = 0
TICKET_MODE = set()

# Старт: по каждому сегменту запоминаем свой последний конец выброса
known = {}
for reg in REGIONS:
    data = get_emission(reg["code"])
    known[reg["code"]] = data["previousEnd"] if data else None
    print(f"Старт [{reg['code']}]. Последний известный конец выброса: {known[reg['code']]}")

while True:
    for reg in REGIONS:
        code = reg["code"]
        data = get_emission(code)
        if not data:
            continue
        new_end = data.get("previousEnd")
        if new_end != known[code]:
            texts = build_message(code, data)
            if reg["lolka"]:
                send_to_lolka(texts["lolka"])
            send_to_max(reg["max_chat"], texts["max"])
            known[code] = new_end
        else:
            print(f"[{code}] Проверка {datetime.now(timezone.utc):%H:%M}: изменений нет")
    poll_max_updates()   # НОВОЕ: слушаем личку и кнопки — каждый цикл
    time.sleep(CHECK_INTERVAL)

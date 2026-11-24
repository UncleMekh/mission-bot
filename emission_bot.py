import os, time, json, requests, urllib3, threading
from datetime import datetime, timedelta, timezone
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)

# --- КОНФИГУРАЦИЯ И ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ---
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ROLE_MENTION = os.environ.get("ROLE_MENTION", "")
MAX_BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "")

CHECK_INTERVAL = 30
MSK = timezone(timedelta(hours=3))

# Безопасное получение ADMIN_CHAT_ID
raw_admin_id = os.environ.get("ADMIN_CHAT_ID", "")
if raw_admin_id and raw_admin_id.strip():
    try:
        ADMIN_CHAT_ID = int(raw_admin_id.strip())
        print(f"✅ ADMIN_CHAT_ID установлен: {ADMIN_CHAT_ID}")
    except ValueError:
        ADMIN_CHAT_ID = None
        print("⚠️ ВНИМАНИЕ: Неверный формат ADMIN_CHAT_ID! Защита от тикетов отключена.")
else:
    ADMIN_CHAT_ID = None
    print("⚠️ ВНИМАНИЕ: ADMIN_CHAT_ID не задан в переменных окружения! Защита от тикетов отключена.")

USER_CHAT = {}
MAX_API = "https://platform-api2.max.ru"

# Тексты меню
SUPPORT_TEXT = ("💰 Поддержать проект можно донатом:\n"
                "[dalink.to/m3xgamer](https://dalink.to/m3xgamer)")
STREAMS_TEXT = ("👋 Привет! Меня зовут Дядя Мэх.\n"
                "В свободное время я веду стримы — буду рад, если заглянешь и посмотришь,"
                " а если всё понравится, ещё и подпишишься 😄\n"
                "\n"
                "🌐 [Twitch — m3xgame](https://www.twitch.tv/m3xgame)\n"
                "🌐 [VK Видео — m3xgamer](https://live.vkvideo.ru/m3xgamer)")
TICKET_NOTICE = "🛠 Опишите суть обращения одним сообщением — я передам его администрации."

STATUS_ONLINE_TEXT = "🟢 Сервера в сети, зона ждёт тебя!"
STATUS_OFFLINE_TEXT = ("🔴 Сервера недоступны, подожди ещё немного!\n"
                       "— Возможно, идут техработы: по средам 08:00–14:00 МСК.")

MAX_HEADERS = {
    "Authorization": MAX_BOT_TOKEN,
    "Content-Type": "application/json",
}

STATUS_URL = "https://eapi.stalzone.com/regions"
STATUS_CACHE_FILE = "status_cache.json"
STATUS_CACHE_TTL = 180

CHANNEL_LINKS = {
    "RU":  "[RU](https://max.ru/channel_EmissionRU)",
    "EU":  "[EU](https://max.ru/channel_EmissionEU)",
    "NA":  "[NA](https://max.ru/channel_EmissionNA)",
    "SEA": "[SEA](https://max.ru/channel_EmissionSEA)",
}

REGIONS = [
    {"code": "RU",  "max_chat": os.environ.get("MAX_CHAT_ID", ""),     "lolka": True},
    {"code": "EU",  "max_chat": os.environ.get("MAX_CHAT_ID_EU", ""),  "lolka": False},
    {"code": "NA",  "max_chat": os.environ.get("MAX_CHAT_ID_NA", ""),  "lolka": False},
    {"code": "SEA", "max_chat": os.environ.get("MAX_CHAT_ID_CEA", ""), "lolka": False},
]

def max_request(method, path, **kwargs):
    url = f"{MAX_API}{path}"
    try:
        return requests.request(method, url, headers=MAX_HEADERS, timeout=20, **kwargs)
    except requests.exceptions.SSLError:
        return requests.request(method, url, headers=MAX_HEADERS, timeout=20, verify=False, **kwargs)

def send_to_lolka(text):
    if not WEBHOOK_URL:
        return
    try:
        r = requests.post(WEBHOOK_URL, json={"content": text})
        print("Лолка:", r.status_code)
    except Exception as e:
        print("Ошибка отправки в Лолку:", e)

def send_to_max(chat_id, text):
    if not MAX_BOT_TOKEN or not chat_id:
        return
    try:
        r = max_request("POST", "/messages", params={"chat_id": chat_id},
                        json={"text": text, "format": "markdown"})
        if r.status_code != 200:
            print(f"MAX ошибка ({r.status_code}): {r.text[:200]}")
        else:
            print(f"✅ Сообщение отправлено в MAX чат {chat_id}")
    except Exception as e:
        print("MAX ошибка:", e)

def get_server_status():
    try:
        with open(STATUS_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if time.time() - cache["ts"] < STATUS_CACHE_TTL:
            return cache["result"]
    except Exception:
        pass

    result = {"ok": False}
    try:
        r = requests.get(STATUS_URL, timeout=10)
        if r.status_code == 200 and r.text.strip():
            result = {"ok": True}
    except Exception:
        pass

    try:
        with open(STATUS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "result": result}, f)
    except Exception:
        pass
    return result

def send_menu(chat_id):
    if not chat_id:
        return
    payload = {
        "text": "Главное меню — выберите кнопку:",
        "format": "markdown",
        "attachments": [{
            "type": "inline_keyboard",
            "payload": {"buttons": [[
                {"type": "callback", "text": "🛠 Обращение", "payload": "ticket"},
                {"type": "callback", "text": "💰 Поддержка", "payload": "support"},
            ], [
                {"type": "callback", "text": "📺 Стримы", "payload": "streams"},
            ], [
                {"type": "callback", "text": "🖥 Состояние сервера", "payload": "status"},
            ]]}
        }]
    }
    r = max_request("POST", "/messages", params={"chat_id": chat_id}, json=payload)
    if r.status_code != 200:
        print("Ошибка отправки меню:", r.text)

def handle_menu_action(payload, chat_id, uid):
    if not chat_id:
        return
    if payload == "ticket":
        TICKET_MODE.add(uid)
        send_to_max(chat_id, TICKET_NOTICE)
    elif payload == "support":
        send_to_max(chat_id, SUPPORT_TEXT)
    elif payload == "streams":
        send_to_max(chat_id, STREAMS_TEXT)
    elif payload == "status":
        status = get_server_status()
        msg = STATUS_ONLINE_TEXT if (status and status["ok"]) else STATUS_OFFLINE_TEXT
        send_to_max(chat_id, msg)
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
            print(f"❌ Ошибка опроса обновлений: {r.status_code}")
            return
            
        data = r.json()
        updates = data.get("updates", )
        
        for u in updates:
            ut = u.get("update_type")
            
            if ut == "message_created":
                msg = u.get("message", {})
                sender = msg.get("sender") or {}
                uid = str(sender.get("user_id", ""))
                uname = sender.get("name", "")
                recipient = msg.get("recipient") or {}
                chat_id = recipient.get("chat_id")

                if not uid or chat_id is None:
                    continue

                USER_CHAT[uid] = chat_id

                # Защита: игнорируем сообщения ИЗ группы тикетов
                if ADMIN_CHAT_ID and chat_id == ADMIN_CHAT_ID:
                    continue

                text = ((msg.get("body") or {}).get("text") or "").strip()
                low = text.lower() if text else ""

                # Логика тикетов
                if uid in TICKET_MODE and text:
                    fwd = (f"📩 <b>НОВОЕ ОБРАЩЕНИЕ</b>\n\n"
                           f"👤 <b>Пользователь:</b> {uname}\n"
                           f"🆔 <b>ID:</b> <code>{uid}</code>\n\n"
                           f"💬 <b>Текст:</b>\n{text}")
    
                    # ✅ ИСПРАВЛЕНИЕ: Берем ID из переменной окружения, а не из списка регионов
                    target_chat_id = ADMIN_CHAT_ID
    
                    if target_chat_id:
                        send_to_max(target_chat_id, fwd)
                        TICKET_MODE.discard(uid)
                        send_to_max(chat_id, "✅ Обращение отправлено администрации")
                    else:
                        print("❌ ОШИБКА: ADMIN_CHAT_ID не задан! Тикет не отправлен.")
                        TICKET_MODE.discard(uid)
                        send_to_max(chat_id, "⚠️ Произошла ошибка при отправке обращения. Администрация не настроена.")
                
                elif "обращение" in low:
                    handle_menu_action("ticket", chat_id, uid)
                elif "поддержка" in low:
                    send_to_max(chat_id, SUPPORT_TEXT)
                elif "стрим" in low:
                    send_to_max(chat_id, STREAMS_TEXT)
                elif "статус" in low or "сервер" in low:
                    status = get_server_status()
                    msg = STATUS_ONLINE_TEXT if (status and status["ok"]) else STATUS_OFFLINE_TEXT
                    send_to_max(chat_id, msg)
                elif "привет" in low or "меню" in low or text == "/start":
                    send_menu(chat_id)
                elif text:
                    send_to_max(chat_id, "Не понял команду — вот меню 👇")
                    send_menu(chat_id)

            elif ut == "message_callback":
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
                
                if cb_id:
                    # Пытаемся подтвердить нажатие кнопки
                    try:
                        ans = max_request("POST", "/answers",
                                          params={"callback_id": cb_id},
                                          json={"notification": "Принято"})
                        if ans.status_code != 200:
                            print(f"Не удалось подтвердить кнопку: {ans.status_code}")
                    except Exception as e:
                        print(f"Ошибка подтверждения кнопки: {e}")
                
                if chat_id is not None:
                    handle_menu_action(payload, chat_id, uid)

        # Обновляем маркер ТОЛЬКО если он пришел в ответе
        new_marker = data.get("marker")
        if new_marker:
            MARKER = new_marker
            # ВАЖНО: Мы НЕ делаем отдельный POST запрос для обновления маркера.
            # MAX API ожидает, что мы просто сохраняем маркер и используем его в следующем GET запросе.
            # Ошибка 404 возникала именно из-за лишнего POST запроса.

    except Exception as e:
        print("poll ошибка:", e)

def get_emission(region, retries=3):
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Ошибка: не заданы CLIENT_ID или CLIENT_SECRET")
        return None
        
    for attempt in range(retries):
        try:
            r = requests.get(
                f"https://eapi.stalzone.com/{region}/emission",
                headers={"client-id": CLIENT_ID, "client-secret": CLIENT_SECRET},
                timeout=15,
            )
            if r.status_code != 200:
                print(f"Ошибка API {region}: {r.status_code}")
                return None
            return r.json()
        except Exception as e:
            print(f"[{region}] запрос не удался (попытка {attempt+1}/{retries}): {e}")
            time.sleep(10)
    return None

def fmt_duration(start_dt, end_dt):
    mins = round((end_dt - start_dt).total_seconds() / 60)
    h, m = divmod(mins, 60)
    return f"{h} ч {m} мин" if h else f"{m} мин"

def build_message(region, data):
    try:
        start_dt = datetime.fromisoformat(data["previousStart"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(data["previousEnd"].replace("Z", "+00:00"))
    except (KeyError, ValueError) as e:
        print(f"Ошибка парсинга времени для региона {region}: {e}")
        return None

    dur = fmt_duration(start_dt, end_dt)
    start_msk = start_dt.astimezone(MSK).strftime("%H:%M")
    f_start = (start_dt + timedelta(hours=2)).astimezone(MSK).strftime("%H:%M")
    f_end = (start_dt + timedelta(hours=4)).astimezone(MSK).strftime("%H:%M")

    timers = " · ".join(CHANNEL_LINKS.get(r, r) for r in CHANNEL_LINKS)

    max_msg = (
        "✅ **ВЫБРОС ЗАКОНЧЕН**\n\n"
        f"**Начался:** {start_msk} МСК\n"
        f"**Длился:** {dur}\n"
        f"**Ожидается:** с {f_start} по {f_end}\n\n"
        "Зона вновь безопасна\n\n"
        f"Таймеры: {timers}"
    )

    lolka_msg = (
        f"✅ {ROLE_MENTION} ЗАКОНЧЕН\n\n"
        f"**Начался:** {start_msk} МСК\n"
        f"**Длился:** {dur}\n"
        f"**Ожидается:** с {f_start} по {f_end}\n\n"
        "Зона вновь безопасна"
    )

    return {"max": max_msg, "lolka": lolka_msg}

def poll_loop():
    while True:
        try:
            poll_max_updates()
        except Exception as e:
            print("poll loop ошибка:", e)
        time.sleep(1)

# ===== ИНИЦИАЛИЗАЦИЯ =====
MARKER = 0
TICKET_MODE = set()

poller = threading.Thread(target=poll_loop, daemon=True)
poller.start()

known = {}
for reg in REGIONS:
    data = get_emission(reg["code"])
    known[reg["code"]] = data["previousEnd"] if data else None
    print(f"Старт [{reg['code']}]. Последний известный конец выброса: {known[reg['code']]}")

while True:
    try:
        for reg in REGIONS:
            code = reg["code"]
            data = get_emission(code)
            if not data:
                continue
            new_end = data.get("previousEnd")
            if new_end != known.get(code):
                texts = build_message(code, data)
                if texts:
                    if reg["lolka"]:
                        send_to_lolka(texts["lolka"])
                    if reg["max_chat"]:
                        send_to_max(reg["max_chat"], texts["max"])
                    known[code] = new_end
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("Ошибка цикла выбросов:", e)
        time.sleep(30)

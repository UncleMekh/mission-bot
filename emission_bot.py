import os, time, requests
from datetime import datetime, timedelta, timezone

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]          # Лолка: только RU-сегмент
ROLE_MENTION = os.environ.get("ROLE_MENTION", "")

MAX_BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "")

CHECK_INTERVAL = 30
MSK = timezone(timedelta(hours=3))

MAX_HEADERS = {
    "Authorization": MAX_BOT_TOKEN,
    "Content-Type": "application/json",
}

# Сегменты: какой MAX-чат слушает какую зону, флажок «слать ли в Лолку»
REGIONS = [
    {"code": "RU",  "max_chat": os.environ.get("MAX_CHAT_ID", ""),     "discord": True},
    {"code": "EU",  "max_chat": os.environ.get("MAX_CHAT_ID_EU", ""),  "discord": False},
    {"code": "NA",  "max_chat": os.environ.get("MAX_CHAT_ID_NA", ""),  "discord": False},
    {"code": "SEA", "max_chat": os.environ.get("MAX_CHAT_ID_CEA", ""), "discord": False},
]

def send_to_discord(text):
    r = requests.post(WEBHOOK_URL, json={"content": text})
    print("Discord:", r.status_code, "-", text[:60])

def send_to_max(chat_id, text):
    if not MAX_BOT_TOKEN or not chat_id:
        return
    try:
        r = requests.post(
            "https://platform-api2.max.ru/messages",
            params={"chat_id": chat_id},
            headers=MAX_HEADERS,
            json={"text": text},
        )
        print(f"MAX({chat_id}):", r.status_code, "-", text[:60])
        if r.status_code != 200:
            print("MAX ответ:", r.text[:200])
    except Exception as e:
        print("MAX ошибка:", e)

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

def forecast_window(start_dt):
    """Окно следующего выброса: +2…+4 часа от НАЧАЛА прошедшего."""
    start = (start_dt + timedelta(hours=2)).astimezone(MSK).strftime("%H:%M")
    stop = (start_dt + timedelta(hours=4)).astimezone(MSK).strftime("%H:%M")
    return f"⚠️ Ожидается выброс с {start} до {stop}"

def build_message(region, data):
    end_dt = datetime.fromisoformat(data["previousEnd"].replace("Z", "+00:00"))
    start_dt = datetime.fromisoformat(data["previousStart"].replace("Z", "+00:00"))
    dur = fmt_duration(start_dt, end_dt)
    end_msk = end_dt.astimezone(MSK).strftime("%H:%M")
    forecast = forecast_window(start_dt)
    return {
        "discord": (
            f"✅ {ROLE_MENTION} закончен в {end_msk} МСК\n"
            f"⏱️ Длился: {dur}\n"
            f"🏃 Зона снова проходима — можно лутать артефакты!\n"
            f"{forecast}"
        ),
        "max": (
            f"✅ Выброс закончен в {end_msk} МСК\n"
            f"⏱️ Длился: {dur}\n"
            f"🏃 Зона снова проходима — можно лутать артефакты!\n"
            f"{forecast}"
        ),
    }

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
            if reg["discord"]:
                send_to_discord(texts["discord"])
            send_to_max(reg["max_chat"], texts["max"])
            known[code] = new_end
        else:
            print(f"[{code}] Проверка {datetime.now(timezone.utc):%H:%M}: изменений нет")
    time.sleep(CHECK_INTERVAL)

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

def send_to_lolka(text):
    r = requests.post(WEBHOOK_URL, json={"content": text})
    print("Лолка:", r.status_code, "-", text[:60])

def send_to_max(chat_id, text):
    if not MAX_BOT_TOKEN or not chat_id:
        return
    try:
        r = requests.post(
            "https://platform-api2.max.ru/messages",
            params={"chat_id": chat_id},
            headers=MAX_HEADERS,
            json={"text": text, "format": "markdown"},
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
    time.sleep(CHECK_INTERVAL)

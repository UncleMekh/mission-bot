import os, time, requests
from datetime import datetime, timedelta, timezone

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
ROLE_MENTION = os.environ.get("ROLE_MENTION", "")

MAX_BOT_TOKEN = os.environ.get("MAX_BOT_TOKEN", "")
MAX_CHAT_ID = os.environ.get("MAX_CHAT_ID", "")

CHECK_INTERVAL = 30
MSK = timezone(timedelta(hours=3))

MAX_HEADERS = {
    "Authorization": MAX_BOT_TOKEN,  # токен в заголовке, без Bearer
    "Content-Type": "application/json",
}

def send_to_discord(text):
    r = requests.post(WEBHOOK_URL, json={"content": text})
    print("Discord:", r.status_code, "-", text[:60])

def detect_max_chat_id():
    """Если тест не прошёл — ищем канал по публичной ссылке и печатаем настоящий chat_id"""
    if not MAX_BOT_TOKEN:
        return
    try:
        r = requests.get(
            "https://platform-api2.max.ru/chats/EmissionRU",
            headers=MAX_HEADERS,
        )
        print("MAX поиск канала:", r.status_code)
        print("MAX ответ (ищите chat_id):", r.text[:500])
    except Exception as e:
        print("MAX поиск не удался:", e)

def send_to_max(text):
    if not MAX_BOT_TOKEN or not MAX_CHAT_ID:
        return
    try:
        r = requests.post(
            "https://platform-api2.max.ru/messages",
            params={"chat_id": MAX_CHAT_ID},
            headers=MAX_HEADERS,
            json={"text": text},
        )
        print("MAX:", r.status_code, "-", text[:60])
        if r.status_code != 200:
            print("MAX ответ:", r.text[:200])
            detect_max_chat_id()
    except Exception as e:
        print("MAX ошибка:", e)

def send_all(text):
    send_to_discord(text)
    send_to_max(text)

def get_emission():
    r = requests.get(
        "https://eapi.stalcraft.net/RU/emission",
        headers={"Client-Id": CLIENT_ID, "Client-Secret": CLIENT_SECRET},
    )
    if r.status_code != 200:
        print("Ошибка API:", r.status_code)
        return None
    return r.json()

def fmt_duration(start_dt, end_dt):
    mins = round((end_dt - start_dt).total_seconds() / 60)
    h, m = divmod(mins, 60)
    if h:
        return f"{h} ч {m} мин"
    return f"{m} мин"

data = get_emission()
known_end = data["previousEnd"] if data else None
print(f"Старт. Последний известный конец выброса: {known_end}")

if MAX_BOT_TOKEN and MAX_CHAT_ID:
    send_to_max("📡 Сигнализатор Зоны на связи — тест соединения")

while True:
    data = get_emission()
    if data:
        new_end = data.get("previousEnd")
        if new_end != known_end:
            end_dt = datetime.fromisoformat(new_end.replace("Z", "+00:00"))
            start_dt = datetime.fromisoformat(data["previousStart"].replace("Z", "+00:00"))
            dur = fmt_duration(start_dt, end_dt)
            end_msk = end_dt.astimezone(MSK).strftime("%H:%M")
            send_all(
                f"✅ {ROLE_MENTION} Выброс закончен в {end_msk} МСК\n"
                f"⏱️ Длился: {dur}\n"
                f"Зона снова проходима — можно лутать артефакты!"
            )
            known_end = new_end
        else:
            print(f"Проверка {datetime.now(timezone.utc):%H:%M}: изменений нет")
    time.sleep(CHECK_INTERVAL)

import os, time, requests
from datetime import datetime, timedelta, timezone

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
ROLE_MENTION = os.environ.get("ROLE_MENTION", "")

CHECK_INTERVAL = 30  # опрос раз в 30 секунд

def send_to_discord(text):
    r = requests.post(WEBHOOK_URL, json={"content": text})
    print("Отправка:", r.status_code, "-", text[:60])

def get_emission():
    r = requests.get(
        "https://eapi.stalcraft.net/RU/emission",
        headers={"Client-Id": CLIENT_ID, "Client-Secret": CLIENT_SECRET},
    )
    if r.status_code != 200:
        print("Ошибка API:", r.status_code)
        return None
    return r.json()

# При старте запоминаем последний известный конец выброса,
# но НЕ сообщаем — иначе при каждом запуске будет ложное оповещение
data = get_emission()
known_end = data["previousEnd"] if data else None
print(f"Старт. Последний известный конец выброса: {known_end}")

while True:
    data = get_emission()
    if data:
        new_end = data.get("previousEnd")
        if new_end != known_end:
            end_dt = datetime.fromisoformat(new_end.replace("Z", "+00:00"))
            start_dt = datetime.fromisoformat(data["previousStart"].replace("Z", "+00:00"))
            dur_min = round((end_dt - start_dt).total_seconds() / 60)
            send_to_discord(
                f"✅ **Выброс закончен** {ROLE_MENTION}\nЗона снова проходима — можно лутать артефакты!"
            )
            known_end = new_end
        else:
            print(f"Проверка {datetime.now(timezone.utc):%H:%M}: изменений нет")
    time.sleep(CHECK_INTERVAL)

import os, time, requests

VK_TOKEN = os.environ["VK_SERVICE_TOKEN"]
VK_GROUP_ID = int(os.environ["VK_GROUP_ID"])   # число без минуса
WEBHOOK_URL = os.environ["NEWS_WEBHOOK_URL"]

CHECK_INTERVAL = 300  # проверка каждые 5 минут
API_URL = "https://api.vk.com/method/"

def vk_method(name, **params):
    params["access_token"] = VK_TOKEN
    params["v"] = "5.199"
    r = requests.get(API_URL + name, params=params, timeout=15)
    data = r.json()
    if "error" in data:
        print("VK ошибка:", data["error"].get("error_msg"))
        return None
    return data["response"]

def send_to_lolka(text, photo_url=None):
    payload = {"content": text}
    if photo_url:
        payload["embeds"] = [{
            "title": "Пост ВКонтакте",
            "url": f"https://vk.com/wall-{VK_GROUP_ID}",
            "image": {"url": photo_url},
        }]
    r = requests.post(WEBHOOK_URL, json=payload)
    print("Lolka:", r.status_code, "-", text[:50])
    if r.status_code != 204:
        print("Ответ:", r.text[:200])

def get_posts():
    resp = vk_method("wall.get", owner_id=-VK_GROUP_ID, count=10)
    if not resp:
        return None
    return resp.get("items", [])

def build_text(item):
    text = item.get("text", "").strip()
    link = f"https://vk.com/wall-{VK_GROUP_ID}_{item['id']}"
    if len(text) > 1800:
        text = text[:1800] + "…"
    return f"**📰 Новость из клуба STALZONE**\n\n{text}\n\n[📰 источник новости]({link})"

# Старт: запоминаем последний пост, старое не пересылаем
items = get_posts()
known_id = 1151666
print(f"Старт. Последний известный пост ВК: {known_id}")

while True:
    items = get_posts()
    if items:
        newest = max(i["id"] for i in items)
        fresh = sorted([i for i in items if i["id"] > known_id],
                       key=lambda i: i["id"])
        for item in fresh:
            photos = [
                a["photo"]["sizes"][-1]["url"]
                for a in item.get("attachments", [])
                if a.get("type") == "photo"
            ]
            send_to_lolka(build_text(item), photos[0] if photos else None)
            time.sleep(3)  # пауза между постами
        if fresh:
            known_id = newest
            print(f"Отправлено новых постов до id {newest}")
    time.sleep(CHECK_INTERVAL)

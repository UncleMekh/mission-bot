import os, time, requests

VK_TOKEN = os.environ["VK_SERVICE_TOKEN"]
VK_GROUP_ID = int(os.environ["VK_GROUP_ID"])   # число без минуса
WEBHOOK_URL = os.environ["NEWS_WEBHOOK_URL"]

CHECK_INTERVAL = 300  # проверка каждые 5 минут
API_URL = "https://api.vk.com/method/"
EMBED_COLOR = 30719  # фирменный синий VK (#0077FF) - полоска слева у карточки

def vk_method(name, **params):
    params["access_token"] = VK_TOKEN
    params["v"] = "5.199"
    r = requests.get(API_URL + name, params=params, timeout=15)
    data = r.json()
    if "error" in data:
        print("VK ошибка:", data["error"].get("error_msg"))
        return None
    return data["response"]

def send_to_lolka(news):
    title, body = news  # заголовок и данные новости
    embed = {
        "title": title,
        "description": body["text"],
        "url": body["link"],
        "color": EMBED_COLOR,
        "footer": {"text": "Источник новости"},
    }
    if body.get("photo"):
        embed["image"] = {"url": body["photo"]}
    payload = {"embeds": [embed]}
    r = requests.post(WEBHOOK_URL, json=payload)
    print("Lolka:", r.status_code, "-", title[:50])
    if r.status_code != 204:
        print("Ответ:", r.text[:200])

def get_posts():
    resp = vk_method("wall.get", owner_id=-VK_GROUP_ID, count=10)
    if not resp:
        return None
    return resp.get("items", [])

def build_news(item):
    text = item.get("text", "").strip()
    link = f"https://vk.com/wall-{VK_GROUP_ID}_{item['id']}"
    if len(text) > 3800:
        text = text[:3800] + "…"
    photos = [
        a["photo"]["sizes"][-1]["url"]
        for a in item.get("attachments", [])
        if a.get("type") == "photo"
    ]
    return ("📰 Новость из клуба STALZONE",
            {"text": text, "link": link, "photo": photos[0] if photos else None})

# Старт: запоминаем последний пост, старое не пересылаем
items = get_posts()
known_id = 1151667
print(f"Старт. Последний известный пост ВК: {known_id}")

while True:
    items = get_posts()
    if items:
        newest = max(i["id"] for i in items)
        fresh = sorted([i for i in items if i["id"] > known_id],
                       key=lambda i: i["id"])
        for item in fresh:
            send_to_lolka(build_news(item))
            time.sleep(3)  # пауза между постами
        if fresh:
            known_id = newest
            print(f"Отправлено новых постов до id {newest}")
    time.sleep(CHECK_INTERVAL)

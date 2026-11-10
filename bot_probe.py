import os, json, requests

TOKEN = os.environ["MAX_BOT_TOKEN"]
API = "https://platform-api2.max.ru"

r = requests.get(
    f"{API}/updates",
    headers={"Authorization": TOKEN},
    params={"timeout": 5},
    timeout=30,
)
print("HTTP:", r.status_code)
data = r.json()
print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])


import os
import requests

key = os.environ.get("API_FOOTBALL_KEY")

if not key:
    raise RuntimeError("API_FOOTBALL_KEY bulunamadi")

url = "https://v3.football.api-sports.io/odds"

response = requests.get(
    url,
    headers={"x-apisports-key": key},
    params={"date": "2026-11-22", "page": 1},
    timeout=30
)

print("HTTP durum:", response.status_code)

response.raise_for_status()

data = response.json()

print("API hatalari:", data.get("errors"))
print("Toplam sonuc:", data.get("results"))
print("Sayfalama:", data.get("paging"))

items = data.get("response") or []

print("Gelen kayit:", len(items))

if items:
    first = items[0]
    print("Ornek mac ID:", first.get("fixture", {}).get("id"))
    print("Bahis sirketi sayisi:", len(first.get("bookmakers", [])))

    for bookmaker in first.get("bookmakers", [])[:2]:
        print("Bahis sirketi:", bookmaker.get("name"))
        print(
            "Piyasalar:",
            [bet.get("name") for bet in bookmaker.get("bets", [])]
        )

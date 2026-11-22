
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

API_KEY = os.environ.get("API_FOOTBALL_KEY")
URL = "https://v3.football.api-sports.io/odds"
TODAY = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")

if not API_KEY:
    raise RuntimeError("API_FOOTBALL_KEY bulunamadi")

MARKETS = {
    "Goals Over/Under": {
        "Over 2.5": "2.5 UST",
        "Over 3.5": "3.5 UST",
    },
    "Goals Over/Under First Half": {
        "Over 0.5": "IY 0.5 UST",
        "Over 1.5": "IY 1.5 UST",
    },
}

session = requests.Session()
session.headers.update({"x-apisports-key": API_KEY})

found = {}
pages_checked = 0
total_pages = 1

for page in range(1, 6):
    response = session.get(
        URL,
        params={"date": TODAY, "page": page},
        timeout=30,
    )

    print("Sayfa:", page, "HTTP:", response.status_code)
    response.raise_for_status()

    data = response.json()

    if data.get("errors"):
        print("API hatalari:", data["errors"])
        break

    paging = data.get("paging") or {}
    total_pages = paging.get("total") or 1
    pages_checked += 1

    for item in data.get("response") or []:
        fixture_id = (item.get("fixture") or {}).get("id")
        if not fixture_id:
            continue

        for bookmaker in item.get("bookmakers") or []:
            bookmaker_name = bookmaker.get("name", "Bilinmiyor")

            for bet in bookmaker.get("bets") or []:
                market_name = bet.get("name")
                targets = MARKETS.get(market_name)

                if not targets:
                    continue

                for value in bet.get("values") or []:
                    label = targets.get(value.get("value"))
                    if not label:
                        continue

                    try:
                        odd = float(value.get("odd"))
                    except (TypeError, ValueError):
                        continue

                    if odd <= 1:
                        continue

                    key = (fixture_id, label)

                    # Her mac ve piyasa icin ilk bulunan
                    # bahis sirketinin oranini kaydet.
                    if key not in found:
                        found[key] = {
                            "fixture_id": fixture_id,
                            "market": label,
                            "odd": odd,
                            "bookmaker": bookmaker_name,
                        }

    if page >= total_pages:
        break

print("\nTEST SONUCU")
print("Tarih:", TODAY)
print("Taranan sayfa:", pages_checked)
print("API toplam sayfa:", total_pages)
print("Bulunan mac/piyasa:", len(found))

for label in [
    "2.5 UST",
    "3.5 UST",
    "IY 0.5 UST",
    "IY 1.5 UST",
]:
    records = [
        item for item in found.values()
        if item["market"] == label
    ]

    print("\n", label, "- Bulunan:", len(records))

    for item in records[:5]:
        print(
            "Mac ID:", item["fixture_id"],
            "| Oran:", item["odd"],
            "| Sirket:", item["bookmaker"],
        )

print("\nNOT: Bu test acilis oranini degil,")
print("API'de su anda bulunan oranlari gosterir.")

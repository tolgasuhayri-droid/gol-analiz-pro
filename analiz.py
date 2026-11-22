
import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

API_KEY = os.getenv("API_FOOTBALL_KEY")
API_URL = "https://v3.football.api-sports.io"

if not API_KEY:
    raise RuntimeError("API_FOOTBALL_KEY bulunamadi")

headers = {"x-apisports-key": API_KEY}
today = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")

response = requests.get(
    API_URL + "/fixtures",
    headers=headers,
    params={"date": today, "timezone": "Europe/Istanbul"},
    timeout=30
)
response.raise_for_status()
data = response.json()

if data.get("errors"):
    raise RuntimeError(str(data["errors"]))

predictions = []

for match in data.get("response", []):
    fixture = match.get("fixture", {})
    teams = match.get("teams", {})
    league = match.get("league", {})

    predictions.append({
        "fixture_id": fixture.get("id"),
        "date": fixture.get("date"),
        "league": league.get("name"),
        "home": teams.get("home", {}).get("name"),
        "away": teams.get("away", {}).get("name"),
        "status": fixture.get("status", {}).get("short")
    })

with open("predictions.json", "w", encoding="utf-8") as f:
    json.dump(predictions, f, ensure_ascii=False, indent=2)

print(f"{len(predictions)} mac kaydedildi.")

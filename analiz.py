
import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
now = datetime.now(TZ)
today = now.strftime("%Y-%m-%d")

API_KEY = os.environ["API_FOOTBALL_KEY"]

url = "https://v3.football.api-sports.io/fixtures"

response = requests.get(
    url,
    headers={"x-apisports-key": API_KEY},
    params={
        "date": today,
        "timezone": "Europe/Istanbul"
    },
    timeout=30
)

response.raise_for_status()
data = response.json()

if data.get("errors"):
    raise RuntimeError(str(data["errors"]))

matches = []

for item in data.get("response", []):
    fixture = item.get("fixture", {})
    status = fixture.get("status", {}).get("short")

    if status != "NS":
        continue

    kickoff = fixture.get("date")
    if not kickoff:
        continue

    dt = datetime.fromisoformat(
        kickoff.replace("Z", "+00:00")
    ).astimezone(TZ)

    if dt <= now:
        continue

    matches.append({
        "fixture_id": fixture.get("id"),
        "kickoff": dt.isoformat(),
        "league": item.get("league", {}).get("name"),
        "home": item.get("teams", {}).get("home", {}).get("name"),
        "away": item.get("teams", {}).get("away", {}).get("name"),
        "status": "NS"
    })

matches.sort(key=lambda m: m["kickoff"])

output = {
    "updated_at": now.isoformat(),
    "matches": matches
}

with open("predictions.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"{len(matches)} baslamamis mac bulundu.")

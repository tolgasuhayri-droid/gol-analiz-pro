
import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
now = datetime.now(TZ)
today = now.strftime("%Y-%m-%d")

API_KEY = os.getenv("API_FOOTBALL_KEY")
if not API_KEY:
    raise RuntimeError("API_FOOTBALL_KEY bulunamadi")

response = requests.get(
    "https://v3.football.api-sports.io/fixtures",
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

    if status not in ("NS", "TBD"):
        continue

    kickoff = fixture.get("date")
    if not kickoff:
        continue

    kickoff_dt = datetime.fromisoformat(
        kickoff.replace("Z", "+00:00")
    ).astimezone(TZ)

    if kickoff_dt <= now:
        continue

    teams = item.get("teams", {})
    league = item.get("league", {})

    matches.append({
        "fixture_id": fixture.get("id"),
        "kickoff": kickoff_dt.isoformat(),
        "league": league.get("name"),
        "home": teams.get("home", {}).get("name"),
        "away": teams.get("away", {}).get("name"),
        "status": status
    })

matches.sort(key=lambda m: m["kickoff"])

with open("predictions.json", "w", encoding="utf-8") as f:
    json.dump(matches, f, ensure_ascii=False, indent=2)

print(f"{len(matches)} baslamamis mac kaydedildi.")


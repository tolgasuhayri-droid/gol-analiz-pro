
import os
import json
import math

def poisson_over(lam, line):
    if lam < 0:
        return 0.0
    k = int(line)
    probability_under = sum(
        math.exp(-lam) * lam**i / math.factorial(i)
        for i in range(k + 1)
    )
    return max(0.0, min(1.0, 1 - probability_under))
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
now = datetime.now(TZ)
today = now.strftime("%Y-%m-%d")

API_KEY = os.getenv("API_FOOTBALL_KEY")
if not API_KEY:
    raise RuntimeError("API_FOOTBALL_KEY bulunamadi")

URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

def api(endpoint, params):
    r = requests.get(
        URL + endpoint,
        headers=HEADERS,
        params=params,
        timeout=30
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"]))
    return data.get("response", [])


def team_stats(team_id, cache):
    if team_id in cache:
        return cache[team_id]

    games = api("/fixtures", {
        "team": team_id,
        "season": 2024,
        "status": "FT"
    })

    games = sorted(
        games,
        key=lambda g: g.get("fixture", {}).get("date", ""),
        reverse=True
    )[:10]

    scored = []
    conceded = []
    first_half = []

    for game in games:
        goals = game.get("goals", {})
        teams = game.get("teams", {})
        score = game.get("score", {})

        home = teams.get("home", {}).get("id") == team_id

        gf = goals.get("home") if home else goals.get("away")
        ga = goals.get("away") if home else goals.get("home")

        if gf is None or ga is None:
            continue

        scored.append(gf)
        conceded.append(ga)

        ht = score.get("halftime") or {}
        h1 = ht.get("home")
        h2 = ht.get("away")

        if h1 is not None and h2 is not None:
            first_half.append(h1 + h2)

    if len(scored) < 5:
        cache[team_id] = None
        return None

    result = {
        "scored": sum(scored) / len(scored),
        "conceded": sum(conceded) / len(conceded),
        "ht_goals": (
            sum(first_half) / len(first_half)
            if first_half else None
        ),
        "n": len(scored)
    }

    cache[team_id] = result
    return result

fixtures = api("/fixtures", {
    "date": today,
    "timezone": "Europe/Istanbul"
})

upcoming = []

for item in fixtures:
    fixture = item.get("fixture", {})
    if fixture.get("status", {}).get("short") != "NS":
        continue

    kickoff = fixture.get("date")
    if not kickoff:
        continue

    dt = datetime.fromisoformat(
        kickoff.replace("Z", "+00:00")
    ).astimezone(TZ)

    if dt <= now:
        continue

    upcoming.append((dt, item))

upcoming.sort(key=lambda x: x[0])

cache = {}
matches = []

for dt, item in upcoming[:10]:
    teams = item["teams"]
    home = teams["home"]
    away = teams["away"]

    hs = team_stats(home["id"], cache)
    aws = team_stats(away["id"], cache)

    if not hs or not aws:
        continue

    home_goals = (hs["scored"] + aws["conceded"]) / 2
    away_goals = (aws["scored"] + hs["conceded"]) / 2

    lam = home_goals + away_goals

    ht_values = [
        v for v in [hs["ht_goals"], aws["ht_goals"]]
        if v is not None
    ]

    ht_lam = (
        sum(ht_values) / len(ht_values)
        if ht_values else None
    )

    matches.append({
        "fixture_id": item["fixture"]["id"],
        "kickoff": dt.isoformat(),
        "league": item["league"]["name"],
        "home": home["name"],
        "away": away["name"],
        "status": "NS",
        "lambda_total": round(lam, 2),
        "home_n": hs["n"],
        "away_n": aws["n"],
        "over25": poisson_over(lam, 2.5),
        "over35": poisson_over(lam, 3.5),
        "ht_over05": (
            poisson_over(ht_lam, 0.5)
            if ht_lam is not None else None
        ),
        "ht_over15": (
            poisson_over(ht_lam, 1.5)
            if ht_lam is not None else None
        )
    })

output = {
    "updated_at": now.isoformat(),
    "matches": matches
}

with open("predictions.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"{len(matches)} mac analiz edildi.")




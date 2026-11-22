import json
import math
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo('Europe/Istanbul')
NOW = datetime.now(TZ)
TODAY = NOW.strftime('%Y-%m-%d')
API_KEY = os.environ.get('API_FOOTBALL_KEY', '')
BASE = 'https://v3.football.api-sports.io'
OUTPUT = Path('predictions.json')
CACHE_FILE = Path('team_cache.json')
MAX_MATCHES = 30
MAX_ODDS_PAGES = 20
MAX_REQUESTS = 100
PRIORITY = {39: 1, 140: 2, 135: 3, 78: 4, 61: 5, 203: 6, 2: 7, 3: 8, 88: 9, 94: 10, 144: 11, 179: 12, 253: 13, 262: 14, 71: 15, 128: 16, 204: 17}
MARKETS = {
    'Goals Over/Under': {'Over 2.5': 'over25', 'Over 3.5': 'over35'},
    'Goals Over/Under First Half': {'Over 0.5': 'ht_over05', 'Over 1.5': 'ht_over15'},
}
SESSION = requests.Session()
SESSION.headers.update({'x-apisports-key': API_KEY})
requests_used = 0


def api(endpoint, params):
    global requests_used
    if not API_KEY:
        raise RuntimeError('API_FOOTBALL_KEY missing: set GitHub Actions secret.')
    if requests_used >= MAX_REQUESTS:
        print('Local API request budget reached.')
        return None
    requests_used += 1
    try:
        response = SESSION.get(BASE + endpoint, params=params, timeout=30)
        if response.status_code == 429:
            print('API rate limit reached.')
            return None
        response.raise_for_status()
        payload = response.json()
        if payload.get('errors'):
            print('API error:', payload['errors'])
            return None
        return payload
    except (requests.RequestException, ValueError) as exc:
        print('API request failed:', exc)
        return None


def load_cache():
    try:
        data = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')


def poisson_over(lam, line):
    if lam is None or lam < 0:
        return None
    k = math.floor(line)
    under = sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))
    return round(max(0.0, min(1.0, 1 - under)), 4)


def team_stats(team_id, league_id, season, cache):
    key = f'{team_id}:{league_id}:{season}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    payload = api('/fixtures', {'team': team_id, 'league': league_id, 'season': season, 'status': 'FT'})
    if payload is None:
        return None
    games = sorted(payload.get('response') or [], key=lambda x: (x.get('fixture') or {}).get('date', ''), reverse=True)[:10]
    scored, conceded, halves = [], [], []
    for game in games:
        teams = game.get('teams') or {}
        goals = game.get('goals') or {}
        home = (teams.get('home') or {}).get('id') == team_id
        gf = goals.get('home' if home else 'away')
        ga = goals.get('away' if home else 'home')
        if not isinstance(gf, (int, float)) or not isinstance(ga, (int, float)):
            continue
        scored.append(gf)
        conceded.append(ga)
        half = (game.get('score') or {}).get('halftime') or {}
        h, a = half.get('home'), half.get('away')
        if isinstance(h, (int, float)) and isinstance(a, (int, float)):

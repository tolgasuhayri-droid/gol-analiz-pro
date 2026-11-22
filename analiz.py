import json
import math
import os
import time
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
MAX_REQUESTS = 65  # Leave room under typical free daily quotas; not a guarantee.
PRIORITY = {39: 1, 140: 2, 135: 3, 78: 4, 61: 5, 203: 6, 2: 7, 3: 8, 88: 9, 94: 10, 144: 11, 179: 12, 253: 13, 262: 14, 71: 15, 128: 16, 204: 17}
SESSION = requests.Session()
SESSION.headers.update({'x-apisports-key': API_KEY})
requests_used = 0


def api(endpoint, params):
    global requests_used
    if not API_KEY:
        raise RuntimeError('API_FOOTBALL_KEY is missing. Configure GitHub Actions secret.')
    if requests_used >= MAX_REQUESTS:
        print('Local API request budget reached.')
        return None
    requests_used += 1
    try:
        response = SESSION.get(BASE + endpoint, params=params, timeout=30)
        if response.status_code == 429:
            print('API rate/quota limit reached.')
            return None
        response.raise_for_status()
        payload = response.json()
        if payload.get('errors'):
            print('API error:', payload['errors'])
            return None
        return payload.get('response', [])
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
    # One request per team/league/season, without restricted `last` parameter.
    games = api('/fixtures', {'team': team_id, 'league': league_id, 'season': season, 'status': 'FT'})
    if games is None:
        return None
    games = sorted(games, key=lambda x: x.get('fixture', {}).get('date', ''), reverse=True)[:10]
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
            halves.append(h + a)
    if len(scored) < 5:
        return None
    result = {'scored': sum(scored) / len(scored), 'conceded': sum(conceded) / len(conceded), 'ht_goals': sum(halves) / len(halves) if halves else None, 'n': len(scored)}
    cache[key] = result
    return result


def main():
    fixtures = api('/fixtures', {'date': TODAY, 'timezone': 'Europe/Istanbul'})
    if fixtures is None:
        raise RuntimeError('Fixture list unavailable; existing predictions.json preserved.')
    upcoming = []
    for item in fixtures:
        fixture = item.get('fixture') or {}
        if (fixture.get('status') or {}).get('short') != 'NS':
            continue
        try:
            kickoff = datetime.fromisoformat(fixture['date'].replace('Z', '+00:00')).astimezone(TZ)
        except (KeyError, TypeError, ValueError):
            continue
        if kickoff <= NOW:
            continue
        league = item.get('league') or {}
        upcoming.append((PRIORITY.get(league.get('id'), 999), kickoff, item))
    upcoming.sort(key=lambda x: (x[0], x[1]))
    chosen = upcoming[:MAX_MATCHES]
    cache = load_cache()
    matches = []
    for _, kickoff, item in chosen:
        fixture, teams, league = item['fixture'], item['teams'], item['league']
        home, away = teams['home'], teams['away']
        record = {'fixture_id': fixture['id'], 'kickoff': kickoff.isoformat(), 'league': league.get('name'), 'home': home.get('name'), 'away': away.get('name'), 'status': 'NS', 'over25': None, 'over35': None, 'ht_over05': None, 'ht_over15': None, 'analysis_status': 'Veri yetersiz'}
        season = league.get('season')
        league_id = league.get('id')
        if season is not None and league_id is not None:
            hs = team_stats(home['id'], league_id, season, cache)
            aws = team_stats(away['id'], league_id, season, cache)
            if hs and aws:
                lam = (hs['scored'] + aws['conceded'] + aws['scored'] + hs['conceded']) / 2
                ht_values = [v for v in (hs['ht_goals'], aws['ht_goals']) if v is not None]
                ht_lam = sum(ht_values) / len(ht_values) if ht_values else None
                record.update({'lambda_total': round(lam, 2), 'home_n': hs['n'], 'away_n': aws['n'], 'over25': poisson_over(lam, 2.5), 'over35': poisson_over(lam, 3.5), 'ht_over05': poisson_over(ht_lam, 0.5), 'ht_over15': poisson_over(ht_lam, 1.5), 'analysis_status': 'Hesaplandı'})
        matches.append(record)
    save_cache(cache)
    output = {'updated_at': NOW.isoformat(), 'matches': matches}
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(matches)} matches selected; {sum(m["analysis_status"] == "Hesaplandı" for m in matches)} analyzed; {requests_used} API requests.')
    print('Note: cache persistence requires committing team_cache.json in GitHub Actions.')


if __name__ == '__main__':
    main()

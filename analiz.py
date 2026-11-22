import os
import json
import math
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Istanbul')
NOW = datetime.now(TZ)
TODAY = NOW.strftime('%Y-%m-%d')
API_KEY = os.environ['API_FOOTBALL_KEY']
BASE = 'https://v3.football.api-sports.io'
SESSION = requests.Session()
SESSION.headers.update({'x-apisports-key': API_KEY})
MAX_REQUESTS = 80
requests_used = 0

# Priority league IDs: major European leagues, UEFA competitions, Turkish Super Lig.
PRIORITY = {39: 1, 140: 2, 135: 3, 78: 4, 61: 5, 203: 6, 2: 7, 3: 8, 88: 9, 94: 10, 144: 11, 179: 12}
MAX_ANALYZE = 25


def api(endpoint, params):
    global requests_used
    if requests_used >= MAX_REQUESTS:
        return None
    requests_used += 1
    try:
        response = SESSION.get(BASE + endpoint, params=params, timeout=30)
        if response.status_code == 429:
            print('API request limit reached; retaining matches without predictions.')
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


def poisson_over(lam, threshold):
    if lam is None or lam < 0:
        return None
    k = math.floor(threshold)
    under = sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))
    return round(100 * max(0.0, min(1.0, 1 - under)), 1)


def team_stats(team_id, cache):
    if team_id in cache:
        return cache[team_id]
    # Last completed fixtures without restricted season parameter.
    games = api('/fixtures', {'team': team_id, 'last': 10})
    if games is None:
        cache[team_id] = None
        return None
    scored, conceded, half = [], [], []
    for game in games:
        if game.get('fixture', {}).get('status', {}).get('short') not in ('FT', 'AET', 'PEN'):
            continue
        teams = game.get('teams') or {}
        goals = game.get('goals') or {}
        home = (teams.get('home') or {}).get('id') == team_id
        gf = goals.get('home') if home else goals.get('away')
        ga = goals.get('away') if home else goals.get('home')
        if not isinstance(gf, int) or not isinstance(ga, int):
            continue
        scored.append(gf)
        conceded.append(ga)
        ht = (game.get('score') or {}).get('halftime') or {}
        if isinstance(ht.get('home'), int) and isinstance(ht.get('away'), int):
            half.append(ht['home'] + ht['away'])
    if len(scored) < 5 or len(half) < 5:
        cache[team_id] = None
        return None
    result = {
        'scored': sum(scored) / len(scored),
        'conceded': sum(conceded) / len(conceded),
        'half': sum(half) / len(half),
        'n': len(scored)
    }
    cache[team_id] = result
    return result


fixtures = api('/fixtures', {'date': TODAY, 'timezone': 'Europe/Istanbul'})
if fixtures is None:
    raise RuntimeError('Could not fetch daily fixtures; existing predictions.json left unchanged.')

matches = []
for item in fixtures:
    fixture = item.get('fixture') or {}
    if (fixture.get('status') or {}).get('short') != 'NS':
        continue
    kickoff = fixture.get('date')
    if not kickoff:
        continue
    try:
        dt = datetime.fromisoformat(kickoff.replace('Z', '+00:00')).astimezone(TZ)
    except ValueError:
        continue
    if dt <= NOW:
        continue
    league = item.get('league') or {}
    teams = item.get('teams') or {}
    home = teams.get('home') or {}
    away = teams.get('away') or {}
    matches.append({
        'fixture_id': fixture.get('id'),
        'kickoff': dt.isoformat(),
        'league': league.get('name'),
        'league_id': league.get('id'),
        'home': home.get('name'),
        'away': away.get('name'),
        'home_id': home.get('id'),
        'away_id': away.get('id'),
        'status': 'NS',
        'over25': None, 'over35': None,
        'ht_over05': None, 'ht_over15': None,
        'lambda_total': None, 'home_n': None, 'away_n': None
    })

matches.sort(key=lambda m: m['kickoff'])
selected = sorted(
    (m for m in matches if m['league_id'] in PRIORITY),
    key=lambda m: (PRIORITY[m['league_id']], m['kickoff'])
)[:MAX_ANALYZE]
cache = {}
analyzed = 0
for match in selected:
    if match['home_id'] is None or match['away_id'] is None:
        continue
    hs = team_stats(match['home_id'], cache)
    aws = team_stats(match['away_id'], cache)
    if not hs or not aws:
        continue
    home_lambda = (hs['scored'] + aws['conceded']) / 2
    away_lambda = (aws['scored'] + hs['conceded']) / 2
    total_lambda = home_lambda + away_lambda
    half_lambda = (hs['half'] + aws['half']) / 2
    match.update({
        'lambda_total': round(total_lambda, 2),
        'home_n': hs['n'], 'away_n': aws['n'],
        'over25': poisson_over(total_lambda, 2.5),
        'over35': poisson_over(total_lambda, 3.5),
        'ht_over05': poisson_over(half_lambda, 0.5),
        'ht_over15': poisson_over(half_lambda, 1.5)
    })
    analyzed += 1

for match in matches:
    match.pop('home_id', None)
    match.pop('away_id', None)

output = {'updated_at': NOW.isoformat(), 'matches': matches,
          'analysis_count': analyzed, 'requests_used': requests_used}
with open('predictions.json', 'w', encoding='utf-8') as file:
    json.dump(output, file, ensure_ascii=False, indent=2)
print(f'{len(matches)} upcoming fixtures; {analyzed} analyzed; {requests_used} API calls.')

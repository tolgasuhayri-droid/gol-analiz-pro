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
OUTPUT = Path('predictions_oranli.json')
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
            halves.append(h + a)
    if len(scored) < 5:
        return None
    result = {
        'scored': sum(scored) / len(scored),
        'conceded': sum(conceded) / len(conceded),
        'ht_goals': sum(halves) / len(halves) if halves else None,
        'n': len(scored),
    }
    cache[key] = result
    return result


def get_odds():
    # Save the first available bookmaker quote for each fixture/market.
    # This is a current snapshot, NOT an opening quote.
    quotes = {}
    total_pages = 1
    pages_checked = 0
    for page in range(1, MAX_ODDS_PAGES + 1):
        payload = api('/odds', {'date': TODAY, 'page': page})
        if payload is None:
            break
        pages_checked += 1
        total_pages = (payload.get('paging') or {}).get('total') or 1
        for item in payload.get('response') or []:
            fixture_id = (item.get('fixture') or {}).get('id')
            if fixture_id is None:
                continue
            for bookmaker in item.get('bookmakers') or []:
                bookmaker_name = bookmaker.get('name') or 'Unknown'
                for bet in bookmaker.get('bets') or []:
                    targets = MARKETS.get(bet.get('name'))
                    if not targets:
                        continue
                    for value in bet.get('values') or []:
                        market = targets.get(value.get('value'))
                        if not market or (fixture_id, market) in quotes:
                            continue
                        try:
                            odd = float(value.get('odd'))
                        except (TypeError, ValueError):
                            continue
                        if not math.isfinite(odd) or odd <= 1:
                            continue
                        quotes[(fixture_id, market)] = {'odd': odd, 'bookmaker': bookmaker_name}
        if page >= total_pages:
            break
    print(f'Odds: {pages_checked}/{total_pages} pages checked; {len(quotes)} fixture/market quotes.')
    return quotes


def main():
    fixture_payload = api('/fixtures', {'date': TODAY, 'timezone': 'Europe/Istanbul'})
    if fixture_payload is None:
        raise RuntimeError('Fixtures unavailable; previous predictions.json preserved.')
    upcoming = []
    for item in fixture_payload.get('response') or []:
        fixture = item.get('fixture') or {}
        if (fixture.get('status') or {}).get('short') != 'NS':
            continue
        try:
            kickoff = datetime.fromisoformat(fixture['date'].replace('Z', '+00:00')).astimezone(TZ)
        except (KeyError, AttributeError, TypeError, ValueError):
            continue
        if kickoff <= NOW:
            continue
        league = item.get('league') or {}
        upcoming.append((PRIORITY.get(league.get('id'), 999), kickoff, item))

    quotes = get_odds()
    # Prioritize fixtures with a larger number of available target markets;
    # league preference is a tie-breaker, not a probability signal.
    upcoming.sort(key=lambda entry: (
        -sum((entry[2]['fixture']['id'], market) in quotes for market in ('over25', 'over35', 'ht_over05', 'ht_over15')),
        entry[0], entry[1]
    ))
    with_odds = [entry for entry in upcoming if any((entry[2]['fixture']['id'], market) in quotes for market in ('over25', 'over35', 'ht_over05', 'ht_over15'))]
    chosen = with_odds[:MAX_MATCHES]
    cache = load_cache()
    matches = []
    for _, kickoff, item in chosen:
        fixture, teams, league = item['fixture'], item['teams'], item['league']
        home, away = teams['home'], teams['away']
        fixture_id = fixture['id']
        record = {
            'fixture_id': fixture_id, 'kickoff': kickoff.isoformat(),
            'league': league.get('name'), 'home': home.get('name'), 'away': away.get('name'),
            'status': 'NS', 'over25': None, 'over35': None,
            'ht_over05': None, 'ht_over15': None,
            'analysis_status': 'Veri yetersiz', 'odds': {}, 'best_market': None,
            'best_ev': None,
        }
        season, league_id = league.get('season'), league.get('id')
        if season is not None and league_id is not None:
            hs = team_stats(home['id'], league_id, season, cache)
            aws = team_stats(away['id'], league_id, season, cache)
            if hs and aws:
                lam = (hs['scored'] + aws['conceded'] + aws['scored'] + hs['conceded']) / 2
                ht_values = [v for v in (hs['ht_goals'], aws['ht_goals']) if v is not None]
                ht_lam = sum(ht_values) / len(ht_values) if ht_values else None
                record.update({
                    'lambda_total': round(lam, 2), 'home_n': hs['n'], 'away_n': aws['n'],
                    'over25': poisson_over(lam, 2.5), 'over35': poisson_over(lam, 3.5),
                    'ht_over05': poisson_over(ht_lam, 0.5), 'ht_over15': poisson_over(ht_lam, 1.5),
                    'analysis_status': 'Hesaplandı',
                })
        for market in ('over25', 'over35', 'ht_over05', 'ht_over15'):
            quote = quotes.get((fixture_id, market))
            if not quote:
                continue
            odd = quote['odd']
            probability = record.get(market)
            detail = {
                'odd': odd, 'bookmaker': quote['bookmaker'],
                'implied_probability': round(1 / odd, 4),
                'ev': round(probability * odd - 1, 4) if probability is not None else None,
            }
            record['odds'][market] = detail
        valid = [(market, detail['ev']) for market, detail in record['odds'].items() if detail['ev'] is not None]
        if valid:
            record['best_market'], record['best_ev'] = max(valid, key=lambda x: x[1])
        matches.append(record)

    # Highest estimated expected value first; insufficient-data matches last.
    matches.sort(key=lambda m: (m['best_ev'] is None, -(m['best_ev'] if m['best_ev'] is not None else -999)))
    save_cache(cache)
    output = {'updated_at': NOW.isoformat(), 'odds_snapshot_at': NOW.isoformat(), 'matches': matches}
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    analyzed = sum(m['analysis_status'] == 'Hesaplandı' for m in matches)
    print(f'{len(matches)} matches with odds selected; {analyzed} analyzed; {requests_used} API requests.')
    print('IMPORTANT: EV is model-based and uncalibrated; positive EV does not guarantee profit.')
    print('Odds are current snapshots, not confirmed opening prices.')


if __name__ == '__main__':
    main()

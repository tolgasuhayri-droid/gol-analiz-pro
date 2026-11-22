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

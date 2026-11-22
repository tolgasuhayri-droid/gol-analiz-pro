"""Offline smoke tests. Run: python -m unittest test_analiz.py -v"""
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import analiz


class AnalizTests(unittest.TestCase):
    def test_poisson_probability(self):
        self.assertAlmostEqual(analiz.poisson_over(3, 2.5), 0.5768, places=4)
        self.assertIsNone(analiz.poisson_over(None, 2.5))

    def test_end_to_end_without_api_calls(self):
        kickoff = (analiz.NOW + timedelta(hours=2)).isoformat()
        fixture = {
            'fixture': {'id': 123, 'date': kickoff, 'status': {'short': 'NS'}},
            'league': {'id': 39, 'name': 'Test League', 'season': 2026},
            'teams': {'home': {'id': 10, 'name': 'Home'}, 'away': {'id': 20, 'name': 'Away'}},
        }

        def fake_api(endpoint, params):
            if params.get('date'):
                return [fixture]
            team = params['team']
            games = []
            for i in range(6):
                games.append({
                    'fixture': {'date': f'2026-09-{i+10:02d}'},
                    'teams': {'home': {'id': team}, 'away': {'id': 1000 + i}},
                    'goals': {'home': 2, 'away': 1},
                    'score': {'halftime': {'home': 1, 'away': 0}},
                })
            return games

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(analiz, 'api', side_effect=fake_api), \
                 patch.object(analiz, 'OUTPUT', Path(directory) / 'predictions.json'), \
                 patch.object(analiz, 'CACHE_FILE', Path(directory) / 'team_cache.json'):
                analiz.main()
                output = json.loads(analiz.OUTPUT.read_text())
                self.assertEqual(len(output['matches']), 1)
                match = output['matches'][0]
                self.assertEqual(match['analysis_status'], 'Hesaplandı')
                for field in ('over25', 'over35', 'ht_over05', 'ht_over15'):
                    self.assertIsInstance(match[field], float)
                    self.assertTrue(0 <= match[field] <= 1)
                self.assertTrue(analiz.CACHE_FILE.exists())


if __name__ == '__main__':
    unittest.main()

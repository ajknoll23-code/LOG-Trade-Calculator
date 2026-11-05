"""No-internet integration tests with 12 synthetic teams / six games."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[2] / 'scripts/newsletters/league_newsletter.py'
spec = spec_from_file_location('league_newsletter', MODULE)
newsletter = module_from_spec(spec)
spec.loader.exec_module(newsletter)


def make_api(final=False, missing=False):
    users = [dict(user_id=str(1000+i), display_name=f'Manager {i}', metadata={'team_name': f'Team {i}'}) for i in range(1, 13)]
    rosters = [dict(roster_id=i, owner_id=str(1000+i), players=[str(i*100+j) for j in range(17)], settings={'wins':8,'losses':8}) for i in range(1,13)]
    def game(week):
        rows=[]
        for i in range(1,13):
            pts=round(90 + i * 3 + week,2) if (week<9 or final) else 0
            rows.append(dict(roster_id=i,matchup_id=(i+1)//2,points=pts,
                             starters=[str(i*100)],players_points={str(i*100):float(pts)/3}))
        return rows[:-1] if missing and week==9 else rows
    def api(path):
        if path == 'state/nfl': return {'week': 10 if final else 9, 'season': '2026'}
        if path == 'league/league26': return {'season':'2026','name':'League of Ordinary Gentlemen','settings':{'playoff_week_start':15}}
        if path == 'league/league26/users': return users
        if path == 'league/league26/rosters': return rosters
        if path.startswith('league/league26/matchups/'):
            return game(int(path.split('/')[-1]))
        if path.startswith('league/league26/transactions/'):
            return []
        raise AssertionError(f'Unexpected request {path}')
    return api


class NewsletterTests(unittest.TestCase):
    def setUp(self):
        self.orig_read = newsletter.read_repo_json
        newsletter.read_repo_json = lambda rel, default=None: {'data/trade_history.json': {'seasons': []}, 'data/free_agent_utility_v1.json':{'players':[]}}.get(rel, default)
    def tearDown(self):
        newsletter.read_repo_json = self.orig_read

    def test_pre_edition_all_six(self):
        p = newsletter.build_payload(make_api(), {'league_id':'league26','season':'2026'}, 'pre')
        self.assertEqual(9,p['week'])
        self.assertEqual(6,len(p['games']))
        self.assertIsNotNone(p['games'][0]['prob_a'])
        html = newsletter.render_html(p)
        self.assertEqual(6,html.count("class='game'"))
        self.assertIn('THE WEEKLY WAR ROOM',html)
        self.assertIn('Historical series:',html)
        self.assertTrue(newsletter.render_text(p).startswith('League of Ordinary Gentlemen'))

    def test_post_edition_median(self):
        p = newsletter.build_payload(make_api(final=True), {'league_id':'league26','season':'2026'}, 'post')
        self.assertEqual(9,p['week'])
        self.assertEqual(6,len(p['games']))
        self.assertIsNotNone(p['median'])
        self.assertEqual('L',p['games'][0]['median_a'])
        self.assertIn('THE AFTERMATH', newsletter.render_html(p))

    def test_incomplete_week_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'six complete'):
            newsletter.build_payload(make_api(missing=True), {'league_id':'league26','season':'2026'}, 'pre')

    def test_unsupported_season_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'NFL season differs'):
            newsletter.build_payload(make_api(), {'league_id':'league26','season':'2025'}, 'pre')

if __name__ == '__main__':
    unittest.main()

# Additional release validation (appended after the original unittest.main guard;
# discovery imports this module, so these tests still run in CI).
class ReleaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.orig_read = newsletter.read_repo_json
        newsletter.read_repo_json = lambda rel, default=None: {
            'data/trade_history.json': {'seasons': []},
            'data/free_agent_utility_v1.json': {'players': []},
        }.get(rel, default)

    def tearDown(self):
        newsletter.read_repo_json = self.orig_read

    def test_post_current_week_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'has not advanced'):
            newsletter.build_payload(make_api(), {'league_id':'league26','season':'2026'}, 'post', 9)

    def test_duplicate_roster_does_not_count_as_two_teams(self):
        original = make_api()
        def api(path):
            result = original(path)
            if path == 'league/league26/matchups/9':
                result[-1] = {**result[-1], 'roster_id': 1}
            return result
        with self.assertRaisesRegex(RuntimeError, 'unique teams'):
            newsletter.build_payload(api, {'league_id':'league26','season':'2026'}, 'pre', 9)

    def test_stale_free_agent_utility_hidden(self):
        original = newsletter.read_repo_json
        newsletter.read_repo_json = lambda rel, default=None: {
            'data/free_agent_utility_v1.json': {'source': {'free_agents_synced_at': 10, 'free_agents_count': 1,'league_id':'league26'},'players':[{'player_id':'101','pos':'RB','priority_rank':1}]},
            'data/free_agents.json': {'synced_at':11,'count':1,'league_id':'league26'},
        }.get(rel, default)
        try:
            self.assertEqual(newsletter.best_free_agents([], {'101': {'name': 'Example Player', 'status':'Active'}}), [])
        finally:
            newsletter.read_repo_json = original

    def test_smtp_requires_secrets(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'Email blocked'):
                newsletter.send_email('Test', '<p>Test</p>', 'Test')

    def test_nonfinite_matchup_score_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'invalid matchup score'):
            newsletter.score({'points':float('nan')})


class TransactionDisplayQualityTests(unittest.TestCase):
    def test_drop_only_transaction_has_grammatical_label(self):
        item = {"status":"complete", "type":"free_agent", "roster_ids":[1],
                "transaction_id":"drop1", "created":5, "drops":{"k1":1}, "adds":{}}
        rows = newsletter.transactions(lambda path: [item] if path.endswith('/9') else [],
                                       'league26', 9,
                                       {'k1':{'name':'Case Keenum'}}, {1:'Team One'})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['description'], 'Team One dropped Case Keenum')
        self.assertNotIn('; dropped', rows[0]['description'])

    def test_unknown_player_id_is_omitted_without_inventing_name(self):
        item = {"status":"complete", "type":"waiver", "roster_ids":[1],
                "transaction_id":"waiver1", "created":7,
                "adds":{"good":1}, "drops":{"7839":1}}
        rows = newsletter.transactions(lambda path: [item] if path.endswith('/9') else [],
                                       'league26', 9,
                                       {'good':{'name':'Michael Mayer'}}, {1:'Team One'})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['description'], 'Team One added Michael Mayer')
        self.assertNotIn('7839', rows[0]['description'])

    def test_unknown_only_transaction_is_not_published(self):
        item = {"status":"complete", "type":"free_agent", "roster_ids":[1],
                "transaction_id":"unknown1", "created":3, "drops":{"7839":1}}
        rows = newsletter.transactions(lambda path: [item] if path.endswith('/9') else [],
                                       'league26', 9, {}, {1:'Team One'})
        self.assertEqual(rows, [])

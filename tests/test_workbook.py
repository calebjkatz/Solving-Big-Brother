import json
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook
from openpyxl.comments import Comment

from app import BASE_DIR, create_app
from scripts.import_workbook import build_content
from workbook_sync import apply_workbook_content


class WorkbookImporterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'source.xlsx'
        self.book = Workbook()
        family = self.book.active
        family.title = 'Family Database'
        family.append(['Family Name', 'Description', 'Strategy'])
        family.append(['New Rule', 'General family rules', None])
        self.sheet = self.book.create_sheet('Season 28')
        self.sheet.append(['Week Number', 'Competition Type', 'Competition Name', 'Competition Family',
                           'Competition Description', 'Competition Strategy', 'Photo of Competition',
                           'Video of Competition', 'Guest Appearances'])
        self.sheet.append([2, 'HOH', 'Achy Breaky HOH', 'New Rule', 'This season only', None, None, None, 'Enzo'])
        self.sheet['E2'].comment = Comment('Rules: https://example.org/episode', 'Research')
        self.catalog = {'competitions': [{'name': 'New Rule'}, {'name': 'Achy Breaky HOH'}],
                        'appearances': [{'season': 28, 'week': '2', 'type': 'HOH',
                                         'variation': 'Achy Breaky HOH', 'competition': 'Achy Breaky HOH',
                                         'event_key': 'bb28-event-08'}]}

    def tearDown(self):
        self.directory.cleanup()

    def run_import(self, previous=None):
        self.book.save(self.path)
        before = self.path.read_bytes()
        result = build_content(self.path, self.catalog, previous)
        self.assertEqual(self.path.read_bytes(), before)
        return result

    def test_content_and_sources_are_separate_from_results(self):
        content, report = self.run_import()
        event = content['events']['bb28-event-08']
        self.assertEqual(report['rows'], 1)
        self.assertEqual(event['description'], 'This season only')
        self.assertEqual(event['families'], ['New Rule'])
        self.assertEqual(event['sources']['description'], ['https://example.org/episode'])
        self.assertNotIn('participants', event)
        self.assertNotIn('winners', event)
        self.assertNotIn(str(self.directory.name), json.dumps(content))

    def test_blanks_preserve_prior_values(self):
        first, _ = self.run_import()
        first['events']['bb28-event-08']['strategy'] = 'Keep this strategy'
        first['families']['New Rule']['strategy'] = 'Keep family strategy'
        self.sheet['E2'] = None
        result, _ = self.run_import(first)
        self.assertEqual(result['events']['bb28-event-08']['description'], 'This season only')
        self.assertEqual(result['events']['bb28-event-08']['strategy'], 'Keep this strategy')
        self.assertEqual(result['families']['New Rule']['strategy'], 'Keep family strategy')

    def test_unknown_and_duplicate_events_abort(self):
        self.sheet['C2'] = 'Unknown competition'
        with self.assertRaisesRegex(ValueError, 'requires review'):
            self.run_import()
        self.sheet['C2'] = 'Achy Breaky HOH'
        self.sheet.append([2, 'HOH', 'Achy Breaky HOH', 'New Rule', 'Duplicate'])
        with self.assertRaisesRegex(ValueError, 'duplicates'):
            self.run_import()

    def test_unsafe_links_and_formulas_abort(self):
        self.sheet['G2'] = 'javascript:alert(1)'
        with self.assertRaisesRegex(ValueError, 'http'):
            self.run_import()
        self.sheet['G2'] = None
        self.sheet['F2'] = '=1+2'
        with self.assertRaisesRegex(ValueError, 'formulas/errors'):
            self.run_import()

    def test_multi_family_and_names_containing_commas(self):
        self.catalog['competitions'] += [{'name': 'Yankee Swap'}, {'name': 'Ready, Set, Woah'}]
        self.sheet['D2'] = 'Yankee Swap, Ready, Set, Woah'
        self.catalog['appearances'][0]['competition'] = 'Yankee Swap'
        duplicate = dict(self.catalog['appearances'][0], competition='Ready, Set, Woah')
        self.catalog['appearances'].append(duplicate)
        result, _ = self.run_import()
        self.assertEqual(result['events']['bb28-event-08']['families'], ['Yankee Swap', 'Ready, Set, Woah'])
        self.sheet['D2'] = 'Ready, Set, Woah'
        result, _ = self.run_import()
        self.assertEqual(result['events']['bb28-event-08']['families'], ['Ready, Set, Woah'])


class WorkbookSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.app = create_app({'TESTING': True, 'DATABASE': str(Path(cls.directory.name) / 'site.sqlite3')})
        cls.client = cls.app.test_client()
        cls.content = json.loads((BASE_DIR / 'data/workbook_content.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_all_imported_rules_and_sources_reach_the_database(self):
        with self.app.extensions['connect_db']() as db:
            self.assertEqual(len(self.content['events']), 978)
            for key, entry in self.content['events'].items():
                rows = db.execute('SELECT * FROM competition_instances WHERE source_event_key = ?', (key,)).fetchall()
                self.assertTrue(rows, key)
                for row in rows:
                    self.assertEqual(row['rules_notes'], entry['description'], key)
                    self.assertEqual(row['strategy_notes'], entry.get('strategy', ''), key)
                    self.assertEqual(row['guest_appearances'], entry.get('guest_appearances', ''), key)

    def test_latest_user_edits_and_event_navigation_render(self):
        response = self.client.get('/events/bb28-event-08')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'New Rule', response.data)
        self.assertIn(b'Description &amp; rules', response.data)
        self.assertIn(b'country-themed dance floor', response.data)
        self.assertIn(b'Devens', response.data)
        qualifier = self.client.get('/events/bb28-event-01').data
        self.assertIn(b'Enzo (seasons 12 and 22)', qualifier)
        self.assertNotIn(b'Dr. Will', qualifier)
        strategy = self.client.get('/events/bb28-event-02').data
        self.assertIn(b'intuative torque', strategy)
        self.assertIn(b'Cecelia Diamond', strategy)
        self.assertEqual(self.client.get('/events/not-a-real-event').status_code, 404)
        with self.app.extensions['connect_db']() as db:
            season = db.execute('SELECT id FROM seasons WHERE season_number=28').fetchone()[0]
            family = db.execute("SELECT id FROM competitions WHERE name='New Rule'").fetchone()[0]
        season_html = self.client.get(f'/seasons/{season}').data
        self.assertIn(b'/events/bb28-event-08', season_html)
        self.assertNotIn(b'<th>Players</th>', season_html)
        self.assertNotIn(b'<th>Day</th>', season_html)
        family_html = self.client.get(f'/competitions/{family}').data
        self.assertIn(b'Go through a series of rounds', family_html)

    def test_every_imported_competition_page_renders(self):
        for key in self.content['events']:
            response = self.client.get(f'/events/{key}')
            self.assertEqual(response.status_code, 200, key)
            self.assertIn(b'Description &amp; rules', response.data, key)

    def test_old_family_links_redirect_without_removing_results(self):
        redirects = self.app.extensions['workbook_redirects']
        self.assertTrue(redirects)
        for old, new in redirects.items():
            response = self.client.get(f'/competitions/{old}')
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith(f'/competitions/{new}'))

    def test_import_is_idempotent_and_preserves_every_result_and_participant(self):
        baseline = create_app({'TESTING': True, 'DATABASE': str(Path(self.directory.name) / 'baseline.sqlite3'),
                               'WORKBOOK_CONTENT': None})
        content = self.content
        with baseline.extensions['connect_db']() as db:
            results_sql = 'SELECT id, source_event_key, week, day, competition_type, variation_name, winner, outcome_notes FROM competition_instances ORDER BY id'
            people_sql = 'SELECT * FROM competition_participants ORDER BY id'
            results_before = [tuple(row) for row in db.execute(results_sql)]
            people_before = [tuple(row) for row in db.execute(people_sql)]
            apply_workbook_content(db, content)
            sources_first = db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]
            families_first = db.execute('SELECT COUNT(*) FROM competitions').fetchone()[0]
            apply_workbook_content(db, content)
            self.assertEqual([tuple(row) for row in db.execute(results_sql)], results_before)
            self.assertEqual([tuple(row) for row in db.execute(people_sql)], people_before)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sources').fetchone()[0], sources_first)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM competitions').fetchone()[0], families_first)

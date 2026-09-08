import tempfile
import unittest
from pathlib import Path

from app import create_app


class BigBrotherStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": str(Path(self.temp_dir.name) / "test.sqlite3")})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_directory_has_seed_data_and_filters(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Study the comp.", response.data)
        self.assertIn(b"Competition analysis feed", response.data)
        self.assertIn(b"OTEV", response.data)
        self.assertIn(b"BB Comics", response.data)
        self.assertIn(b"Pressure Cooker", response.data)
        self.assertIn(
            b"Tracked seasons: 7,8,9,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27",
            response.data,
        )

        response = self.client.get("/?q=OTEV")
        self.assertIn(b"OTEV", response.data)
        self.assertNotIn(b"BB Comics", response.data)

    def test_competition_detail_lists_appearances(self):
        response = self.client.get("/competitions/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Season appearances", response.data)

    def test_bb25_week_four_veto_lists_all_players(self):
        with self.app.app_context():
            connect = self.app.extensions["connect_db"]
            with connect() as db:
                competition_id = db.execute(
                    "SELECT id FROM competitions WHERE name = 'Artifact Stack'"
                ).fetchone()[0]
        response = self.client.get(f"/competitions/{competition_id}")
        self.assertEqual(response.status_code, 200)
        for name in (b"Cameron", b"Blue", b"Jag", b"Mecole", b"Jared", b"Red"):
            self.assertIn(name, response.data)
        self.assertIn(b"Red \xe2\x98\x85", response.data)
        self.assertIn(b"BB25", response.data)

    def test_every_non_hoh_competition_has_documented_players(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            missing = db.execute("""
                SELECT COUNT(*)
                FROM competition_instances ci
                WHERE LOWER(ci.competition_type) NOT LIKE '%hoh%'
                  AND NOT EXISTS (
                      SELECT 1 FROM competition_participants cp
                      WHERE cp.instance_id = ci.id
                        AND cp.notes LIKE '%participant%'
                  )
            """).fetchone()[0]
            self.assertEqual(missing, 0)

            invalid_winners = db.execute("""
                SELECT COUNT(*)
                FROM competition_participants cp
                JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE LOWER(ci.competition_type) NOT LIKE '%hoh%'
                  AND cp.placement = 1
                  AND cp.notes NOT LIKE '%participant%'
            """).fetchone()[0]
            self.assertEqual(invalid_winners, 0)

    def test_every_hoh_competition_has_documented_players(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            missing = db.execute("""
                SELECT COUNT(*)
                FROM competition_instances ci
                WHERE LOWER(ci.competition_type) LIKE '%hoh%'
                  AND NOT EXISTS (
                      SELECT 1 FROM competition_participants cp
                      WHERE cp.instance_id = ci.id
                        AND cp.notes LIKE '%participant%'
                  )
            """).fetchone()[0]
            self.assertEqual(missing, 0)

            premiere_fields = db.execute("""
                SELECT ci.source_event_key, COUNT(cp.houseguest_id)
                FROM competition_instances ci
                JOIN competition_participants cp ON cp.instance_id = ci.id
                WHERE ci.source_event_key IN (
                    'bb16-event-01', 'bb16-event-02',
                    'bb17-event-01', 'bb17-event-02'
                ) AND cp.notes LIKE '%participant%'
                GROUP BY ci.source_event_key
            """).fetchall()
            self.assertEqual(dict(premiere_fields), {
                "bb16-event-01": 8, "bb16-event-02": 8,
                "bb17-event-01": 7, "bb17-event-02": 7,
            })

            bb23_final = db.execute("""
                SELECT ci.source_event_key, COUNT(cp.houseguest_id)
                FROM competition_instances ci
                JOIN competition_participants cp ON cp.instance_id = ci.id
                WHERE ci.source_event_key IN (
                    'bb23-event-36', 'bb23-event-37', 'bb23-event-38'
                ) AND cp.notes LIKE '%participant%'
                GROUP BY ci.source_event_key
            """).fetchall()
            self.assertEqual(dict(bb23_final), {
                "bb23-event-36": 3, "bb23-event-37": 2,
                "bb23-event-38": 2,
            })

    def test_season_index_and_detail(self):
        response = self.client.get("/seasons")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Big Brother 25", response.data)
        self.assertIn(b"Big Brother 27", response.data)

    def test_houseguest_directory_and_profile(self):
        response = self.client.get("/houseguests?season=24&q=Taylor")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Taylor", response.data)
        self.assertIn(b"BB24", response.data)
        self.assertIn(b"documented wins", response.data)
        self.assertIn(b"Taylor memory-wall photo", response.data)
        self.assertIn(b"static.wikia.nocookie.net", response.data)

        connect = self.app.extensions["connect_db"]
        with connect() as db:
            player_id = db.execute("""
                SELECT h.id FROM houseguests h JOIN seasons s ON s.id = h.season_id
                WHERE h.name = 'Taylor' AND s.season_number = 24
            """).fetchone()[0]
        profile = self.client.get(f"/houseguests/{player_id}")
        self.assertEqual(profile.status_code, 200)
        self.assertIn(b"Competitions won", profile.data)
        self.assertIn(b"Strengths", profile.data)
        self.assertIn(b"Weaknesses", profile.data)
        self.assertIn(b"Memory-wall image source", profile.data)

    def test_houseguest_bios_use_full_names_including_game_nicknames(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            rockstar = db.execute("""
                SELECT h.bio, h.person_key FROM houseguests h
                JOIN seasons s ON s.id = h.season_id
                WHERE s.season_number = 20 AND h.name = 'Rockstar'
            """).fetchone()
            self.assertEqual(rockstar["person_key"], 'Angie "Rockstar" Lantry')
            self.assertIn('Angie "Rockstar" Lantry competed', rockstar["bio"])
            incomplete = db.execute("""
                SELECT COUNT(*) FROM houseguests
                WHERE bio NOT LIKE '%' || person_key || '%'
            """).fetchone()[0]
            self.assertEqual(incomplete, 0)

    def test_returning_player_has_season_and_combined_performance(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            janelle = db.execute("""
                SELECT h.id FROM houseguests h JOIN seasons s ON s.id = h.season_id
                WHERE h.person_key = 'Janelle Pierzina' AND s.season_number = 6
            """).fetchone()
            self.assertIsNotNone(janelle)
        response = self.client.get(f"/houseguests/{janelle['id']}")
        self.assertIn(b"Combined performance", response.data)
        self.assertIn(b"across 4 seasons", response.data)
        for season in (6, 7, 14, 22):
            self.assertIn(f"BB{season}".encode(), response.data)

    def test_player_win_counts_deduplicate_multi_family_events(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            jag = db.execute("""
                SELECT h.id FROM houseguests h JOIN seasons s ON s.id = h.season_id
                WHERE h.name = 'Jag' AND s.season_number = 25
            """).fetchone()
            raw, distinct_events = db.execute("""
                SELECT COUNT(*), COUNT(DISTINCT ci.source_event_key)
                FROM competition_participants cp
                JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE cp.houseguest_id = ? AND cp.placement = 1
            """, (jag["id"],)).fetchone()
            self.assertGreater(raw, distinct_events)
            self.assertEqual(distinct_events, 12)
        response = self.client.get(f"/houseguests/{jag['id']}")
        self.assertIn(b'<strong>12</strong>', response.data)
        self.assertIn(b'<strong>37.5%</strong>', response.data)
        self.assertIn(b'12 wins in 32 competitions played', response.data)

    def test_houseguest_profile_shows_win_rates_by_competition_type(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            jag_id = db.execute("""
                SELECT h.id FROM houseguests h JOIN seasons s ON s.id = h.season_id
                WHERE h.name = 'Jag' AND s.season_number = 25
            """).fetchone()[0]
        response = self.client.get(f"/houseguests/{jag_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Competition efficiency", response.data)
        self.assertIn(b"Win rate", response.data)
        self.assertIn(b"POV", response.data)
        self.assertRegex(response.data.decode(), r"POV</span><b>\d+\.\d%</b><small>\d+/\d+</small>")

    def test_returning_player_profile_shows_combined_win_rate(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            janelle_id = db.execute("""
                SELECT h.id FROM houseguests h JOIN seasons s ON s.id = h.season_id
                WHERE h.person_key = 'Janelle Pierzina' AND s.season_number = 6
            """).fetchone()[0]
        response = self.client.get(f"/houseguests/{janelle_id}")
        self.assertIn(b"Combined performance", response.data)
        self.assertIn(b"% win rate", response.data)
        self.assertRegex(response.data.decode(), r"BB14</span><b>\d+ wins? \u00b7 \d+\.\d%")

    def test_ai_arena_and_block_buster_safety_results_count_as_wins(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            credited = dict(db.execute("""
                SELECT ci.competition_type,
                       COUNT(DISTINCT ci.source_event_key) AS credited_wins
                FROM competition_participants cp
                JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE cp.placement = 1
                  AND ci.competition_type IN ('AI Arena', 'Block Buster')
                GROUP BY ci.competition_type
            """).fetchall())
            self.assertEqual(credited, {"AI Arena": 7, "Block Buster": 18})

            kelley = db.execute("""
                SELECT h.id FROM houseguests h JOIN seasons s ON s.id = h.season_id
                WHERE h.name = 'Kelley' AND s.season_number = 27
            """).fetchone()
        profile = self.client.get(f"/houseguests/{kelley['id']}")
        self.assertIn(b"Block Buster <b>3</b>", profile.data)

    def test_battle_of_the_block_credits_both_safe_nominees(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            events, winner_credits = db.execute("""
                SELECT COUNT(DISTINCT ci.source_event_key),
                       COUNT(DISTINCT ci.source_event_key || ':' || cp.houseguest_id)
                FROM competition_instances ci
                JOIN competition_participants cp ON cp.instance_id = ci.id
                WHERE ci.competition_type = 'BOB' AND cp.placement = 1
            """).fetchone()
            self.assertEqual(events, 13)
            self.assertEqual(winner_credits, 26)

    def test_coaches_competitions_credit_the_winning_coach(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            winners = db.execute("""
                SELECT h.name, COUNT(DISTINCT ci.source_event_key)
                FROM competition_instances ci
                JOIN competition_participants cp ON cp.instance_id = ci.id
                JOIN houseguests h ON h.id = cp.houseguest_id
                WHERE ci.competition_type = 'Coaches Competition'
                  AND cp.placement = 1
                GROUP BY h.name
            """).fetchall()
            self.assertEqual(dict(winners), {"Janelle": 2, "Mike": 1})

            results = [row[0] for row in db.execute("""
                SELECT outcome_notes FROM competition_instances
                WHERE competition_type = 'Coaches Competition'
                ORDER BY week
            """).fetchall()]
            self.assertEqual(results, [
                "Mike wins the Coaches Competition and saves Ian",
                "Janelle wins the Coaches Competition and saves Ashley",
                "Janelle wins the Coaches Competition and saves Wil",
            ])

    def test_season_competition_shows_spaced_family_name(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            season_id = db.execute(
                "SELECT id FROM seasons WHERE season_number = 24"
            ).fetchone()[0]
        response = self.client.get(f"/seasons/{season_id}")
        self.assertIn(b"OTEV the Singing Stageroach", response.data)
        self.assertIn(b"> (OTEV)</span>", response.data)
        self.assertEqual(response.data.count(b"OTEV the Singing Stageroach"), 1)

    def test_full_recurring_catalog_is_loaded(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            self.assertGreaterEqual(db.execute("SELECT COUNT(*) FROM competitions").fetchone()[0], 400)
            self.assertGreaterEqual(db.execute("SELECT COUNT(*) FROM competition_instances").fetchone()[0], 900)
            seasons = db.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]
            self.assertEqual(seasons, 27)

    def test_bb28_is_loaded_through_barrett_hoh(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            season = db.execute(
                "SELECT id FROM seasons WHERE season_number = 28"
            ).fetchone()
            self.assertIsNotNone(season)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM houseguests WHERE season_id = ?", (season["id"],)
            ).fetchone()[0], 17)
            latest = db.execute("""
                SELECT variation_name, competition_type, outcome_notes
                FROM competition_instances WHERE season_id = ?
                ORDER BY id DESC LIMIT 1
            """, (season["id"],)).fetchone()
            self.assertEqual(tuple(latest),
                             ("Rainbow Rollers", "HOH", "Barrett wins HOH"))
            season_one = db.execute("SELECT 1 FROM seasons WHERE season_number = 1").fetchone()
            self.assertIsNone(season_one)
            typed = db.execute("""
                SELECT COUNT(*) FROM competition_instances
                WHERE week != '' AND competition_type != ''
            """).fetchone()[0]
            self.assertGreaterEqual(typed, 900)
            otev_27 = db.execute("""
                SELECT ci.week, ci.competition_type, ci.variation_name
                FROM competition_instances ci
                JOIN competitions c ON c.id = ci.competition_id
                JOIN seasons s ON s.id = ci.season_id
                WHERE c.name = 'OTEV' AND s.season_number = 27
            """).fetchone()
            self.assertEqual(tuple(otev_27), ("6", "POV", "OTEV the Hog Father"))

    def test_add_competition(self):
        response = self.client.post("/competitions/new", data={
            "name": "Test Competition", "category": "Quiz",
            "description": "A test description", "verification_status": "needs verification",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Competition added", response.data)
        self.assertIn(b"Test Competition", response.data)

    def test_csv_export_and_health(self):
        response = self.client.get("/export/competitions.csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn(b"OTEV", response.data)
        self.assertEqual(self.client.get("/health").json, {"status": "ok"})

    def test_public_mode_is_read_only(self):
        public_app = create_app({
            "TESTING": True,
            "DATABASE": str(Path(self.temp_dir.name) / "public.sqlite3"),
            "PUBLIC_EDITING_ENABLED": False,
        })
        client = public_app.test_client()
        self.assertNotIn(b"Add competition", client.get("/").data)
        self.assertEqual(client.get("/competitions/new").status_code, 403)
        self.assertIn(b"Editing is private", client.get("/competitions/new").data)


if __name__ == "__main__":
    unittest.main()

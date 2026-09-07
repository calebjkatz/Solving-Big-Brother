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
        self.assertIn(b"BB25", response.data)

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

    def test_season_competition_shows_spaced_family_name(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            season_id = db.execute(
                "SELECT id FROM seasons WHERE season_number = 24"
            ).fetchone()[0]
        response = self.client.get(f"/seasons/{season_id}")
        self.assertIn(b"OTEV the Singing Stageroach", response.data)
        self.assertIn(b"> (OTEV)</span>", response.data)

    def test_full_recurring_catalog_is_loaded(self):
        connect = self.app.extensions["connect_db"]
        with connect() as db:
            self.assertGreaterEqual(db.execute("SELECT COUNT(*) FROM competitions").fetchone()[0], 400)
            self.assertGreaterEqual(db.execute("SELECT COUNT(*) FROM competition_instances").fetchone()[0], 900)
            seasons = db.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]
            self.assertEqual(seasons, 26)
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

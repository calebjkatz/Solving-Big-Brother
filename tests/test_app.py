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
        self.assertIn(b"Every repeat. Every variation.", response.data)
        self.assertIn(b"OTEV", response.data)
        self.assertIn(b"BB Comics", response.data)

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

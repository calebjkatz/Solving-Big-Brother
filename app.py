import csv
import io
import json
import os
import sqlite3
from pathlib import Path

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = BASE_DIR / "data" / "big_brother_stats.sqlite3"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "local-development-key"),
        DATABASE=str(DEFAULT_DATABASE),
        PUBLIC_EDITING_ENABLED=os.environ.get("PUBLIC_EDITING_ENABLED", "true").lower() == "true",
    )
    if test_config:
        app.config.update(test_config)

    def connect():
        database = Path(app.config["DATABASE"])
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize_database():
        with connect() as db:
            db.executescript((BASE_DIR / "schema.sql").read_text())
            instance_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(competition_instances)")
            }
            if "week" not in instance_columns:
                db.execute("ALTER TABLE competition_instances ADD COLUMN week TEXT NOT NULL DEFAULT ''")
            if "day" not in instance_columns:
                db.execute("ALTER TABLE competition_instances ADD COLUMN day TEXT NOT NULL DEFAULT ''")
            if "source_event_key" not in instance_columns:
                db.execute("ALTER TABLE competition_instances ADD COLUMN source_event_key TEXT NOT NULL DEFAULT ''")
            houseguest_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(houseguests)")
            }
            for column in ("bio", "strengths", "weaknesses", "notes", "image_url",
                           "image_source", "person_key", "profile_url"):
                if column not in houseguest_columns:
                    db.execute(
                        f"ALTER TABLE houseguests ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
                    )
            if db.execute("SELECT COUNT(*) FROM franchises").fetchone()[0] == 0:
                db.executescript((BASE_DIR / "seed.sql").read_text())
            catalog_path = BASE_DIR / "data" / "us_recurring_competitions.json"
            if catalog_path.exists():
                catalog = json.loads(catalog_path.read_text())
                franchise_id = db.execute(
                    "SELECT id FROM franchises WHERE name = 'Big Brother US'"
                ).fetchone()[0]
                # The modern U.S. game format begins with season 2; season 1 is intentionally out of scope.
                db.execute(
                    "DELETE FROM seasons WHERE franchise_id = ? AND season_number = 1",
                    (franchise_id,),
                )
                for season in catalog["seasons"]:
                    db.execute("""
                        INSERT INTO seasons (franchise_id, season_number, title, year)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(franchise_id, season_number) DO UPDATE SET
                            title=excluded.title, year=excluded.year
                    """, (franchise_id, season["number"], season["title"], season["year"]))
                db.execute("""
                    DELETE FROM competition_instances
                    WHERE variation_name IN ('Starter appearance record', 'Recurring format appearance')
                       OR verification_status = 'source indexed'
                """)
                for item in catalog["competitions"]:
                    db.execute("""
                        INSERT OR IGNORE INTO competitions
                        (name, category, format, description, verification_status)
                        VALUES (?, 'Competition format', 'See sourced competition record', ?, 'partially verified')
                    """, (item["name"],
                          "A competition format documented in the Big Brother US competition history."))
                    competition_id = db.execute(
                        "SELECT id FROM competitions WHERE name = ?", (item["name"],)
                    ).fetchone()[0]
                    if not db.execute(
                        "SELECT 1 FROM sources WHERE competition_id = ? AND url = ?",
                        (competition_id, item["source_url"]),
                    ).fetchone():
                        db.execute("""
                            INSERT INTO sources (competition_id, title, url, source_type, notes)
                            VALUES (?, ?, ?, 'community-maintained reference', ?)
                        """, (competition_id, f"Big Brother Wiki: {item['name']}", item["source_url"],
                              f"Season mapping derived from {catalog['source']} and U.S. season competition tables."))
                for player in catalog.get("houseguests", []):
                    season_id = db.execute("""
                        SELECT id FROM seasons WHERE franchise_id = ? AND season_number = ?
                    """, (franchise_id, player["season"])).fetchone()[0]
                    db.execute("""
                        INSERT INTO houseguests
                        (season_id, name, bio, strengths, weaknesses, notes, image_url,
                         image_source, person_key, profile_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(season_id, name) DO UPDATE SET
                            bio=excluded.bio, strengths=excluded.strengths,
                            weaknesses=excluded.weaknesses, notes=excluded.notes,
                            image_url=excluded.image_url, image_source=excluded.image_source,
                            person_key=excluded.person_key, profile_url=excluded.profile_url
                    """, (season_id, player["name"], player["bio"], player["strengths"],
                          player["weaknesses"], player["notes"], player.get("image_url", ""),
                          player.get("image_source", ""), player.get("person_key", player["name"]),
                          player.get("profile_url", "")))
                for appearance in catalog.get("appearances", []):
                    competition_id = db.execute(
                        "SELECT id FROM competitions WHERE name = ?", (appearance["competition"],)
                    ).fetchone()[0]
                    season_id = db.execute("""
                        SELECT id FROM seasons WHERE franchise_id = ? AND season_number = ?
                    """, (franchise_id, appearance["season"])).fetchone()[0]
                    cursor = db.execute("""
                        INSERT INTO competition_instances
                        (competition_id, season_id, week, day, source_event_key, competition_type,
                         variation_name, outcome_notes, verification_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'source indexed')
                    """, (competition_id, season_id, appearance["week"], appearance["day"],
                          appearance["event_key"], appearance["type"], appearance["variation"],
                          appearance["result"]))
                    instance_id = cursor.lastrowid
                    winners = set(appearance.get("winners", []))
                    for participant in appearance.get("participants", []):
                        houseguest = db.execute("""
                            SELECT id FROM houseguests WHERE season_id = ? AND name = ?
                        """, (season_id, participant)).fetchone()
                        if houseguest:
                            db.execute("""
                                INSERT OR IGNORE INTO competition_participants
                                (instance_id, houseguest_id, placement, notes)
                                VALUES (?, ?, ?, 'source indexed participant')
                            """, (instance_id, houseguest["id"], 1 if participant in winners else None))
                    for winner in appearance.get("winners", []):
                        houseguest = db.execute("""
                            SELECT id FROM houseguests WHERE season_id = ? AND name = ?
                        """, (season_id, winner)).fetchone()
                        if houseguest:
                            db.execute("""
                                INSERT INTO competition_participants
                                (instance_id, houseguest_id, placement, notes)
                                VALUES (?, ?, 1, 'source indexed winner')
                                ON CONFLICT(instance_id, houseguest_id) DO UPDATE SET
                                    placement=1,
                                    notes=CASE
                                        WHEN competition_participants.notes LIKE '%participant%'
                                        THEN 'source indexed winner and participant'
                                        ELSE 'source indexed winner'
                                    END
                            """, (instance_id, houseguest["id"]))

    app.extensions["connect_db"] = connect
    app.extensions["initialize_database"] = initialize_database
    initialize_database()

    @app.context_processor
    def template_helpers():
        return {
            "format_tags": lambda value: [tag.strip() for tag in (value or "").split(",") if tag.strip()],
            "editing_enabled": app.config["PUBLIC_EDITING_ENABLED"],
        }

    @app.get("/")
    def index():
        query = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        skill = request.args.get("skill", "").strip()
        sql = """
            SELECT c.*, COUNT(ci.id) AS appearance_count,
                   (
                       SELECT GROUP_CONCAT(ordered_seasons.season_number)
                       FROM (
                           SELECT DISTINCT s2.season_number
                           FROM competition_instances ci2
                           JOIN seasons s2 ON s2.id = ci2.season_id
                           WHERE ci2.competition_id = c.id
                           ORDER BY s2.season_number
                       ) AS ordered_seasons
                   ) AS seasons
            FROM competitions c
            LEFT JOIN competition_instances ci ON ci.competition_id = c.id
            LEFT JOIN seasons s ON s.id = ci.season_id
            WHERE 1 = 1
        """
        params = []
        if query:
            sql += " AND (c.name LIKE ? OR c.description LIKE ? OR c.aliases LIKE ?)"
            wildcard = f"%{query}%"
            params.extend([wildcard, wildcard, wildcard])
        if category:
            sql += " AND c.category = ?"
            params.append(category)
        if skill:
            sql += " AND c.skills LIKE ?"
            params.append(f"%{skill}%")
        sql += " GROUP BY c.id ORDER BY c.name COLLATE NOCASE"
        with connect() as db:
            competitions = db.execute(sql, params).fetchall()
            categories = db.execute("SELECT DISTINCT category FROM competitions ORDER BY category").fetchall()
            skills = db.execute("SELECT skills FROM competitions").fetchall()
            stats = {
                "competitions": db.execute("SELECT COUNT(*) FROM competitions").fetchone()[0],
                "appearances": db.execute("SELECT COUNT(*) FROM competition_instances").fetchone()[0],
                "seasons": db.execute("SELECT COUNT(*) FROM seasons").fetchone()[0],
            }
        skill_options = sorted({item.strip() for row in skills for item in (row[0] or "").split(",") if item.strip()})
        return render_template("index.html", competitions=competitions, categories=categories,
                               skill_options=skill_options, stats=stats, filters=request.args)

    @app.get("/competitions/<int:competition_id>")
    def competition_detail(competition_id):
        with connect() as db:
            competition = db.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,)).fetchone()
            if not competition:
                abort(404)
            appearances = db.execute("""
                SELECT ci.*, s.season_number, s.year, s.title, f.name AS franchise_name
                FROM competition_instances ci
                JOIN seasons s ON s.id = ci.season_id
                JOIN franchises f ON f.id = s.franchise_id
                WHERE ci.competition_id = ?
                ORDER BY s.season_number DESC, CAST(ci.week AS INTEGER), ci.day
            """, (competition_id,)).fetchall()
            sources = db.execute("SELECT * FROM sources WHERE competition_id = ? ORDER BY title", (competition_id,)).fetchall()
            winner_rows = db.execute("""
                SELECT cp.instance_id, h.id, h.name FROM competition_participants cp
                JOIN houseguests h ON h.id = cp.houseguest_id
                JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE ci.competition_id = ? AND cp.placement = 1
                ORDER BY h.name
            """, (competition_id,)).fetchall()
            participant_rows = db.execute("""
                SELECT cp.instance_id, h.id, h.name, cp.placement
                FROM competition_participants cp
                JOIN houseguests h ON h.id = cp.houseguest_id
                JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE ci.competition_id = ?
                  AND EXISTS (
                      SELECT 1 FROM competition_participants documented
                      WHERE documented.instance_id = cp.instance_id
                        AND documented.notes LIKE '%participant%'
                  )
                ORDER BY cp.placement IS NOT NULL DESC, h.name COLLATE NOCASE
            """, (competition_id,)).fetchall()
        winners = {}
        for row in winner_rows:
            winners.setdefault(row["instance_id"], []).append(row)
        participants = {}
        for row in participant_rows:
            participants.setdefault(row["instance_id"], []).append(row)
        return render_template("competition.html", competition=competition, appearances=appearances,
                               sources=sources, winners=winners, participants=participants)

    @app.route("/competitions/new", methods=["GET", "POST"])
    def new_competition():
        if not app.config["PUBLIC_EDITING_ENABLED"]:
            abort(403)
        if request.method == "POST":
            required = ["name", "category", "description"]
            if any(not request.form.get(field, "").strip() for field in required):
                flash("Name, category, and description are required.", "error")
                return render_template("competition_form.html", values=request.form), 400
            with connect() as db:
                cursor = db.execute("""
                    INSERT INTO competitions
                    (name, aliases, category, format, description, skills, strategy, strategy_evidence, verification_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(request.form.get(field, "").strip() for field in (
                    "name", "aliases", "category", "format", "description", "skills",
                    "strategy", "strategy_evidence", "verification_status"
                )))
                competition_id = cursor.lastrowid
            flash("Competition added.", "success")
            return redirect(url_for("competition_detail", competition_id=competition_id))
        return render_template("competition_form.html", values={"verification_status": "needs verification"})

    @app.route("/competitions/<int:competition_id>/appearances/new", methods=["GET", "POST"])
    def new_appearance(competition_id):
        if not app.config["PUBLIC_EDITING_ENABLED"]:
            abort(403)
        with connect() as db:
            competition = db.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,)).fetchone()
            if not competition:
                abort(404)
            seasons = db.execute("SELECT * FROM seasons ORDER BY season_number DESC").fetchall()
            if request.method == "POST":
                try:
                    season_id = int(request.form.get("season_id", ""))
                except ValueError:
                    season_id = 0
                if not any(row["id"] == season_id for row in seasons):
                    flash("Choose a valid season.", "error")
                    return render_template("appearance_form.html", competition=competition, seasons=seasons), 400
                db.execute("""
                    INSERT INTO competition_instances
                    (competition_id, season_id, week, day, episode, competition_type, variation_name, rules_notes, winner, outcome_notes, verification_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (competition_id, season_id) + tuple(request.form.get(field, "").strip() for field in (
                    "week", "day", "episode", "competition_type", "variation_name", "rules_notes", "winner",
                    "outcome_notes", "verification_status"
                )))
                db.commit()
            if request.method == "POST":
                flash("Season appearance added.", "success")
                return redirect(url_for("competition_detail", competition_id=competition_id))
        return render_template("appearance_form.html", competition=competition, seasons=seasons)

    @app.get("/seasons")
    def seasons():
        with connect() as db:
            rows = db.execute("""
                SELECT s.*, f.name AS franchise_name, COUNT(ci.id) AS tracked_competitions
                FROM seasons s JOIN franchises f ON f.id = s.franchise_id
                LEFT JOIN competition_instances ci ON ci.season_id = s.id
                GROUP BY s.id ORDER BY s.season_number DESC
            """).fetchall()
        return render_template("seasons.html", seasons=rows)

    @app.get("/houseguests")
    def houseguests():
        query = request.args.get("q", "").strip()
        season_number = request.args.get("season", "").strip()
        sql = """
            SELECT h.*, s.season_number, s.year,
                   COUNT(DISTINCT CASE WHEN cp.id IS NOT NULL THEN
                       COALESCE(NULLIF(ci.source_event_key, ''), 'local-' || ci.id) END) AS competition_wins
            FROM houseguests h
            JOIN seasons s ON s.id = h.season_id
            LEFT JOIN competition_participants cp
              ON cp.houseguest_id = h.id AND cp.placement = 1
            LEFT JOIN competition_instances ci ON ci.id = cp.instance_id
            WHERE 1 = 1
        """
        params = []
        if query:
            sql += " AND h.name LIKE ?"
            params.append(f"%{query}%")
        if season_number:
            sql += " AND s.season_number = ?"
            params.append(season_number)
        sql += " GROUP BY h.id ORDER BY s.season_number DESC, h.name COLLATE NOCASE"
        with connect() as db:
            players = db.execute(sql, params).fetchall()
            season_options = db.execute(
                "SELECT season_number FROM seasons ORDER BY season_number DESC"
            ).fetchall()
        return render_template("houseguests.html", players=players,
                               season_options=season_options, filters=request.args)

    @app.get("/houseguests/<int:houseguest_id>")
    def houseguest_detail(houseguest_id):
        with connect() as db:
            player = db.execute("""
                SELECT h.*, s.season_number, s.year, s.title
                FROM houseguests h JOIN seasons s ON s.id = h.season_id
                WHERE h.id = ?
            """, (houseguest_id,)).fetchone()
            if not player:
                abort(404)
            wins = db.execute("""
                SELECT ci.*, MIN(c.id) AS competition_id,
                       GROUP_CONCAT(DISTINCT c.name) AS family_name
                FROM competition_participants cp
                JOIN competition_instances ci ON ci.id = cp.instance_id
                JOIN competitions c ON c.id = ci.competition_id
                WHERE cp.houseguest_id = ? AND cp.placement = 1
                GROUP BY COALESCE(NULLIF(ci.source_event_key, ''), 'local-' || ci.id)
                ORDER BY CAST(ci.week AS INTEGER), CAST(ci.day AS REAL), c.name
            """, (houseguest_id,)).fetchall()
            type_counts = db.execute("""
                SELECT ci.competition_type,
                       COUNT(DISTINCT COALESCE(NULLIF(ci.source_event_key, ''), 'local-' || ci.id)) AS total
                FROM competition_participants cp
                JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE cp.houseguest_id = ? AND cp.placement = 1
                GROUP BY ci.competition_type ORDER BY total DESC
            """, (houseguest_id,)).fetchall()
            other_seasons = db.execute("""
                SELECT other.id, other.name, s.season_number, s.year,
                       COUNT(DISTINCT CASE WHEN cp.id IS NOT NULL THEN
                           COALESCE(NULLIF(ci.source_event_key, ''), 'local-' || ci.id) END) AS wins
                FROM houseguests other
                JOIN seasons s ON s.id = other.season_id
                LEFT JOIN competition_participants cp
                  ON cp.houseguest_id = other.id AND cp.placement = 1
                LEFT JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE other.person_key = ?
                GROUP BY other.id ORDER BY s.season_number
            """, (player["person_key"],)).fetchall()
            career_types = db.execute("""
                SELECT ci.competition_type,
                       COUNT(DISTINCT COALESCE(NULLIF(ci.source_event_key, ''), 'local-' || ci.id)) AS total
                FROM houseguests career
                JOIN competition_participants cp ON cp.houseguest_id = career.id AND cp.placement = 1
                JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE career.person_key = ?
                GROUP BY ci.competition_type ORDER BY total DESC
            """, (player["person_key"],)).fetchall()
            career_total = sum(row["wins"] for row in other_seasons)
        return render_template("houseguest.html", player=player, wins=wins,
                               type_counts=type_counts, other_seasons=other_seasons,
                               career_types=career_types, career_total=career_total)

    @app.get("/seasons/<int:season_id>")
    def season_detail(season_id):
        with connect() as db:
            season = db.execute("""
                SELECT s.*, f.name AS franchise_name FROM seasons s
                JOIN franchises f ON f.id = s.franchise_id WHERE s.id = ?
            """, (season_id,)).fetchone()
            if not season:
                abort(404)
            appearances = db.execute("""
                SELECT ci.*, MIN(c.id) AS competition_id, MIN(c.name) AS name,
                       GROUP_CONCAT(DISTINCT c.name) AS family_names,
                       MIN(c.category) AS category, MIN(c.skills) AS skills
                FROM competition_instances ci
                JOIN competitions c ON c.id = ci.competition_id
                WHERE ci.season_id = ?
                GROUP BY COALESCE(NULLIF(ci.source_event_key, ''), 'local-' || ci.id)
                ORDER BY CAST(ci.week AS INTEGER), CAST(ci.day AS REAL), c.name
            """, (season_id,)).fetchall()
            winner_rows = db.execute("""
                SELECT cp.instance_id, h.id, h.name FROM competition_participants cp
                JOIN houseguests h ON h.id = cp.houseguest_id
                JOIN competition_instances ci ON ci.id = cp.instance_id
                WHERE ci.season_id = ? AND cp.placement = 1 ORDER BY h.name
            """, (season_id,)).fetchall()
        winners = {}
        for row in winner_rows:
            winners.setdefault(row["instance_id"], []).append(row)
        return render_template("season.html", season=season, appearances=appearances,
                               winners=winners)

    @app.get("/export/competitions.csv")
    def export_competitions():
        with connect() as db:
            rows = db.execute("SELECT * FROM competitions ORDER BY name").fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(rows[0].keys() if rows else ["id", "name"])
        writer.writerows([tuple(row) for row in rows])
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=big-brother-competitions.csv"})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, title="Editing is private",
                               message="This public research archive is read-only."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, title="Record not found",
                               message="That competition or season is not in the archive."), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

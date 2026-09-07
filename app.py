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
                db.execute("DELETE FROM competition_instances WHERE variation_name = 'Starter appearance record'")
                for item in catalog["competitions"]:
                    db.execute("""
                        INSERT OR IGNORE INTO competitions
                        (name, category, format, description, verification_status)
                        VALUES (?, 'Recurring format', 'See sourced competition record', ?, 'partially verified')
                    """, (item["name"],
                          "A recurring competition format documented across Big Brother US seasons."))
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
                    for season_number in item["seasons"]:
                        season_id = db.execute("""
                            SELECT id FROM seasons WHERE franchise_id = ? AND season_number = ?
                        """, (franchise_id, season_number)).fetchone()[0]
                        if not db.execute("""
                            SELECT 1 FROM competition_instances
                            WHERE competition_id = ? AND season_id = ?
                        """, (competition_id, season_id)).fetchone():
                            db.execute("""
                                INSERT INTO competition_instances
                                (competition_id, season_id, variation_name, verification_status)
                                VALUES (?, ?, 'Recurring format appearance', 'partially verified')
                            """, (competition_id, season_id))

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
                   GROUP_CONCAT(DISTINCT s.season_number) AS seasons
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
                ORDER BY s.season_number DESC
            """, (competition_id,)).fetchall()
            sources = db.execute("SELECT * FROM sources WHERE competition_id = ? ORDER BY title", (competition_id,)).fetchall()
        return render_template("competition.html", competition=competition, appearances=appearances, sources=sources)

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
                    (competition_id, season_id, episode, competition_type, variation_name, rules_notes, winner, outcome_notes, verification_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (competition_id, season_id) + tuple(request.form.get(field, "").strip() for field in (
                    "episode", "competition_type", "variation_name", "rules_notes", "winner",
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
                SELECT ci.*, c.name, c.category, c.skills FROM competition_instances ci
                JOIN competitions c ON c.id = ci.competition_id
                WHERE ci.season_id = ? ORDER BY COALESCE(ci.episode, 999), c.name
            """, (season_id,)).fetchall()
        return render_template("season.html", season=season, appearances=appearances)

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

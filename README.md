# Big Brother Stats

A local research app for recurring competitions in the U.S. civilian edition of *Big Brother*.

## What the MVP does

- Separates a reusable competition family from each season appearance.
- Filters competitions by name, category, and skill.
- Shows descriptions, strategic analysis, evidence notes, aliases, and appearances.
- Browses tracked competitions by season.
- Adds new competition families and season appearances through the browser.
- Exports the competition catalog to CSV.
- Includes schema support for houseguests, participant results, and sources.

The included records are starter data and intentionally labeled `needs verification`. They demonstrate the system; they are not a completed historical dataset.

## Run locally

```bash
cd "Big Brother Stats"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>.

The SQLite database is created automatically at `data/big_brother_stats.sqlite3`. Delete that file only when you deliberately want to recreate it from the seed data.

## Publish it on your website

The app is ready to deploy on Render using `render.yaml`. Your portfolio can remain on Cloudflare Pages, while this server-backed app lives at a custom subdomain such as `bigbrother.calebjkatz.com`.

1. Put this directory in its own GitHub repository, or make it the selected root directory in a monorepo.
2. In Render, create a Blueprint and connect that repository. Render will read `render.yaml`.
3. After the first successful deploy, add `bigbrother.calebjkatz.com` under the service's **Settings → Custom Domains**.
4. Add the DNS record Render gives you to the DNS settings for `calebjkatz.com`.
5. Add the final subdomain URL to the portfolio's project section.

Production is read-only by default (`PUBLIC_EDITING_ENABLED=false`). This prevents website visitors from changing the archive. Continue editing locally, commit updates to `seed.sql`, and redeploy. A future admin login and hosted PostgreSQL database can support safe browser-based editing.

Do not enable anonymous public editing. If persistent online editing becomes necessary, move the SQLite data to PostgreSQL and add authentication first.

## Test

```bash
cd "Big Brother Stats"
python3 -m unittest discover -s tests
```

## Recommended research workflow

1. Add or select a competition family.
2. Add one appearance for every season in which the format occurred.
3. Record the exact variation, competition type, episode, winner, and mechanics.
4. Add a source record in SQLite for every factual claim (source editing UI is a next milestone).
5. Move an entry from `needs verification` to `verified` only after checking reliable sources.
6. Update strategy separately from factual mechanics and state the evidence and limitations.

## Next milestones

1. Add season, source, houseguest, and participant editing screens.
2. Import a researched CSV covering all U.S. civilian seasons.
3. Store round-level results and calculate win rates by player and competition skill.
4. Add side-by-side competition and season comparisons.
5. Add authentication before deploying any editing interface publicly.

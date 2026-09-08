"""Import sourced non-HOH participation from houseguest competition-history tables."""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "us_recurring_competitions.json"
API = "https://bigbrother.fandom.com/api.php"
CACHE = Path("/tmp/big-brother-player-histories")
NON_PARTICIPATION = (
    "not picked", "ineligible", "unable to play", "did not play", "not eligible",
    "previous hoh", "not selected", "didn't play", "did not compete", "n/a",
    "sat out",
    "dethroned", "survived",
)

# Multi-stage twists often use one generic row on player profiles for several
# distinct competitions. These lineups come from season/episode competition tables.
OVERRIDES = {
    (6, "bb6-event-02"): {"Ashlea", "Beau", "Eric", "Ivette", "Jennifer", "Kaysar", "Michael", "Maggie", "Janelle", "April", "Howie", "James", "Rachel", "Sarah"},
    (11, "bb11-event-06"): {"Casey", "Chima", "Jeff", "Jordan", "Kevin", "Laura", "Lydia", "Michele", "Natalie", "Ronnie", "Russell", "Jessie"},
    (11, "bb11-event-15"): {"Chima", "Jeff", "Jordan", "Kevin", "Lydia", "Michele", "Natalie", "Russell", "Jessie"},
    (15, "bb15-event-25"): {"Candice", "Judd", "Jessie", "Helen"},
    (17, "bb17-event-29"): {"Shelli", "Jackie", "Becky", "John"},
    (18, "bb18-event-04"): {"Corey", "Glenn"},
    (18, "bb18-event-31"): {"Nicole", "Paul", "James", "Corey", "Victor", "Natalie", "Michelle", "Paulie"},
    (18, "bb18-event-37"): {"Da'Vonne", "Zakiyah", "Bridgette", "Paulie", "Victor"},
    (19, "bb19-event-15"): {"Alex", "Jason", "Mark", "Matt"},
    (19, "bb19-event-19"): {"Alex", "Cody", "Elena", "Jason", "Jessica", "Kevin", "Mark", "Matt", "Paul", "Raven"},
    (19, "bb19-event-22"): {"Cody", "Elena", "Jason", "Josh", "Kevin", "Mark", "Matt", "Paul", "Raven"},
    (20, "bb20-event-03"): {"Angela", "Bayleigh", "Brett", "Faysal", "Haleigh", "JC", "Kaitlyn", "Kaycee", "Rachel", "Rockstar", "Sam", "Scottie", "Steve", "Swaggy C", "Tyler", "Winston"},
    (20, "bb20-event-05"): {"Angela", "Swaggy C"},
    (21, "bb21-event-20"): {"Analyse", "Christie", "Jackson"},
    (23, "bb23-event-16"): {"Claire", "Derek F", "Kyland", "Sarah Beth", "Tiffany"},
    (23, "bb23-event-20"): {"Alyssa"},
    (23, "bb23-event-23"): {"Claire", "Derek F"},
    (25, "bb25-event-01"): {"America", "Jared", "Bowie Jane", "Mecole"},
    (25, "bb25-event-02"): {"Matt", "Blue", "Kirsten", "Hisam"},
    (25, "bb25-event-03"): {"Felicia", "Izzy", "Jag", "Cameron"},
    (25, "bb25-event-04"): {"Red", "Cory", "Luke", "Reilly"},
    (25, "bb25-event-24"): {"Cameron", "Jared"},
    (26, "bb26-event-01"): {"Angela", "Joseph", "Makensy", "Rubina"},
    (26, "bb26-event-02"): {"Cam", "Chelsie", "Kimo", "Tucker"},
    (26, "bb26-event-03"): {"Leah", "Quinn"},
    (26, "bb26-event-04"): {"Brooklyn", "Cedric", "Kenney", "Lisa", "Matt", "T'kor"},
    (28, "bb28-event-01"): {"Ashley", "Barrett", "Chuk", "Drew", "Haley", "Jason", "Kamu", "LaTrice", "Lyric", "Mallory", "Melody", "Rome", "Taylor", "Yash"},
    (28, "bb28-event-02"): {"LaTrice", "Kamu", "Rome", "Mallory"},
    (28, "bb28-event-03"): {"Drew", "Haley", "Chuk", "Taylor"},
    (28, "bb28-event-04"): {"Yash", "Melody", "Lyric", "Jason"},
}

BOTB = {
    (16, "1"): {"Brittany", "Victoria", "Donny", "Paola"},
    (16, "2"): {"Hayden", "Nicole", "Brittany", "Paola"},
    (16, "3"): {"Amber", "Donny", "Caleb", "Jocasta"},
    (16, "4"): {"Amber", "Jocasta", "Brittany", "Victoria"},
    (16, "5"): {"Christine", "Nicole", "Jocasta", "Victoria"},
    (16, "6"): {"Caleb", "Victoria", "Jocasta", "Zach"},
    (16, "7"): {"Frankie", "Donny", "Zach"},  # Caleb officially sat out.
    (16, "8"): {"Christine", "Donny", "Caleb", "Cody"},
    (17, "1"): {"Becky", "John", "Jackie", "Steve"},
    (17, "2"): {"Jason", "Steve", "Da'Vonne", "John"},
    (17, "3"): {"Jason", "Meg", "James", "John"},
    (17, "4"): {"Jackie", "James", "Jason", "John"},
    (17, "5"): {"James", "Liz", "Becky", "Clay"},
}


def title_from_url(url):
    return urllib.parse.unquote(url.rsplit("/", 1)[-1])


def fetch(title):
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / (urllib.parse.quote(title, safe="") + ".json")
    if target.exists():
        return title, json.loads(target.read_text())["parse"]["text"]["*"]
    query = urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "text", "format": "json",
        "origin": "*",
    })
    request = urllib.request.Request(
        f"{API}?{query}", headers={"User-Agent": "BigBrotherStatsResearch/1.0"}
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read().decode()
            target.write_text(payload)
            return title, json.loads(payload)["parse"]["text"]["*"]
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def histories(html):
    """Yield (season, week, sequence, label, status) rows from profile tables."""
    soup = BeautifulSoup(html, "html.parser")
    for heading in soup.find_all(["h2", "h3"]):
        heading_text = clean(heading.get_text(" ", strip=True))
        match = re.search(r"Player History.*?Big Brother\s+(\d+)", heading_text, re.I)
        if not match:
            continue
        season = int(match.group(1))
        node = heading.find_next_sibling()
        while node and node.name not in ("h2",):
            if node.name == "h3" and "Competition History" in clean(node.get_text(" ", strip=True)):
                table = node.find_next("table")
                current_week = None
                sequence = defaultdict(int)
                for row in table.find_all("tr") if table else []:
                    cells = [clean(cell.get_text(" ", strip=True))
                             for cell in row.find_all(["th", "td"], recursive=False)]
                    if not cells:
                        continue
                    if re.fullmatch(r"Week\s+\d+(?:\.\d+)?", cells[0], re.I):
                        current_week = re.search(r"\d+(?:\.\d+)?", cells[0]).group()
                        cells = cells[1:]
                    if current_week and len(cells) >= 2:
                        label, status = cells[-2], cells[-1]
                        key = normalize_type(label)
                        sequence[(current_week, key)] += 1
                        yield season, current_week, sequence[(current_week, key)], label, status
            node = node.find_next_sibling()


def normalize_type(value):
    value = clean(value).casefold().replace("power of veto", "pov")
    value = value.replace("battle of the block", "bob").replace("botb", "bob")
    value = value.replace("bb blockbuster", "block buster").replace("blockbuster", "block buster")
    value = re.sub(r"\s+part\s+\d+$", "", value)
    if re.search(r"\bpov\b", value) or "veto" in value:
        return "pov"
    if "hoh" in value or "head of household" in value:
        return "hoh"
    if "ai arena" in value:
        return "ai arena"
    if "block buster" in value:
        return "block buster"
    if value == "bob" or "bob" in value:
        return "bob"
    if "have-not" in value or "have/not" in value or "have not" in value:
        return "have-not"
    if "food" in value:
        return "food"
    if "luxury" in value:
        return "luxury"
    if any(term in value for term in ("re-entry", "reentry", "battle back", "comeback")):
        return "re-entry"
    if value == "htr" or "hit the road" in value:
        return "hit the road"
    if "immunity" in value or value == "safety":
        return "immunity"
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def participated(status):
    status = clean(status).casefold()
    return bool(status) and not any(marker in status for marker in NON_PARTICIPATION)


def main(download):
    catalog = json.loads(DATA.read_text())
    profiles = {title_from_url(h["profile_url"]) for h in catalog["houseguests"]
                if h.get("profile_url")}
    pages = {}
    if download:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(fetch, title): title for title in profiles}
            for index, future in enumerate(as_completed(futures), 1):
                title, html = future.result()
                pages[title] = html
                if index % 25 == 0:
                    print(f"Downloaded {index}/{len(futures)} profiles")
    else:
        for title in profiles:
            path = CACHE / (urllib.parse.quote(title, safe="") + ".json")
            if path.exists():
                pages[title] = json.loads(path.read_text())["parse"]["text"]["*"]

    # Rebuild imported lineups from scratch so parser improvements remove stale rows.
    for appearance in catalog["appearances"]:
        if normalize_type(appearance["type"]) != "hoh":
            appearance.pop("participants", None)

    # One chronological slot for each distinct televised event.
    slots = defaultdict(list)
    seen = set()
    for appearance in catalog["appearances"]:
        if normalize_type(appearance["type"]) == "hoh":
            continue
        identity = (appearance["season"], appearance["event_key"])
        if identity in seen:
            continue
        seen.add(identity)
        key = (appearance["season"], str(appearance["week"]), normalize_type(appearance["type"]))
        slots[key].append(appearance["event_key"])

    event_players = defaultdict(set)
    unmatched = []
    for player in catalog["houseguests"]:
        html = pages.get(title_from_url(player.get("profile_url", "")))
        if not html:
            continue
        for season, week, sequence, label, status in histories(html):
            if season != player["season"] or normalize_type(label) == "hoh" or not participated(status):
                continue
            candidates = slots.get((season, week, normalize_type(label)), [])
            if sequence <= len(candidates):
                event_players[(season, candidates[sequence - 1])].add(player["name"])
            else:
                unmatched.append((season, player["name"], week, label, status))

    event_players.update({key: set(value) for key, value in OVERRIDES.items()})
    for appearance in catalog["appearances"]:
        if normalize_type(appearance["type"]) == "bob":
            event_players[(appearance["season"], appearance["event_key"])] = set(
                BOTB[(appearance["season"], str(appearance["week"]))]
            )

    for appearance in catalog["appearances"]:
        if normalize_type(appearance["type"]) != "hoh":
            players = set(event_players.get((appearance["season"], appearance["event_key"]), ()))
            players.update(appearance.get("winners", []))
            if players:
                appearance["participants"] = sorted(players, key=str.casefold)

    DATA.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    print(f"Mapped {len(event_players)} non-HOH events; {len(unmatched)} played rows unmatched")
    for row in unmatched[:100]:
        print("UNMATCHED", *row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    main(parser.parse_args().download)

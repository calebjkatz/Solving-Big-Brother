"""Ensure every season profile names the person, not only their game nickname."""
import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data" / "us_recurring_competitions.json"

# The wiki page title is usually a full name, but these profiles use a nickname,
# shortened name, or privacy-redacted title that needs a sourced correction.
FULL_NAME_CORRECTIONS = {
    "Bunky Miller": 'Bill "Bunky" Miller',
    "Nakomis Dedmon": 'Jennifer "Nakomis" Dedmon',
    "Enzo Palumbo": 'Vincenzo "Enzo" Palumbo',
    "Memphis Garrett": 'Robert "Memphis" Garrett',
    "Rockstar Lantry": 'Angie "Rockstar" Lantry',
    "Chris Williams": 'Christopher "Swaggy C" Williams',
    "Frenchie French": 'Brandon "Frenchie" French',
    "Pooch Pucciarelli": 'Joseph "Pooch" Pucciarelli',
    "Ashley I": "Ashley Iocco",
    "T'kor Clottey": "Dinah T'kor Clottey",
    "Will Williams": 'Cliffton "Will" Williams',
    "Zae Frederich": 'Isaiah "Zae" Frederich',
}

catalog = json.loads(DATA.read_text())
years = {season["number"]: season["year"] for season in catalog["seasons"]}

for player in catalog["houseguests"]:
    full_name = FULL_NAME_CORRECTIONS.get(player["person_key"], player["person_key"])
    player["person_key"] = full_name
    player["bio"] = (
        f"{full_name} competed on Big Brother {player['season']} in "
        f"{years[player['season']]}. This profile currently focuses on sourced "
        "competition results."
    )

DATA.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")

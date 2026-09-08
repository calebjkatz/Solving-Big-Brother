"""Add the sourced BB28 roster and competition history through Barrett's HOH win."""
import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data" / "us_recurring_competitions.json"
SOURCE = "https://bigbrother.fandom.com/wiki/Big_Brother_28_(US)"

roster = [
    ("Angela", "Angela Murray", "2/24/US28_Small_Angela.jpg", "20260710012426"),
    ("Barrett", "Barrett Pfeiffer", "7/7c/US28_Small_Barrett.jpg", "20260707171003"),
    ("Dee", "Dee Valladares", "1/11/US28_Small_Dee.jpg", "20260711020009"),
    ("Devens", "Rick Devens", "5/5f/US28_Small_Devens.jpg", "20260710012752"),
    ("Drew", "Drew Campbell", "8/88/US28_Small_Drew.jpg", "20260707172041"),
    ("Melody", "Melody Morris", "9/99/US28_Small_Melody.jpg", "20260707174118"),
    ("Taylor", "Taylor Brown", "9/98/US28_Small_Taylor.jpg", "20260707174628"),
    ("Yash", "Yash Patel", "8/83/US28_Small_Yash.jpg", "20260707174851"),
    ("LaTrice", "LaTrice Verrett", "0/06/US28_Small_LaTrice.jpg", "20260707173249"),
    ("Haley", "Haley Thogmartin", "d/d9/US28_Small_Haley.jpg", "20260707172350"),
    ("Mallory", "Mallory Aurichio", "9/99/US28_Small_Mallory.jpg", "20260707173626"),
    ("Kamu", "Kamu Kirk", "c/c0/US28_Small_Kamu.jpg", "20260707173054"),
    ("Chuk", "Chuk Anyanwu", "c/c6/US28_Small_Chuk.jpg", "20260707171909"),
    ("Lyric", "Lyric Medeiros", "4/46/US28_Small_Lyric.jpg", "20260707173442"),
    ("Jason", "Jason De Puy", "c/c7/US28_Small_Jason.jpg", "20260707172712"),
    ("Rome", "Rome Seymour", "0/08/US28_Small_Rome.jpg", "20260707174317"),
    ("Ashley", "Ashley Trail", "d/dc/US28_Small_Ashley.jpg", "20260707170756"),
]

# week, day, type, family, variation, result, credited winners
events = [
    (1, 1, "Immunity qualifier", "Find the BB-tonium", "Find the BB-tonium", "Ashley & Barrett fail to advance", []),
    (1, 1, "Immunity", "1988 Long Beach, CA", "1988 Long Beach, CA", "Rome wins Safety", ["Rome"]),
    (1, 1, "Immunity", "2018 Fiji", "2018 Fiji", "Chuk wins Safety", ["Chuk"]),
    (1, 1, "Immunity", "2010 Las Vegas, NV", "2010 Las Vegas, NV", "Jason wins Safety", ["Jason"]),
    (1, 1, "HOH", "175 Million BC", "175 Million BC", "Dee wins HOH", ["Dee"]),
    (1, 5, "POV", "Back From the Future", "Back From the Future", "Mallory wins the Veto", ["Mallory"]),
    (1, 10, "Block Buster", "Do Over", "Do Over", "Yash is saved", ["Yash"]),
    (2, 10, "HOH", "Achy Breaky HOH", "Achy Breaky HOH", "Devens wins HOH", ["Devens"]),
    (2, 11, "Time Capsule", "BB Time Capsule", "BB Time Capsule", "Angela is punished", []),
    (2, 12, "POV", "Flower Power", "Flower Power", "Devens wins the Veto", ["Devens"]),
    (2, 17, "Block Buster", "Pirate's Booty", "Pirate's Booty", "Jason is saved", ["Jason"]),
    (3, 17, "HOH", "Wrestlegasm 85", "Wrestlegasm 85", "Kamu wins HOH", ["Kamu"]),
    (3, 18, "Time Capsule", "BB Time Capsule", "BB Time Capsule", "Devens is rewarded", []),
    (3, 19, "POV", "Bowlerina", "The Pickle Ball", "Lyric wins the Veto", ["Lyric"]),
    (3, 24, "Block Buster", "Video Tape Tumble", "Video Tape Tumble", "Mallory is saved", ["Mallory"]),
    (4, 24, "HOH", "Jack the Ripper", "Jack the Ripper", "Haley wins HOH", ["Haley"]),
    (4, 25, "Time Capsule", "BB Time Capsule", "BB Time Capsule", "Dee is rewarded", []),
    (4, 26, "POV", "Murder at the Masquerade", "Murder at the Masquerade", "Taylor wins the Veto", ["Taylor"]),
    (4, 31, "Block Buster", "The Paw Patrol Dino Puzzle", "The Paw Patrol Dino Puzzle", "Drew is saved", ["Drew"]),
    (5, 31, "HOH", "The Wall", "Sasquatch Watch", "LaTrice wins HOH", ["LaTrice"]),
    (5, 32, "Time Capsule", "BB Time Capsule", "BB Time Capsule", "Mallory is punished", []),
    (5, 33, "POV", "Saturday Night Veto", "Saturday Night Veto", "Kamu wins the Veto", ["Kamu"]),
    (5, 38, "Block Buster", "Newton's Apples", "Newton's Apples", "Haley is saved", ["Haley"]),
    (6, 38, "HOH", "Knockout", "Bugs in the System", "Yash wins HOH", ["Yash"]),
    (6, 39, "Time Capsule", "BB Time Capsule", "BB Time Capsule", "Melody is punished", []),
    (6, 40, "POV", "OTEV", "OTEV the Belligerent B-Movie Blob", "Yash wins the Veto", ["Yash"]),
    (6, 45, "Block Buster", "Space Race", "Space Race", "Angela is saved", ["Angela"]),
    (7, 45, "HOH", "Norse By Norsewest", "Norse By Norsewest", "Dee wins HOH", ["Dee"]),
    (7, 46, "Time Capsule", "BB Time Capsule", "BB Time Capsule", "Drew is rewarded", []),
    (7, 47, "POV", "Feel The Burn", "Feel The Burn", "LaTrice wins the Veto", ["LaTrice"]),
    (7, 52, "Block Buster", "BB Grand Cliptacular", "BB Grand Cliptacular", "Drew is saved", ["Drew"]),
    (8, "52-53", "Immunity", "Stones of Safety", "Stones of Safety", "Dee wins Safety", ["Dee"]),
    (8, "52-53", "Hit The Road", "Fit the Crops", "Fit the Crops", "Drew wins Safety", ["Drew"]),
    (8, "52-53", "Hit The Road", "Deliver the Grapes", "Deliver the Grapes", "Barrett wins Safety", ["Barrett"]),
    (8, "52-53", "Hit The Road", "Adorn the Crown", "Adorn the Crown", "Yash wins Safety", ["Yash"]),
    (8, 53, "HOH", "2026: A Zing Odyssey", "2026: A Zing Odyssey", "Drew wins HOH", ["Drew"]),
    (8, 54, "POV", "The Gold, the Bad, and the Ugly", "The Gold, the Bad, and the Ugly", "Yash wins the Veto", ["Yash"]),
    (8, 59, "Block Buster", "Your Game in Ruins", "Your Game in Ruins", "Devens is saved", ["Devens"]),
    (9, 59, "HOH", "Rainbow Rollers", "Rainbow Rollers", "Barrett wins HOH", ["Barrett"]),
]

catalog = json.loads(DATA.read_text())
catalog["scope"] = "Big Brother US civilian seasons 2-28 (season 28 through Barrett's Week 9 HOH win)"
catalog["seasons"] = [s for s in catalog["seasons"] if s["number"] != 28]
catalog["seasons"].append({"number": 28, "year": 2026, "title": "Big Brother 28"})

catalog["houseguests"] = [h for h in catalog["houseguests"] if h["season"] != 28]
for short, full, image_path, stamp in roster:
    catalog["houseguests"].append({
        "name": short,
        "season": 28,
        "bio": f"{full} competed on Big Brother 28 in 2026. This profile currently covers results through Barrett's Week 9 HOH win.",
        "strengths": "Competition strengths will be assessed as more sourced results become available.",
        "weaknesses": "No evidence-backed weaknesses have been recorded yet.",
        "notes": "Roster membership and memory-wall image sourced from the season page.",
        "image_url": f"https://static.wikia.nocookie.net/bigbrother/images/{image_path}/revision/latest/scale-to-width-down/300?cb={stamp}",
        "image_source": SOURCE,
        "person_key": full,
        "profile_url": f"https://bigbrother.fandom.com/wiki/{full.replace(' ', '_')}",
    })

catalog["appearances"] = [a for a in catalog["appearances"] if a["season"] != 28]
known = {c["name"] for c in catalog["competitions"]}
for index, (week, day, kind, family, variation, result, winners) in enumerate(events, 1):
    if family not in known:
        catalog["competitions"].append({"name": family, "seasons": [28], "source_url": SOURCE})
        known.add(family)
    else:
        for competition in catalog["competitions"]:
            if competition["name"] == family:
                competition["seasons"] = sorted(set(competition.get("seasons", [])) | {28})
                break
    catalog["appearances"].append({
        "competition": family, "season": 28, "week": str(week), "day": str(day),
        "type": kind, "variation": variation, "result": result,
        "winners": winners, "event_key": f"bb28-event-{index:02d}",
    })

DATA.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")

"""Add primary Big Brother Wiki images to competition-family records."""
import argparse
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "us_recurring_competitions.json"
API = "https://bigbrother.fandom.com/api.php"


def query_images(titles):
    query = urllib.parse.urlencode({
        "action": "query",
        "titles": "|".join(titles),
        "prop": "pageimages|info",
        "pithumbsize": 800,
        "inprop": "url",
        "redirects": 1,
        "format": "json",
    })
    request = urllib.request.Request(
        f"{API}?{query}", headers={"User-Agent": "BigBrotherStatsResearch/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["query"]


def image_results(titles):
    result = query_images(titles)
    redirects = {row["from"]: row["to"] for row in result.get("redirects", [])}
    normalized = {row["from"]: row["to"] for row in result.get("normalized", [])}
    pages = {page.get("title", "").casefold(): page
             for page in result.get("pages", {}).values()}
    matches = {}
    for title in titles:
        resolved = normalized.get(title, title)
        resolved = redirects.get(resolved, resolved)
        page = pages.get(resolved.casefold())
        if page and page.get("thumbnail", {}).get("source"):
            matches[title] = page
    return matches


def search_image(titles):
    for title in titles:
        query = urllib.parse.urlencode({
            "action": "query",
            "generator": "search",
            "gsrsearch": f'"{title}"',
            "gsrnamespace": 6,
            "gsrlimit": 3,
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        })
        request = urllib.request.Request(
            f"{API}?{query}", headers={"User-Agent": "BigBrotherStatsResearch/1.0"}
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                pages = json.load(response).get("query", {}).get("pages", {})
        except Exception:
            continue
        wanted = "".join(character for character in title.casefold() if character.isalnum())
        for page in sorted(pages.values(), key=lambda item: item.get("index", 999)):
            file_title = page.get("title", "").removeprefix("File:")
            candidate = "".join(character for character in file_title.casefold()
                                if character.isalnum())
            imageinfo = page.get("imageinfo", [])
            if wanted and wanted in candidate and imageinfo:
                return {
                    "image_url": imageinfo[0]["url"],
                    "image_source": imageinfo[0]["descriptionurl"],
                }
    return None


def main():
    catalog = json.loads(DATA.read_text())
    records = catalog["competitions"]
    by_title = {urllib.parse.unquote(item["source_url"].rsplit("/", 1)[-1]).replace("_", " "): item
                for item in records}
    found = 0
    for start in range(0, len(by_title), 40):
        titles = list(by_title)[start:start + 40]
        for title, page in image_results(titles).items():
            item = by_title[title]
            item["image_url"] = page["thumbnail"]["source"]
            item["image_source"] = page.get("fullurl", item["source_url"])
            found += 1

    # Many format names are index labels rather than standalone wiki pages.
    # Use the first sourced season variation that has its own page image.
    candidates = defaultdict(list)
    records_by_name = {item["name"]: item for item in records}
    for appearance in catalog["appearances"]:
        item = records_by_name[appearance["competition"]]
        if not item.get("image_url") and appearance["variation"] not in candidates[item["name"]]:
            candidates[item["name"]].append(appearance["variation"])
    variation_titles = list(dict.fromkeys(
        title for titles in candidates.values() for title in titles
    ))
    variation_images = {}
    for start in range(0, len(variation_titles), 40):
        titles = variation_titles[start:start + 40]
        variation_images.update(image_results(titles))
    for family, titles in candidates.items():
        for title in titles:
            page = variation_images.get(title)
            if page:
                item = records_by_name[family]
                item["image_url"] = page["thumbnail"]["source"]
                item["image_source"] = page.get("fullurl", item["source_url"])
                found += 1
                break

    remaining = [item for item in records if not item.get("image_url")]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(search_image, [item["name"], *candidates.get(item["name"], [])]): item
            for item in remaining
        }
        for future in as_completed(futures):
            image = future.result()
            if image:
                futures[future].update(image)
                found += 1
    DATA.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    print(f"Added sourced images to {found}/{len(records)} competition families")


if __name__ == "__main__":
    main()

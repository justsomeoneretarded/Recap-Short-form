"""Phase 0: how much story detail can we get for a movie name, and from where?

Records per film: Wikipedia plot length (and saves the text), TMDB matches/videos/cast (when
TMDB_READ_TOKEN is set), OpenSubtitles availability and one full subtitle download (when
OPENSUBTITLES_API_KEY is set), and whether IMSDb has a screenplay.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import USER_AGENT, films, out_dir, slug, write_report  # noqa: E402

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT
WIKI = "https://en.wikipedia.org/w/api.php"


def wikipedia(film: dict, directory: Path) -> dict:
    query = f"{film['title']} {film['year']} film"
    search = SESSION.get(WIKI, params={"action": "query", "list": "search", "srsearch": query, "srlimit": 3,
                                       "format": "json"}, timeout=30).json()
    hits = [h["title"] for h in search.get("query", {}).get("search", [])]
    if not hits:
        return {"found": False}
    page = hits[0]
    data = SESSION.get(WIKI, params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": page,
                                     "format": "json", "redirects": 1}, timeout=30).json()
    text = next(iter(data["query"]["pages"].values())).get("extract", "")
    match = re.search(r"\n==\s*Plot\s*==\n(.*?)(?=\n==[^=])", text, re.S)
    plot = match.group(1).strip() if match else ""
    (directory / f"{slug(film['title'])}-wikipedia-plot.txt").write_text(plot)
    return {"found": True, "page": page, "other_hits": hits[1:], "plot_words": len(plot.split()),
            "plot_paragraphs": len([p for p in plot.split("\n") if p.strip()])}


def tmdb(film: dict) -> dict:
    token = os.environ.get("TMDB_READ_TOKEN", "").strip()
    if not token:
        return {"skipped": "TMDB_READ_TOKEN not set"}
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    base = "https://api.themoviedb.org/3"
    found = SESSION.get(f"{base}/search/movie", headers=headers, timeout=30,
                        params={"query": film["title"], "year": film["year"]}).json().get("results", [])
    if not found:
        return {"found": False}
    movie_id = found[0]["id"]
    details = SESSION.get(f"{base}/movie/{movie_id}", headers=headers, timeout=30,
                          params={"append_to_response": "videos,credits,keywords,images",
                                  "include_image_language": "en,null"}).json()
    videos = details.get("videos", {}).get("results", [])
    types: dict[str, int] = {}
    for video in videos:
        types[video.get("type", "?")] = types.get(video.get("type", "?"), 0) + 1
    cast = details.get("credits", {}).get("cast", [])
    return {"found": True, "id": movie_id, "title": details.get("title"), "imdb_id": details.get("imdb_id"),
            "results_for_query": len(found), "video_types": types,
            "clip_titles": [v.get("name") for v in videos if v.get("type") == "Clip"][:10],
            "cast_with_photos": sum(1 for c in cast[:15] if c.get("profile_path")),
            "keywords": [k["name"] for k in details.get("keywords", {}).get("keywords", [])][:15],
            "backdrops": len(details.get("images", {}).get("backdrops", []))}


def opensubtitles(film: dict, imdb_id: str | None, directory: Path, allow_download: bool) -> dict:
    key = os.environ.get("OPENSUBTITLES_API_KEY", "").strip()
    if not key:
        return {"skipped": "OPENSUBTITLES_API_KEY not set"}
    headers = {"Api-Key": key, "User-Agent": USER_AGENT, "Accept": "application/json"}
    params = {"languages": "en", "order_by": "download_count"}
    if imdb_id:
        params["imdb_id"] = imdb_id.removeprefix("tt").lstrip("0")
    else:
        params.update(query=film["title"], year=film["year"])
    response = SESSION.get("https://api.opensubtitles.com/api/v1/subtitles", headers=headers, params=params, timeout=30)
    if response.status_code != 200:
        return {"status": response.status_code, "error": response.text[:300]}
    rows = response.json().get("data", [])
    result = {"results": len(rows), "top": [
        {"release": r["attributes"].get("release"), "downloads": r["attributes"].get("download_count"),
         "hearing_impaired": r["attributes"].get("hearing_impaired"),
         "machine_translated": r["attributes"].get("machine_translated")} for r in rows[:3]]}
    if rows and allow_download:
        file_id = rows[0]["attributes"]["files"][0]["file_id"]
        link = SESSION.post("https://api.opensubtitles.com/api/v1/download", headers=headers,
                            json={"file_id": file_id}, timeout=30)
        result["download_status"] = link.status_code
        if link.status_code == 200:
            body = link.json()
            result["remaining_downloads"] = body.get("remaining")
            srt = SESSION.get(body["link"], timeout=60).text
            (directory / f"{slug(film['title'])}.srt").write_text(srt)
            cues = re.findall(r"\d\d:\d\d:\d\d,\d\d\d --> ", srt)
            result.update(subtitle_cues=len(cues), subtitle_words=len(re.sub(r"[\d:,\->\n]+", " ", srt).split()))
        else:
            result["download_error"] = link.text[:300]
    return result


_IMSDB_INDEX: list[str] = []


def _norm(text: str) -> str:
    text = re.sub(r"^(the|a|an)\s+(.*)$", r"\2, \1", text.strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def imsdb(film: dict, directory: Path) -> dict:
    """IMSDb names scripts like 'Dark Knight, The'; look the title up in its full index."""
    if not _IMSDB_INDEX:
        page = SESSION.get("https://imsdb.com/all-scripts.html", timeout=60).text
        _IMSDB_INDEX.extend(re.findall(r'href="/Movie Scripts/([^"]+?) Script\.html"', page))
    wanted = {_norm(film["title"]), _norm(film["short"])}
    names = [n for n in _IMSDB_INDEX if _norm(n) in wanted]
    if not names:
        return {"index_size": len(_IMSDB_INDEX), "listed": False, "screenplay_words": 0}
    url = "https://imsdb.com/scripts/" + names[0].replace(" ", "-") + ".html"
    try:
        response = SESSION.get(url, timeout=30)
    except requests.RequestException as exc:
        return {"url": url, "error": str(exc)[:200]}
    match = re.search(r"<pre>(.*?)</pre>", response.text, re.S | re.I)
    body = re.sub(r"<[^>]+>", "", match.group(1)) if match else ""
    if body:
        (directory / f"{slug(film['title'])}-screenplay.txt").write_text(body)
    return {"url": url, "status": response.status_code, "screenplay_words": len(body.split())}


def imsdb_cell(row: dict) -> str:
    if row.get("error"):
        return "error: " + row["error"][:60]
    if row.get("listed") is False:
        return f"not listed (index {row.get('index_size')})"
    return f"{row.get('screenplay_words', 0)} (HTTP {row.get('status')})"


def main() -> None:
    directory = out_dir("research")
    report = {"films": []}
    for index, film in enumerate(films()):
        entry = {"film": film["title"], "year": film["year"]}
        for name, fn in (("wikipedia", lambda: wikipedia(film, directory)), ("tmdb", lambda: tmdb(film)),
                         ("imsdb", lambda: imsdb(film, directory))):
            try:
                entry[name] = fn()
            except Exception as exc:  # noqa: BLE001
                entry[name] = {"error": str(exc)[:300]}
        try:
            # Download a full subtitle for the first two films only: free accounts have a small daily quota.
            entry["opensubtitles"] = opensubtitles(film, entry.get("tmdb", {}).get("imdb_id"), directory, index < 2)
        except Exception as exc:  # noqa: BLE001
            entry["opensubtitles"] = {"error": str(exc)[:300]}
        report["films"].append(entry)
        time.sleep(1)
    lines = ["## Phase 0 · Story-detail probe", "",
             "| Film | Wikipedia plot words | TMDB clips | Cast photos | OpenSubtitles | Subtitle cues | IMSDb screenplay words |",
             "|---|---|---|---|---|---|---|"]
    for e in report["films"]:
        t, o = e.get("tmdb", {}), e.get("opensubtitles", {})
        lines.append(f"| {e['film']} | {e.get('wikipedia', {}).get('plot_words', '–')} | "
                     f"{t.get('video_types', {}).get('Clip', t.get('skipped', t.get('error', '–')))} | "
                     f"{t.get('cast_with_photos', '–')} | {o.get('results', o.get('skipped', o.get('error', '–')))} | "
                     f"{o.get('subtitle_cues', '–')} | {imsdb_cell(e.get('imsdb', {}))} |")
    write_report(directory, report, lines)


if __name__ == "__main__":
    main()

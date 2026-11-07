"""Movie research from a movie name alone.

Sources, each recorded with provenance:
- TMDB (required, TMDB_READ_TOKEN): identity, cast with photos, keywords, official clips, stills.
- Wikipedia (keyless): the Plot section, used as background (who, why, stakes).
- OpenSubtitles (optional, OPENSUBTITLES_API_KEY): the full English subtitle file, the
  detailed source used to place YouTube clips inside the movie and to read what happens
  around them.

Results are cached per movie under the work directory, so reruns do not spend API quota.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import requests

USER_AGENT = "RecapShorts/0.2 (+https://github.com/justsomeoneretarded/Recap-Short-form)"
TMDB = "https://api.themoviedb.org/3"
TMDB_IMAGES = "https://image.tmdb.org/t/p/"
WIKI = "https://en.wikipedia.org/w/api.php"
OPENSUBTITLES = "https://api.opensubtitles.com/api/v1"
RESEARCH_VERSION = 3  # +1: identity check


class ResearchError(RuntimeError):
    """A required research source failed in a way the user should hear about."""


@dataclass(frozen=True)
class MovieQuery:
    title: str
    year: int | None = None
    # 'Nobody 2021' may mean the 2021 film or a title ending in a number ('Blade Runner 2049',
    # 'Wonder Woman 1984'). The full text is searched first; this split is the fallback.
    split: tuple[str, int] | None = None

    @property
    def label(self) -> str:
        return f"{self.title} ({self.year})" if self.year else self.title


def parse_movie(text: str) -> MovieQuery:
    """'John Wick: Chapter 3 (2019)' → title + year; the year is optional."""
    text = " ".join(str(text or "").split())
    if not text:
        raise ValueError("Enter a movie name, optionally with its year, e.g. 'Nobody (2021)'.")
    match = re.fullmatch(r"(.+?)\s*[\(\[]\s*((?:19|20)\d\d)\s*[\)\]]", text)
    if match:
        return MovieQuery(match.group(1).strip(" -–:"), int(match.group(2)))
    bare = re.fullmatch(r"(.+?)\s+((?:19|20)\d\d)", text)
    return MovieQuery(text, split=(bare.group(1).strip(" -–:"), int(bare.group(2))) if bare else None)


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "movie"


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


class Http:
    """Small requests wrapper with retries for transient failures (429/5xx/timeouts)."""

    def __init__(self, session: requests.Session | None = None, attempts: int = 3, pause: float = 2.0):
        self.session = session or requests.Session()
        # requests ships its own default User-Agent, so setdefault would keep "python-requests/x",
        # which Wikipedia refuses (HTTP 403, robot policy).
        self.session.headers["User-Agent"] = USER_AGENT
        self.attempts, self.pause = attempts, pause

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", 30)
        last: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code in (429, 500, 502, 503, 504) and attempt + 1 < self.attempts:
                    time.sleep(self.pause * (attempt + 1))
                    continue
                return response
            except requests.RequestException as exc:
                last = exc
                time.sleep(self.pause * (attempt + 1))
        raise ResearchError(f"Network request failed for {url.split('?')[0]}: {last}")

    def json(self, method: str, url: str, **kwargs) -> dict:
        response = self.request(method, url, **kwargs)
        if response.status_code != 200:
            raise ResearchError(f"{url.split('?')[0]} returned HTTP {response.status_code}: {response.text[:200]}")
        return response.json()


# --------------------------------------------------------------------------- TMDB

def _year(date: str | None) -> int | None:
    return int(date[:4]) if date and re.match(r"\d{4}", date) else None


def choose_tmdb_result(results: list[dict], query: MovieQuery) -> dict | None:
    """First result whose title matches and, when a year is given, whose year is within one.

    TMDB's own order is kept (as in Top10-Movies); an exact-year match wins over an
    adjacent-year one, which covers festival premieres a year before release.
    """
    wanted = _fold(query.title)
    def title_ok(row: dict) -> bool:
        names = {_fold(row.get("title", "")), _fold(row.get("original_title", ""))}
        return any(n == wanted or n.startswith(wanted + " ") or wanted.startswith(n + " ") for n in names if n) \
            or wanted in names
    exact_titles = [r for r in results if wanted in {_fold(r.get("title", "")), _fold(r.get("original_title", ""))}]
    titled = exact_titles or [r for r in results if title_ok(r)] or results
    if query.year is None:
        return titled[0] if titled else None
    exact = [r for r in titled if _year(r.get("release_date")) == query.year]
    near = [r for r in titled if _year(r.get("release_date")) in (query.year - 1, query.year + 1)]
    return (exact or near or [None])[0]


def tmdb_movie(query: MovieQuery, http: Http, token: str) -> dict:
    if not token:
        raise ResearchError("TMDB_READ_TOKEN is not set. Add the TMDB read access token as a repository secret.")
    headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
    params = {"query": query.title, "include_adult": "false", "language": "en-US"}
    results = http.json("GET", f"{TMDB}/search/movie", headers=headers, params=params).get("results", [])
    if query.year and not choose_tmdb_result(results, query):
        results += http.json("GET", f"{TMDB}/search/movie", headers=headers,
                             params={**params, "year": query.year}).get("results", [])
    chosen = choose_tmdb_result(results, query)
    exact_title = chosen and _fold(query.title) in {_fold(chosen.get("title", "")), _fold(chosen.get("original_title", ""))}
    if query.split and not exact_title:
        split = MovieQuery(*query.split)
        more = http.json("GET", f"{TMDB}/search/movie", headers=headers, params={**params, "query": split.title}).get("results", [])
        chosen = choose_tmdb_result(more, split) or chosen
        results = more + results
    if not chosen:
        raise ResearchError(f"TMDB has no movie matching {query.label}. Check the spelling or add the year.")
    details = http.json("GET", f"{TMDB}/movie/{chosen['id']}", headers=headers, params={
        "append_to_response": "videos,credits,keywords,images,external_ids",
        "include_image_language": "en,null", "language": "en-US"})
    return summarise_tmdb(details, alternatives=[r for r in results if r.get("id") != chosen["id"]][:3])


def summarise_tmdb(details: dict, alternatives: list[dict] | None = None) -> dict:
    credits = details.get("credits", {})
    cast = [{"name": c.get("name"), "character": c.get("character"), "order": c.get("order"),
             "photo": f"{TMDB_IMAGES}w185{c['profile_path']}" if c.get("profile_path") else None}
            for c in credits.get("cast", [])[:15]]
    crew = credits.get("crew", [])
    videos = details.get("videos", {}).get("results", [])
    def video(v: dict) -> dict:
        return {"key": v.get("key"), "name": v.get("name"), "type": v.get("type"), "site": v.get("site"),
                "official": v.get("official"), "url": f"https://www.youtube.com/watch?v={v['key']}"}
    youtube = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
    images = details.get("images", {})
    return {
        "tmdb_id": details.get("id"),
        "imdb_id": details.get("imdb_id") or details.get("external_ids", {}).get("imdb_id"),
        "title": details.get("title"), "original_title": details.get("original_title"),
        "year": _year(details.get("release_date")), "release_date": details.get("release_date"),
        "runtime_minutes": details.get("runtime"), "overview": details.get("overview"),
        "tagline": details.get("tagline"), "genres": [g["name"] for g in details.get("genres", [])],
        "keywords": [k["name"] for k in details.get("keywords", {}).get("keywords", [])][:25],
        "original_language": details.get("original_language"),
        "cast": cast,
        "directors": [c.get("name") for c in crew if c.get("job") == "Director"],
        # Only studio scene clips: featurettes and behind-the-scenes cut to interviews.
        "clips": [video(v) for v in youtube if v.get("type") == "Clip"],
        "trailers": [video(v) for v in youtube if v.get("type") in ("Trailer", "Teaser")],
        "backdrops": [f"{TMDB_IMAGES}w1280{b['file_path']}" for b in images.get("backdrops", [])[:30]],
        "poster": f"{TMDB_IMAGES}w780{details['poster_path']}" if details.get("poster_path") else None,
        "alternatives": [{"id": a.get("id"), "title": a.get("title"), "release_date": a.get("release_date")}
                         for a in alternatives or []],
    }


# --------------------------------------------------------------------- Wikipedia

def plot_section(extract: str) -> str:
    match = re.search(r"\n==\s*(?:Plot|Synopsis|Plot summary)\s*==\n(.*?)(?=\n==[^=]|\Z)", "\n" + extract, re.S)
    return re.sub(r"\n{3,}", "\n\n", match.group(1)).strip() if match else ""


def wikipedia_plot(movie: dict, http: Http) -> dict:
    """Find the film's article (title + year + 'film') and return its Plot section."""
    title, year = movie["title"], movie.get("year")
    hits = http.json("GET", WIKI, params={"action": "query", "list": "search", "format": "json", "srlimit": 5,
                                          "srsearch": f"{title} {year or ''} film".strip()})
    candidates = [h["title"] for h in hits.get("query", {}).get("search", [])]
    wanted = _fold(title)
    skipped: list[str] = []
    for page in candidates:
        if wanted.split()[0] not in _fold(page):
            skipped.append(f"{page}: title differs")
            continue
        data = http.json("GET", WIKI, params={"action": "query", "prop": "extracts", "explaintext": 1,
                                              "redirects": 1, "format": "json", "titles": page})
        extract = next(iter(data.get("query", {}).get("pages", {}).values()), {}).get("extract", "")
        intro = extract[:600]
        if year and str(year) not in intro and str(year - 1) not in intro:
            skipped.append(f"{page}: year {year} not in intro")
            continue  # same name, different film
        plot = plot_section(extract)
        if not plot:
            skipped.append(f"{page}: no Plot section ({len(extract)} chars)")
        if plot:
            return {"page": page, "url": f"https://en.wikipedia.org/wiki/{page.replace(' ', '_')}",
                    "plot": plot, "words": len(plot.split())}
    return {"page": None, "plot": "", "words": 0, "candidates": skipped or candidates}


# ------------------------------------------------------------------ OpenSubtitles

def choose_subtitle(rows: list[dict]) -> dict | None:
    """Most-downloaded human subtitle; avoid machine translations, AI output and foreign-parts-only files."""
    def score(row: dict) -> tuple:
        a = row.get("attributes", {})
        return (not a.get("machine_translated"), not a.get("ai_translated"), not a.get("foreign_parts_only"),
                not a.get("hearing_impaired"), a.get("download_count") or 0)
    usable = [r for r in rows if r.get("attributes", {}).get("files")]
    return max(usable, key=score) if usable else None


def opensubtitles_file(movie: dict, http: Http, key: str, target: Path) -> dict:
    if target.exists() and target.stat().st_size > 1000:
        return {"path": str(target), "cached": True}
    if not key:
        return {"skipped": "OPENSUBTITLES_API_KEY not set"}
    headers = {"Api-Key": key, "User-Agent": USER_AGENT, "Accept": "application/json"}
    params = {"languages": "en", "order_by": "download_count"}
    if movie.get("imdb_id"):
        params["imdb_id"] = str(movie["imdb_id"]).removeprefix("tt").lstrip("0")
    else:
        params.update(query=movie["title"], year=movie.get("year") or "")
    rows = http.json("GET", f"{OPENSUBTITLES}/subtitles", headers=headers, params=params).get("data", [])
    chosen = choose_subtitle(rows)
    if not chosen:
        return {"skipped": "no English subtitle found", "results": len(rows)}
    attributes = chosen["attributes"]
    link = http.request("POST", f"{OPENSUBTITLES}/download", headers=headers,
                        json={"file_id": attributes["files"][0]["file_id"]})
    if link.status_code != 200:
        return {"skipped": f"download refused (HTTP {link.status_code}): {link.text[:160]}", "results": len(rows)}
    body = link.json()
    text = http.request("GET", body["link"], timeout=60).text
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return {"path": str(target), "release": attributes.get("release"), "downloads": attributes.get("download_count"),
            "hearing_impaired": attributes.get("hearing_impaired"), "remaining_quota": body.get("remaining"),
            "results": len(rows)}


# ----------------------------------------------------------------------- research

def identity_check(movie: dict, query: "MovieQuery", subtitles_path: str | None) -> dict:
    """Is this the film the user meant, and do the subtitles belong to it? Titles are shared by
    many films ('Havoc', 'Fractured'): without a year the wrong one is easy to pick; a subtitle
    file from another film or cut would place every clip wrongly."""
    out: dict = {"warnings": []}
    if not query.year:
        out["warnings"].append(f"No year given: picked {movie.get('title')} ({movie.get('year')}); add the year "
                               "if this is the wrong film.")
    runtime = float(movie.get("runtime_minutes") or 0) * 60
    if subtitles_path and runtime:
        try:
            from .locate import MovieTranscript
            cues = MovieTranscript.from_subtitles(Path(subtitles_path).read_text(errors="ignore")).cues
            last = cues[-1].end if cues else 0.0
        except Exception:  # noqa: BLE001 - a broken file is reported, not fatal
            last = 0.0
        out["subtitle_end_minutes"] = round(last / 60, 1)
        # Credits run past the last line, so subtitles end before the runtime; ending far later means
        # another film or a longer cut, far earlier a partial file.
        if last > runtime * 1.08:
            out["subtitles_mismatch"] = True
            out["warnings"].append(f"Subtitles end at {last / 60:.0f} min but the film runs {runtime / 60:.0f} min: "
                                   "they belong to another film or cut and are not used.")
        elif last < runtime * 0.6:  # a partial file still places the clips it covers
            out["warnings"].append(f"Subtitles end at {last / 60:.0f} min of {runtime / 60:.0f}: partial file, "
                                   "later scenes are found by watching.")
    return out


def research(movie_text: str, workdir: Path, *, http: Http | None = None,
             tmdb_token: str | None = None, subtitles_key: str | None = None) -> dict:
    """Resolve the movie and gather its story sources; cached per movie."""
    query = parse_movie(movie_text)
    http = http or Http()
    tmdb_token = os.environ.get("TMDB_READ_TOKEN", "") if tmdb_token is None else tmdb_token
    subtitles_key = os.environ.get("OPENSUBTITLES_API_KEY", "") if subtitles_key is None else subtitles_key
    movie = tmdb_movie(query, http, tmdb_token.strip())
    folder = Path(workdir) / "research" / f"{slug(movie['title'])}-{movie.get('year') or 'unknown'}"
    cache = folder / "research.json"
    if cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached.get("version") == RESEARCH_VERSION and cached.get("movie", {}).get("tmdb_id") == movie["tmdb_id"]:
            complete = cached.get("wikipedia", {}).get("words") and (cached.get("subtitles", {}).get("path")
                                                                      or not subtitles_key)
            if complete:
                return cached
    folder.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    try:
        wiki = wikipedia_plot(movie, http)
    except ResearchError as exc:
        wiki = {"page": None, "plot": "", "words": 0, "error": str(exc)}
    if not wiki["plot"]:
        why = wiki.get("error") or f"searched {wiki.get('candidates') or 'no pages'}"
        warnings.append(f"No Wikipedia plot found ({why}); the story will rely on subtitles, clips and the TMDB overview.")
    (folder / "plot.txt").write_text(wiki["plot"] or movie.get("overview") or "", encoding="utf-8")
    try:
        subtitles = opensubtitles_file(movie, http, subtitles_key.strip(), folder / "movie.srt")
    except ResearchError as exc:
        subtitles = {"skipped": str(exc)}
    if not subtitles.get("path"):
        warnings.append(f"No full subtitle file ({subtitles.get('skipped')}); clips cannot be placed by dialogue.")
    identity = identity_check(movie, query, subtitles.get("path"))
    warnings += identity["warnings"]
    if identity.get("subtitles_mismatch"):  # another film's or a very different cut's subtitles: worse than none
        subtitles = {"skipped": "subtitle file does not match the film's runtime", "rejected_path": subtitles.get("path")}
    result = {"identity": identity, "version": RESEARCH_VERSION, "query": {"title": query.title, "year": query.year},
              "movie": movie, "wikipedia": {k: v for k, v in wiki.items() if k != "plot"},
              "plot_path": str(folder / "plot.txt"), "subtitles": subtitles, "warnings": warnings,
              "folder": str(folder)}
    cache.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result

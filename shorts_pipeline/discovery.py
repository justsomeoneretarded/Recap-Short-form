"""Find and rank scene clips for a researched movie, from any YouTube channel.

Pipeline: build queries → search → title/duration prefilter → full metadata → identity check
→ score. Scores combine audience signals (views, likes, subscribers, verified checkmark,
Most Replayed heatmap) with quality (resolution) and are recorded per component, so a run
report can say why each clip was chosen. Heavier checks (burned subtitles, existing
narration, borders) run after download in screening.
"""
from __future__ import annotations

import math
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .compilations import description_chapters

# Words that mark a video as something other than a clean scene of the film.
REJECT_TITLE = re.compile(
    r"\b(trailer|teaser|tv spot|promo|review|reaction|reacts?|explained|explain|recap|summary|ending|"
    r"breakdown|analysis|theory|easter eggs?|behind the scenes|making of|interview|press|premiere|"
    r"edit|amv|fmv|slowed|reverb|sped up|nightcore|lyrics?|soundtrack|ost|theme song|full movie|"
    r"fan ?made|concept|ai generated|parody|spoof|honest|pitch meeting|ranked|ranking|top \d+|"
    r"vs\.? (?:the )?real|in \d+ minutes|movie in|explained in|hindi|tamil|telugu|dubbed|"
    r"#shorts?|bloopers?|deleted scenes?|commentary|podcast|unboxing|gameplay|game|breaks? down|"
    r"experts?|stunt ?(?:man|woman|men|women|coordinator)s?|react(?:ion|s|ing)?|rates?|vfx artists?)\b", re.I)
# Words that mark scene footage.
SCENE_WORDS = {"scene", "scenes", "clip", "clips", "fight", "chase", "final", "opening", "moment", "moments"}
COMPILATION = re.compile(r"\b(all|best|every|top)\b.*\bscenes?\b|\bcompilation\b|\bscenes? pack\b", re.I)
BOT_CHECK = re.compile(r"sign in to confirm|not a bot|confirm you.?re not", re.I)

SCENE_CONCEPTS = {
    "Action": ("fight scene", "chase scene"), "Adventure": ("chase scene",), "Thriller": ("tense scene",),
    "Crime": ("confrontation scene",), "Horror": ("scary scene",), "Science Fiction": ("best scene",),
    "War": ("battle scene",), "Western": ("showdown scene",), "Comedy": ("funny scene",),
    "Drama": ("emotional scene",), "Mystery": ("interrogation scene",), "Fantasy": ("battle scene",),
}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def build_queries(movie: dict, scene_hints: list[str] | None = None, limit: int = 12) -> list[str]:
    """Templates, then studio clip names and plot hints (specific scenes), then genre concepts."""
    title, year = movie["title"], movie.get("year") or ""
    stem = f"{title} {year}".strip()
    queries = [f"{stem} scene", f"{stem} best scenes", f"{stem} clip"]
    # The scenes people talk about most (Gemini + Google Search) come before the generic queries.
    for hint in (scene_hints or [])[:5]:
        queries.append(f"{title} {hint} scene")
    for clip in movie.get("clips", [])[:6]:
        name = re.sub(r"(?i)\b(clip|official|hd|4k|movieclips|\(\d{4}\))\b", " ", clip.get("name", ""))
        name = " ".join(name.replace("|", " ").replace("-", " ").split())
        if name and fold(name) != fold(title):
            queries.append(f"{title} {name}" if fold(title) not in fold(name) else name)
    for hint in (scene_hints or [])[5:]:
        queries.append(f"{title} {hint} scene")
    for genre in movie.get("genres", []):
        for concept in SCENE_CONCEPTS.get(genre, ()):
            queries.append(f"{stem} {concept}")
    queries.append(f"{title} all scenes compilation")
    return list(dict.fromkeys(" ".join(q.split()) for q in queries))[:limit]


def prefilter(entry: dict, movie: dict) -> str | None:
    """Return a reason to drop a search result before fetching its full metadata, else None."""
    title = entry.get("title") or ""
    if REJECT_TITLE.search(title):
        return "title marks non-scene content"
    duration = entry.get("duration") or 0
    if duration and (duration < 20 or duration > 45 * 60):
        return f"duration {int(duration)} s outside 20 s–45 min"
    if entry.get("live_status") in ("is_live", "is_upcoming"):
        return "live or upcoming"
    folded = fold(title)
    words = [w for w in fold(movie["title"]).split() if len(w) > 2] or fold(movie["title"]).split()
    surnames = {fold(c["name"]).split()[-1] for c in movie.get("cast", [])[:8] if c.get("name")}
    if not all(w in folded.split() for w in words) and not surnames & set(folded.split()):
        return "title names neither the film nor its cast"
    return None


def identity(info: dict, movie: dict) -> dict:
    """Evidence that this upload is footage of this film (not a namesake, remake or other film)."""
    text = fold(" ".join(str(info.get(k) or "") for k in ("title", "description")) + " " +
                " ".join(info.get("tags") or []))
    tokens = set(text.split())
    title_words = [w for w in fold(movie["title"]).split() if len(w) > 2] or fold(movie["title"]).split()
    title_hit = all(w in tokens for w in title_words)
    cast = [fold(c["name"]) for c in movie.get("cast", [])[:10] if c.get("name")]
    cast_hits = sorted({name for name in cast if name in text or name.split()[-1] in tokens})
    years = {int(y) for y in re.findall(r"\b(19[2-9]\d|20[0-4]\d)\b", fold(info.get("title")))}
    wrong_year = bool(movie.get("year") and years and not any(abs(y - movie["year"]) <= 1 for y in years))
    ok = title_hit and not wrong_year and (bool(cast_hits) or str(movie.get("year")) in text or not cast)
    return {"ok": ok, "title_hit": title_hit, "cast_hits": cast_hits[:5], "wrong_year": wrong_year}


def best_format(info: dict) -> dict:
    formats = [f for f in info.get("formats") or [] if f.get("vcodec") not in (None, "none") and f.get("height")]
    if not formats:
        return {"height": info.get("height") or 0, "fps": info.get("fps") or 0}
    top = max(formats, key=lambda f: (f.get("height") or 0, f.get("fps") or 0, f.get("tbr") or 0))
    return {"height": top.get("height") or 0, "width": top.get("width"), "fps": top.get("fps") or 0}


_STAMP = re.compile(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b")


def comment_peaks(comments: list[dict], duration: float | None = None) -> list[dict]:
    """Timestamps viewers point at ('2:13 that look'), weighted by comment likes."""
    peaks: dict[int, float] = {}
    for comment in comments:
        for h, m, s in _STAMP.findall(comment.get("text") or ""):
            second = int(h or 0) * 3600 + int(m) * 60 + int(s)
            if duration and second > duration:
                continue
            peaks[second] = peaks.get(second, 0) + 1 + math.log1p(comment.get("like_count") or 0)
    return [{"second": s, "weight": round(w, 2)} for s, w in sorted(peaks.items(), key=lambda x: -x[1])[:8]]


def heatmap_peaks(info: dict, top: int = 3) -> list[dict]:
    heat = sorted(info.get("heatmap") or [], key=lambda h: -(h.get("value") or 0))
    return [{"start": h.get("start_time"), "end": h.get("end_time"), "value": round(h.get("value") or 0, 3)}
            for h in heat[:top]]


def score(info: dict) -> dict:
    """Audience + quality score with components (each roughly 0–1, weights sum to 1)."""
    views = info.get("view_count") or 0
    likes = info.get("like_count") or 0
    subs = info.get("channel_follower_count") or 0
    fmt = best_format(info)
    parts = {
        "views": min(1.0, math.log10(views + 1) / 8),  # 100M views → 1.0
        "subscribers": min(1.0, math.log10(subs + 1) / 7.5),
        "verified": 1.0 if info.get("channel_is_verified") else 0.0,
        "like_ratio": min(1.0, (likes / views) / 0.03) if views > 500 else 0.0,
        "replayed": 1.0 if info.get("heatmap") else 0.0,
        "resolution": min(1.0, (fmt["height"] or 0) / 1080),
    }
    weights = {"views": .30, "subscribers": .15, "verified": .15, "like_ratio": .10, "replayed": .10,
               "resolution": .20}
    total = sum(parts[k] * w for k, w in weights.items())
    if (fmt["height"] or 0) < 720:
        total *= 0.6  # visibly soft once cropped to 9:16
    return {"total": round(total, 4), "parts": {k: round(v, 3) for k, v in parts.items()}}


@dataclass
class Candidate:
    id: str
    title: str
    channel: str | None
    duration: float | None
    url: str
    score: dict
    identity: dict
    signals: dict
    queries: list[str] = field(default_factory=list)
    official: bool = False
    compilation: bool = False

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def candidate(info: dict, movie: dict, query: str, official_ids: set[str]) -> Candidate:
    fmt = best_format(info)
    description = info.get("description") or ""
    return Candidate(
        id=info["id"], title=info.get("title") or "", channel=info.get("channel"), duration=info.get("duration"),
        url=f"https://www.youtube.com/watch?v={info['id']}", score=score(info), identity=identity(info, movie),
        signals={"views": info.get("view_count"), "likes": info.get("like_count"),
                 "subscribers": info.get("channel_follower_count"), "verified": bool(info.get("channel_is_verified")),
                 "heatmap_peaks": heatmap_peaks(info), "chapters": [
                     {"title": c.get("title"), "start": c.get("start_time"), "end": c.get("end_time")}
                     for c in info.get("chapters") or []] or description_chapters(description),
                 "description_timestamps": len(_STAMP.findall(description)),
                 "captions": sorted(set((info.get("subtitles") or {}).keys()) |
                                    ({"en (auto)"} if "en" in (info.get("automatic_captions") or {}) else set())),
                 **fmt},
        queries=[query], official=info["id"] in official_ids,
        compilation=bool(COMPILATION.search(info.get("title") or "")) or len(info.get("chapters") or []) >= 3
        or len(description_chapters(description)) >= 3)


class YouTube:
    """yt-dlp wrapper: direct route first, then the WARP proxy after a bot check."""

    def __init__(self, proxy: str | None = None, cookies: str | None = None, pause: float = 1.0,
                 budget: float | None = None):
        self.proxy = proxy if proxy is not None else os.environ.get("YTDLP_FALLBACK_PROXY", "")
        self.cookies = cookies if cookies is not None else os.environ.get("YOUTUBE_COOKIE_FILE", "")
        self.pause = pause
        # Fail fast like Top10-Movies: short back-off, few retries, then move on to the next clip.
        self.bot_backoff = float(os.environ.get("SHORTS_BOT_BACKOFF", "8"))
        seconds = budget if budget is not None else float(os.environ.get("SHORTS_YOUTUBE_BUDGET", "2700"))
        self.deadline = time.monotonic() + seconds  # no YouTube work after this, so jobs end in time
        self.prefer_proxy = False  # once the direct route is bot-checked, go straight to the proxy
        self.log: list[dict] = []

    @property
    def signed_in(self) -> bool:
        return bool(self.cookies and Path(self.cookies).exists())

    def _options(self, use_proxy: bool, extra: dict) -> dict:
        options = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20,
                   "retries": 2, "fragment_retries": 3, "extractor_retries": 1, **extra}
        if os.environ.get("SHORTS_YTDLP_NODE", "1") != "0":
            # YouTube hides media URLs behind JavaScript challenges; yt-dlp solves them with a JS runtime.
            options.setdefault("js_runtimes", {"node": {}})
        if self.cookies:
            options["cookiefile"] = self.cookies
        if use_proxy and self.proxy:
            options["proxy"] = self.proxy
        return options

    def extract(self, target: str, **extra) -> dict:
        if time.monotonic() > self.deadline:
            raise RuntimeError("YouTube time budget reached; skipped")
        import yt_dlp
        routes = ([True] if self.prefer_proxy else [False]) + ([True] if self.proxy and not self.prefer_proxy else [])
        last = "no route"
        for use_proxy in routes:
            for attempt in range(2):
                if time.monotonic() > self.deadline:
                    raise RuntimeError("YouTube time budget reached; skipped")
                try:
                    with yt_dlp.YoutubeDL(self._options(use_proxy, extra)) as ydl:
                        info = ydl.extract_info(target, download=not extra.get("skip_download", True))
                    self.log.append({"target": target[:90], "proxy": use_proxy, "ok": True})
                    return info
                except Exception as exc:  # noqa: BLE001 - yt-dlp raises many types
                    last = str(exc)
                    bot = bool(BOT_CHECK.search(last))
                    self.log.append({"target": target[:90], "proxy": use_proxy, "ok": False, "bot": bot,
                                     "error": last[:200]})
                    if bot and not use_proxy and self.proxy:
                        self.prefer_proxy = True
                        break
                    if bot:  # the proxy route was challenged too: one short back-off, then give up on this item
                        time.sleep(self.bot_backoff)
                        continue
                    if "unavailable" in last.lower() or "private" in last.lower():
                        raise RuntimeError(last) from exc
                    time.sleep(self.pause * (attempt + 1))
        raise RuntimeError(last)

    def search(self, query: str, count: int = 10) -> list[dict]:
        return self.extract(f"ytsearch{count}:{query}", extract_flat="in_playlist").get("entries") or []

    def info(self, video_id: str) -> dict:
        return self.extract(f"https://www.youtube.com/watch?v={video_id}")

    def comments(self, video_id: str, count: int = 40) -> list[dict]:
        info = self.extract(f"https://www.youtube.com/watch?v={video_id}", getcomments=True,
                            extractor_args={"youtube": {"max_comments": [str(count), "all", "0", "0"],
                                                        "comment_sort": ["top"]}})
        return info.get("comments") or []

    def download(self, video_id: str, folder: Path, max_height: int = 1080) -> Path | None:
        """Best video up to max_height plus audio, merged to MP4 (yt-dlp's own downloader honours the proxy)."""
        folder.mkdir(parents=True, exist_ok=True)
        existing = sorted(folder.glob(f"{video_id}.mp4"))
        if existing:
            return existing[0]
        self.extract(f"https://www.youtube.com/watch?v={video_id}", skip_download=False,
                     format=f"bv*[height<={max_height}]+ba/b[height<={max_height}]", merge_output_format="mp4",
                     outtmpl=str(folder / f"{video_id}.%(ext)s"), max_filesize=600 * 1024 * 1024)
        found = sorted(folder.glob(f"{video_id}.mp4"))
        return found[0] if found else None

    def captions(self, video_id: str, folder: Path) -> Path | None:
        folder.mkdir(parents=True, exist_ok=True)
        self.extract(f"https://www.youtube.com/watch?v={video_id}", writesubtitles=True, writeautomaticsub=True,
                     subtitleslangs=["en", "en-US", "en-GB", "en-orig"], subtitlesformat="vtt",
                     outtmpl=str(folder / video_id), skip_download=True)
        files = sorted(folder.glob(f"{video_id}*.vtt"))
        manual = [f for f in files if re.search(r"\.en(-US|-GB)?\.vtt$", f.name)]
        return (manual or files or [None])[0]


def youtube_workers() -> int:
    """How many YouTube requests run at once (few, so the runner does not look like a bot)."""
    return max(1, int(os.environ.get("SHORTS_YOUTUBE_WORKERS", "3")))


def _parallel(function, items: list) -> list:
    """function(item) for every item, a few at a time, results in input order."""
    from concurrent.futures import ThreadPoolExecutor
    if youtube_workers() == 1 or len(items) < 2:
        return [function(item) for item in items]
    with ThreadPoolExecutor(max_workers=youtube_workers()) as pool:
        return list(pool.map(function, items))


def discover(research: dict, youtube: YouTube, *, scene_hints: list[str] | None = None, per_query: int = 10,
             max_full: int = 30) -> dict:
    """Search, filter and rank candidates. Returns kept candidates (best first) and every rejection."""
    movie = research["movie"]
    official = {c["key"] for c in movie.get("clips", [])}
    queries = build_queries(movie, scene_hints)
    found: dict[str, dict] = {}
    rejected: list[dict] = []
    errors: list[dict] = []
    for key in official:  # studio clips are candidates even if search misses them
        found[key] = {"id": key, "title": "", "query": "tmdb official clip"}
    # Searches and info lookups wait on the network, so a few run at once; results are
    # handled in the original order, so the outcome is the same as one at a time.
    def search(query):
        try:
            return youtube.search(query, per_query), None
        except RuntimeError as exc:
            return [], {"query": query, "error": str(exc)[:200]}

    for query, (entries, error) in zip(queries, _parallel(search, queries)):
        if error:
            errors.append(error)
            continue
        for entry in entries:
            if not entry.get("id") or entry["id"] in found:
                continue
            reason = prefilter(entry, movie)
            if reason:
                rejected.append({"id": entry["id"], "title": entry.get("title"), "reason": reason})
                continue
            found[entry["id"]] = {"id": entry["id"], "title": entry.get("title"), "query": query,
                                  "flat_views": entry.get("view_count") or 0}
    ordered = sorted(found.values(), key=lambda e: (e["id"] not in official, -(e.get("flat_views") or 0)))
    kept: list[Candidate] = []

    def lookup(entry):
        try:
            return youtube.info(entry["id"]), None
        except RuntimeError as exc:
            return None, {"video": entry["id"], "error": str(exc)[:200]}

    chosen = ordered[:max_full]
    for entry, (info, error) in zip(chosen, _parallel(lookup, chosen)):
        if error:
            errors.append(error)
            continue
        reason = prefilter(info, movie) if entry["id"] not in official else None
        fmt = best_format(info)
        if not reason and fmt.get("width") and fmt["width"] < fmt["height"]:
            reason = "vertical re-upload (already cropped; quality and framing lost)"
        if not reason and re.search(r"#\w+", info.get("title") or "") and (info.get("duration") or 0) <= 70:
            reason = "hashtag short (re-upload)"
        item = candidate(info, movie, entry["query"], official)
        if reason or not (item.identity["ok"] or item.official):
            rejected.append({"id": item.id, "title": item.title,
                             "reason": reason or f"identity not confirmed {item.identity}"})
            continue
        kept.append(item)
    # Audience signals decide the order; a studio upload only gets a small trust bonus.
    kept.sort(key=lambda c: c.score["total"] + (0.08 if c.official else 0.0), reverse=True)
    return {"queries": queries, "candidates": [c.as_dict() for c in kept], "rejected": rejected, "errors": errors}

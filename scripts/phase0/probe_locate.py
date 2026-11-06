"""Phase 0: can we find where a YouTube clip sits inside the full movie?

For each film that has a downloaded full subtitle file (from probe_research.py), search a few
clips, fetch each clip's English captions (manual or automatic) and match its words against
the movie's subtitles. Matching 4-word phrases vote for an offset; a clear winner gives the
clip's start time in the movie and the dialogue just before and after it.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import films, out_dir, slug, write_report  # noqa: E402

import yt_dlp  # noqa: E402

PROXY = os.environ.get("YTDLP_FALLBACK_PROXY", "")
CLIPS_PER_FILM = 5
GRAM = 4
TIME = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{3})")


def seconds(match: re.Match) -> float:
    h, m, s, ms = (int(x) for x in match.groups())
    return h * 3600 + m * 60 + s + ms / 1000


def words(text: str) -> list[str]:
    text = re.sub(r"<[^>]+>|\[[^\]]*\]|\([^)]*\)|♪", " ", text.lower())
    return re.findall(r"[a-z0-9']+", text)


def timed_words(subtitle_text: str) -> list[tuple[float, str]]:
    """SRT or VTT → [(time, word)], spreading each cue's words across its duration.

    Rolling auto-captions repeat lines; a word repeated at the same position is dropped.
    """
    rows: list[tuple[float, str]] = []
    for block in re.split(r"\n\s*\n", subtitle_text.replace("\r", "")):
        times = list(TIME.finditer(block))
        if len(times) < 2:
            continue
        start, end = seconds(times[0]), seconds(times[1])
        body = block[times[1].end():]
        body = body.split("\n", 1)[1] if "\n" in body else ""
        cue = words(body)
        for i, word in enumerate(cue):
            rows.append((start + (end - start) * i / max(1, len(cue)), word))
    deduped: list[tuple[float, str]] = []
    for t, w in rows:
        recent = [x[1] for x in deduped[-12:]]
        if len(deduped) >= 1 and w in recent and t - deduped[-1][0] < 0.05:
            continue
        deduped.append((t, w))
    # Remove the exact repeats rolling captions create (the same phrase twice in a row).
    out: list[tuple[float, str]] = []
    for t, w in deduped:
        if len(out) >= 6 and [x[1] for x in out[-6:]] == [x[1] for x in out[-12:-6]]:
            out = out[:-6]
        out.append((t, w))
    return out


def locate(clip: list[tuple[float, str]], movie: list[tuple[float, str]]) -> dict:
    index: dict[tuple, list[float]] = {}
    for i in range(len(movie) - GRAM + 1):
        index.setdefault(tuple(w for _, w in movie[i:i + GRAM]), []).append(movie[i][0])
    votes: Counter = Counter()
    grams = 0
    for i in range(len(clip) - GRAM + 1):
        key = tuple(w for _, w in clip[i:i + GRAM])
        grams += 1
        for movie_time in index.get(key, [])[:5]:
            votes[round((movie_time - clip[i][0]) / 2) * 2] += 1
    if not votes:
        return {"matched": False, "clip_grams": grams}
    offset, hits = votes.most_common(1)[0]
    near = sum(v for k, v in votes.items() if abs(k - offset) <= 4)
    return {"matched": hits >= 3, "movie_offset_seconds": offset, "matching_phrases": near,
            "clip_grams": grams, "share": round(near / max(1, grams), 2)}


def context(movie: list[tuple[float, str]], start: float, end: float, pad: float = 45) -> dict:
    before = " ".join(w for t, w in movie if start - pad <= t < start)
    after = " ".join(w for t, w in movie if end < t <= end + pad)
    return {"before": before[-300:], "after": after[:300]}


def ydl(**extra) -> yt_dlp.YoutubeDL:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 30,
            "retries": 3, "extractor_retries": 3, **extra}
    if PROXY:
        opts["proxy"] = PROXY
    return yt_dlp.YoutubeDL(opts)


def clip_captions(video_id: str, directory: Path) -> tuple[str, str] | None:
    target = directory / video_id
    for attempt in range(2):
        try:
            with ydl(writesubtitles=True, writeautomaticsub=True, subtitleslangs=["en", "en-orig", "en-US"],
                     subtitlesformat="vtt", outtmpl=str(target)) as y:
                y.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            break
        except Exception as exc:  # noqa: BLE001
            if attempt:
                print(f"captions {video_id}: {str(exc)[:200]}", flush=True)
                return None
            time.sleep(5)
    files = sorted(directory.glob(f"{video_id}*.vtt"))
    if not files:
        return None
    manual = [f for f in files if ".en.vtt" in f.name]
    chosen = (manual or files)[0]
    return chosen.read_text(errors="ignore"), chosen.name


def main() -> None:
    directory = out_dir("locate")
    research = Path(os.environ.get("PROBE_RESEARCH", "work/phase0/research"))
    report = {"films": []}
    for film in films():
        srt = research / f"{slug(film['title'])}.srt"
        if not srt.exists():
            continue
        movie = timed_words(srt.read_text(errors="ignore"))
        entry = {"film": film["title"], "movie_words": len(movie), "clips": []}
        try:
            with ydl(extract_flat="in_playlist") as y:
                found = y.extract_info(f"ytsearch8:{film['short']} {film['year']} scene", download=False)
            ids = [e["id"] for e in found.get("entries") or [] if e.get("id")][:CLIPS_PER_FILM]
        except Exception as exc:  # noqa: BLE001
            entry["error"] = str(exc)[:300]
            ids = []
        for video_id in ids:
            got = clip_captions(video_id, directory)
            if not got:
                entry["clips"].append({"id": video_id, "captions": None})
                continue
            text, name = got
            clip = timed_words(text)
            row = {"id": video_id, "captions": name, "clip_words": len(clip), **locate(clip, movie)}
            if row.get("matched") and clip:
                start = row["movie_offset_seconds"] + clip[0][0]
                end = row["movie_offset_seconds"] + clip[-1][0]
                row.update(movie_start=round(start), movie_end=round(end), **context(movie, start, end))
            entry["clips"].append(row)
            time.sleep(2)
        report["films"].append(entry)
    lines = ["## Phase 0 · Locate clips inside the movie", "",
             "| Film | Clip | Caption file | Clip words | Matched | Movie time | Phrase share |",
             "|---|---|---|---|---|---|---|"]
    for e in report["films"]:
        if e.get("error"):
            lines.append(f"| {e['film']} | search failed: {e['error'][:80]} | | | | | |")
        for c in e["clips"]:
            when = (f"{c['movie_start'] // 60}:{c['movie_start'] % 60:02d}–{c['movie_end'] // 60}:{c['movie_end'] % 60:02d}"
                    if c.get("movie_start") is not None else "–")
            lines.append(f"| {e['film']} | {c['id']} | {c.get('captions') or 'none'} | {c.get('clip_words', '–')} | "
                         f"{c.get('matched', '–')} | {when} | {c.get('share', '–')} |")
    if not report["films"]:
        lines.append("No full subtitle files were available from the research probe.")
    write_report(directory, report, lines)


if __name__ == "__main__":
    main()

"""Split compilation videos into scenes and keep only the scenes from our movie.

Boundaries come from, in order: YouTube chapters, timestamps in the description, then long
gaps in the dialogue. Each segment is placed in the movie on its own; segments that do not
match the movie's subtitles (another film in a multi-movie compilation, or silent action)
are kept as "unplaced" for visual matching later, never silently attributed to our film.
"""
from __future__ import annotations

import re

from .locate import MovieTranscript

_LINE_STAMP = re.compile(r"^\s*(?:[-–•▶]\s*)?((?:\d{1,2}:)?\d{1,2}:\d{2})\s*[-–:|)]*\s*(.*)$")


def _seconds(stamp: str) -> int:
    parts = [int(p) for p in stamp.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def description_chapters(description: str) -> list[dict]:
    """'0:00 Intro / 1:23 Library fight …' lines → [{'start', 'title'}], only if they look like chapters."""
    rows = []
    for line in (description or "").splitlines():
        match = _LINE_STAMP.match(line)
        if match:
            rows.append({"start": _seconds(match.group(1)), "title": match.group(2).strip() or None})
    starts = [r["start"] for r in rows]
    if len(rows) < 3 or starts != sorted(starts) or starts[0] > 15:
        return []
    return rows


def segments_from_chapters(chapters: list[dict], duration: float) -> list[dict]:
    segments = []
    for i, chapter in enumerate(chapters):
        start = float(chapter["start"])
        end = float(chapters[i + 1]["start"]) if i + 1 < len(chapters) else float(duration)
        if end - start >= 8:
            segments.append({"start": start, "end": end, "title": chapter.get("title"), "source": "chapters"})
    return segments


def segments_from_dialogue_gaps(words: list[tuple[float, str]], duration: float, gap: float = 6.0,
                                minimum: float = 15.0) -> list[dict]:
    """Fallback: cut where nobody speaks for `gap` seconds; merge pieces shorter than `minimum`."""
    if not words:
        return [{"start": 0.0, "end": float(duration), "title": None, "source": "whole"}]
    cuts = [0.0]
    for (t0, _), (t1, _) in zip(words, words[1:]):
        if t1 - t0 >= gap:
            cuts.append((t0 + t1) / 2)
    cuts.append(float(duration))
    segments = []
    for start, end in zip(cuts, cuts[1:]):
        if segments and (end - start < minimum or segments[-1]["end"] - segments[-1]["start"] < minimum):
            segments[-1]["end"] = end
        else:
            segments.append({"start": start, "end": end, "title": None, "source": "dialogue gaps"})
    return segments


def split(candidate: dict, words: list[tuple[float, str]], description: str = "") -> list[dict]:
    duration = float(candidate.get("duration") or (words[-1][0] + 5 if words else 0))
    chapters = [{"start": c["start"], "title": c.get("title")} for c in candidate["signals"].get("chapters") or []]
    chapters = chapters or description_chapters(description)
    if chapters:
        return segments_from_chapters(chapters, duration)
    return segments_from_dialogue_gaps(words, duration)


def place_segments(segments: list[dict], words: list[tuple[float, str]], movie: MovieTranscript) -> list[dict]:
    placed = []
    for segment in segments:
        inside = [(t - segment["start"], w) for t, w in words if segment["start"] <= t < segment["end"]]
        located = movie.locate(inside) if inside else {"matched": False, "reason": "no dialogue"}
        row = {**segment, **located}
        if located.get("matched"):
            # movie_start/end from locate are relative to the segment's own clock; keep both clocks.
            row["clip_start"], row["clip_end"] = segment["start"], segment["end"]
            row["context"] = movie.context(located["movie_start"], located["movie_end"])
        placed.append(row)
    return placed

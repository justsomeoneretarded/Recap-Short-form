"""Group placed scenes into story arcs; each arc becomes one Short.

1. Scene units: every accepted clip (or compilation segment) that was placed in the movie,
   limited to its usable window (no studio title/end cards).
2. Duplicates: units covering the same stretch of the movie are one scene; the best upload
   (audience score, resolution) is kept and the others are alternates.
3. Arcs: runs of consecutive scenes close together in the movie, long enough for the
   requested length. Arcs never share a scene, so Shorts never reuse footage.
4. Ranking: audience score, Most Replayed / comment peaks, footage coverage and intensity.
   When Gemini watched the clips, intensity is what actually happens on screen (action and
   story value per moment) instead of a guess from the cutting rate, and its strongest
   moments count as peaks.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .locate import MovieTranscript

MAX_GAP_SECONDS = 6 * 60    # scenes further apart in the movie start a new story
MAX_ARC_SPAN = 15 * 60      # one Short covers at most this much movie time
MAX_UNIT_SECONDS = 90       # pieces over twice this (previews, "first 10 minutes") are cut into ~90 s scenes
LONG_UPLOAD_SECONDS = 360   # uploads this long are excerpts, not a scene someone chose to clip
ARC_FOOTAGE_FACTOR = 1.6    # a story gathers at most this many times the Short's length in footage
MAX_SHORTS = 5


@dataclass
class Unit:
    clip_id: str
    clip_title: str
    clip_start: float
    clip_end: float
    movie_start: float
    movie_end: float
    score: float
    height: int
    peaks: list[float] = field(default_factory=list)
    alternates: list[str] = field(default_factory=list)
    clip_seconds: float = 0.0
    intensity: float = 0.5   # 0 calm talk … 1 fast action (from the clip's cutting rate)
    avoid: list = field(default_factory=list)  # clip-time ranges never to show (text cards)
    moments: list = field(default_factory=list)  # what Gemini saw, clip time (optional)

    @property
    def seconds(self) -> float:
        return max(0.0, self.clip_end - self.clip_start)

    def overlap(self, other: "Unit") -> float:
        shared = min(self.movie_end, other.movie_end) - max(self.movie_start, other.movie_start)
        return max(0.0, shared) / max(1e-6, min(self.movie_end - self.movie_start, other.movie_end - other.movie_start))


def units_from(clips: list[dict], screening: dict[str, dict]) -> list[Unit]:
    units = []
    for clip in clips:
        report = screening.get(clip["id"])
        if report is not None and not report.get("accept"):
            continue
        usable = (report or {}).get("usable") or [0.0, clip.get("duration") or 0.0]
        placement = clip.get("placement") or {}
        # Each piece maps clip time → movie time with one offset (movie = offset + clip time).
        pieces = [{"start": s["start"], "end": s["end"], "offset": s["offset_seconds"] - s["start"]}
                  for s in placement.get("segments") or [] if s.get("matched")]
        if not pieces and placement.get("matched"):
            pieces = [{"start": 0.0, "end": float(clip.get("duration") or 0.0), "offset": placement["offset_seconds"]}]
        peaks = [p["start"] for p in clip.get("signals", {}).get("heatmap_peaks") or [] if p.get("start") is not None]
        peaks += [p["second"] for p in clip.get("comment_peaks") or []]
        height = clip.get("signals", {}).get("height") or (report or {}).get("height") or 0
        if height and height < 720:
            continue  # soft re-uploads look bad once cropped
        clip_seconds = float(clip.get("duration") or (report or {}).get("duration") or 0.0)
        shot = ((report or {}).get("cutting") or {}).get("average_shot_seconds")
        intensity = 0.5 if not shot else min(1.0, max(0.0, (7.0 - float(shot)) / 5.0))  # 2 s shots → 1, 7 s → 0
        watch = (report or {}).get("watch") or {}
        moments = watch.get("moments") or []
        watched_peaks = [m["start"] for m in moments if m.get("intensity", 0) >= 8 or m.get("story", 0) >= 9]
        if watch.get("best_moment"):
            watched_peaks.append(watch["best_moment"]["start"])
        score = clip.get("score", {}).get("total", 0.0)
        if clip_seconds >= LONG_UPLOAD_SECONDS:
            score *= 0.85  # a long excerpt is less of an audience signal for any one scene in it
        for piece in pieces:
            start, end = max(piece["start"], usable[0]), min(piece["end"], usable[1])
            if end - start < 6:
                continue
            # Long pieces become several scene-sized units, so a 10-minute preview cannot swallow the
            # focused scene uploads that overlap it, and a story is built from scenes, not whole reels.
            count = 1 if end - start <= 2 * MAX_UNIT_SECONDS else math.ceil((end - start) / MAX_UNIT_SECONDS - 1e-9)
            step = (end - start) / count
            for k in range(count):
                s, e = start + k * step, start + (k + 1) * step
                inside = [m for m in moments if m["end"] > s and m["start"] < e]
                units.append(Unit(clip["id"], clip.get("title", ""), s, e, max(0.0, piece["offset"] + s),
                                  piece["offset"] + e, score, height,
                                  [p for p in peaks + watched_peaks if s <= p <= e],
                                  clip_seconds=clip_seconds, intensity=seen_intensity(inside, intensity),
                                  avoid=[r for r in (report or {}).get("avoid") or [] if r[1] > s and r[0] < e],
                                  moments=inside))
    return units


def seen_intensity(moments: list[dict], fallback: float) -> float:
    """0..1 from what is on screen: half action, half story value, weighted by moment length."""
    if not moments:
        return fallback
    weight = sum(max(0.5, m["end"] - m["start"]) for m in moments)
    value = sum(max(0.5, m["end"] - m["start"]) * (0.5 * m.get("intensity", 5) + 0.5 * m.get("story", 5)) for m in moments)
    return round(min(1.0, max(0.0, (value / weight - 1) / 9)), 3)


def merge_duplicates(units: list[Unit], threshold: float = 0.5) -> list[Unit]:
    """Same stretch of the movie uploaded by several channels → keep the best, remember the rest."""
    # Best audience score first; among similar scores a focused scene upload beats a long excerpt.
    best_first = sorted(units, key=lambda u: (round(u.score, 2), u.clip_seconds < LONG_UPLOAD_SECONDS, u.height),
                        reverse=True)
    kept: list[Unit] = []
    for unit in best_first:
        twin = next((k for k in kept if k.overlap(unit) >= threshold), None)
        if twin:
            twin.alternates.append(unit.clip_id)
        else:
            kept.append(unit)
    return sorted(kept, key=lambda u: u.movie_start)


def _arc_score(units: list[Unit], target: float) -> float:
    footage = sum(u.seconds for u in units)
    audience = sum(u.score * u.seconds for u in units) / max(1.0, footage)
    peaks = min(1.0, sum(len(u.peaks) for u in units) / 4)
    coverage = min(1.0, footage / max(1.0, target))
    intensity = sum(u.intensity * u.seconds for u in units) / max(1.0, footage)
    # Shorts live on visible action: a story of fast-cut scenes beats one of people talking at a table.
    return round(0.45 * audience + 0.15 * peaks + 0.2 * coverage + 0.2 * intensity, 4)


def candidate_arcs(units: list[Unit], target: float) -> list[list[Unit]]:
    """Every run of consecutive scenes that stays within the gap and span limits."""
    arcs = []
    for i in range(len(units)):
        run = [units[i]]
        arcs.append(list(run))
        for unit in units[i + 1:]:
            if unit.movie_start - run[-1].movie_end > MAX_GAP_SECONDS or unit.movie_end - run[0].movie_start > MAX_ARC_SPAN:
                break
            run.append(unit)
            arcs.append(list(run))
            if sum(u.seconds for u in run) >= ARC_FOOTAGE_FACTOR * target:
                break
    return arcs


def choose_arcs(units: list[Unit], target_seconds: float, *, max_shorts: int = MAX_SHORTS,
                minimum_share: float = 0.6) -> list[dict]:
    """Greedy: best-scoring arc first, then the best arc that shares no scene with those chosen."""
    minimum = minimum_share * target_seconds
    pool = [a for a in candidate_arcs(units, target_seconds) if sum(u.seconds for u in a) >= minimum]
    if not pool and units:  # thin footage: one shorter Short from the best run available
        pool = sorted(candidate_arcs(units, target_seconds), key=lambda a: -sum(u.seconds for u in a))[:1]
    pool.sort(key=lambda a: _arc_score(a, target_seconds), reverse=True)
    chosen: list[list[Unit]] = []
    used: set[int] = set()
    for arc in pool:
        if len(chosen) >= max_shorts:
            break
        if any(id(u) in used for u in arc):
            continue
        chosen.append(arc)
        used.update(id(u) for u in arc)
    return [describe(arc, target_seconds, n) for n, arc in enumerate(sorted(chosen, key=lambda a: a[0].movie_start))]


def describe(arc: list[Unit], target: float, number: int, movie: MovieTranscript | None = None) -> dict:
    footage = sum(u.seconds for u in arc)
    return {
        "id": f"arc{number + 1}",
        "movie_start": round(arc[0].movie_start, 1), "movie_end": round(arc[-1].movie_end, 1),
        "footage_seconds": round(footage, 1), "score": _arc_score(arc, target),
        "short_seconds": round(min(target, footage), 1), "shorter_than_requested": footage < target,
        "scenes": [{"clip_id": u.clip_id, "clip_title": u.clip_title, "clip_start": round(u.clip_start, 2),
                    "clip_end": round(u.clip_end, 2), "movie_start": round(u.movie_start, 1),
                    "movie_end": round(u.movie_end, 1), "peaks": sorted(set(round(p, 1) for p in u.peaks)),
                    "avoid": u.avoid, "moments": u.moments,
                    "alternates": u.alternates} for u in arc],
    }


def attach_dialogue(arcs: list[dict], movie: MovieTranscript, pad: float = 60.0) -> list[dict]:
    """Give the writer the real dialogue: before the arc, inside each scene, and just after."""
    for arc in arcs:
        arc["dialogue_before"] = movie.dialogue_between(max(0.0, arc["movie_start"] - pad), arc["movie_start"])[-600:]
        arc["dialogue_after"] = movie.dialogue_between(arc["movie_end"], arc["movie_end"] + pad)[:400]
        for scene in arc["scenes"]:
            scene["dialogue"] = movie.dialogue_between(scene["movie_start"], scene["movie_end"])[:1200]
    return arcs


def build_arcs(clips: list[dict], screening: dict[str, dict], target_seconds: float,
               movie: MovieTranscript | None = None, max_shorts: int = MAX_SHORTS) -> dict:
    units = merge_duplicates(units_from(clips, screening))
    arcs = choose_arcs(units, target_seconds, max_shorts=max_shorts)
    if movie is not None:
        attach_dialogue(arcs, movie)
    return {"target_seconds": target_seconds, "scenes_available": len(units), "arcs": arcs}

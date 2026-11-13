"""Step 1 of the footage-first script: Gemini watches every scene's footage and lists its events.

For each scene of the story, the clip around the scene (its window ±30 s, at most two minutes) is cut
locally, made small (360p, 2 fps, mono sound) and sent to Gemini as video. Gemini answers with the
events it sees: start, end and the peak second of the action, who is in it, what is on screen, and how
much it matters to the story. It also says whether the footage has burned-in captions or someone
talking over the film. All times come back in the clip's own seconds, so the edit can play exactly
what a line describes, with the action's peak under the line's key word.
"""
from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

PAD = 30.0            # seconds around the scene that Gemini also watches (the action often starts earlier)
MAX_WINDOW = 120.0    # longest stretch sent in one request (input-token limits)

EVENTS_SCHEMA = {"type": "object", "properties": {
    "events": {"type": "array", "items": {"type": "object", "properties": {
        "start": {"type": "number"}, "end": {"type": "number"}, "peak": {"type": "number"},
        "what": {"type": "string"}, "who": {"type": "string"}, "on_screen": {"type": "string"},
        "importance": {"type": "integer"}},
        "required": ["start", "end", "peak", "what", "who", "on_screen", "importance"]}},
    "burned_in_captions": {"type": "boolean"},
    "narrator_over_film": {"type": "boolean"}},
    "required": ["events", "burned_in_captions", "narrator_over_film"]}

PROMPT = """You are logging footage for a movie-recap Short about {movie}. Watch this clip (a stretch of the movie).
The scene the story needs here: "{must_show}".
List every distinct EVENT you see, in order, with times in seconds from the start of THIS clip:
- start / end: when the event begins and ends; peak: the second where its key action happens (the strike, the fall,
  the phone lighting up, the look).
- what: the concrete visible action in a few words (who does what to whom/with what). Only what is SHOWN.
- who: the people in it (names if you know them from the movie, else a short description).
- on_screen: the place and the important objects visible.
- importance: 1-10 for how much the event matters to this movie's story (a killing, a reveal, a threat = high;
  someone walking, painting, waiting = low).
Cover the whole clip; split long actions into separate events when the action changes (an attack, then the victim
falling, then dying are three events). Also say whether the clip has burned-in captions and whether someone talks
over the film (a narrator or commentator)."""


def window(scene: dict, duration: float) -> tuple[float, float]:
    """The stretch Gemini watches: the scene ±PAD, at most MAX_WINDOW, centred on the scene."""
    lo, hi = max(0.0, scene["clip_start"] - PAD), scene["clip_end"] + PAD
    if duration:
        hi = min(hi, duration)
    if hi - lo > MAX_WINDOW:
        middle = (scene["clip_start"] + scene["clip_end"]) / 2
        lo = max(0.0, middle - MAX_WINDOW / 2)
        hi = lo + MAX_WINDOW
    return round(lo, 2), round(hi, 2)


def cut_segment(video: str, lo: float, hi: float, target: Path) -> Path:
    """A small copy of [lo, hi]: 360p, 2 fps, mono sound (Gemini samples video at about 1 fps anyway)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{lo:.3f}", "-t", f"{hi - lo:.3f}", "-i", str(video),
                             "-vf", "scale=-2:360,fps=2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "32",
                             "-c:a", "aac", "-ac", "1", "-b:a", "48k", str(target)], capture_output=True)
    if result.returncode or not target.exists():
        raise RuntimeError(f"could not cut the scene: {result.stderr[-200:]!r}")
    return target


def clean_events(raw: dict, lo: float, hi: float) -> list[dict]:
    """Clip-seconds events inside the window, in order, each with start ≤ peak ≤ end."""
    events = []
    for row in (raw or {}).get("events") or []:
        try:
            start, end, peak = (float(row.get(k)) for k in ("start", "end", "peak"))
        except (TypeError, ValueError):
            continue
        start, end = lo + max(0.0, start), lo + max(0.0, end)
        peak = lo + max(0.0, peak)
        start, end = max(lo, min(start, hi)), max(lo, min(end, hi))
        if end - start < 0.5:
            continue
        peak = min(max(peak, start), end)
        events.append({"start": round(start, 2), "end": round(end, 2), "peak": round(peak, 2),
                       "what": " ".join(str(row.get("what", "")).split())[:160],
                       "who": " ".join(str(row.get("who", "")).split())[:100],
                       "on_screen": " ".join(str(row.get("on_screen", "")).split())[:120],
                       "importance": max(1, min(10, int(row.get("importance") or 5)))})
    return sorted(events, key=lambda e: e["start"])


def watch_scene(gemini, scene: dict, video: str, work: Path, movie: dict, *, probe=None) -> dict:
    """{'window': [lo, hi], 'events': [...], 'burned_in_captions', 'narrator_over_film'} for one scene."""
    if probe is None:
        from .media import probe
    duration = float((probe(Path(video)) or {}).get("duration") or 0)
    lo, hi = window(scene, duration)
    segment = cut_segment(video, lo, hi, Path(work) / f"{scene['clip_id']}-{int(lo)}.mp4")
    record = gemini.upload(segment)
    try:
        raw = gemini.generate("smart", [
            {"fileData": {"fileUri": record["uri"], "mimeType": record.get("mimeType", "video/mp4")}},
            {"text": PROMPT.format(movie=f"{movie.get('title')} ({movie.get('year')})",
                                   must_show=(scene.get("beat") or {}).get("what_we_see", ""))}],
            schema=EVENTS_SCHEMA, temperature=0.2, low_media=True, max_tokens=8192)
    finally:
        gemini.delete(record)
        segment.unlink(missing_ok=True)
    return {"window": [lo, hi], "events": clean_events(raw, lo, hi),
            "burned_in_captions": bool((raw or {}).get("burned_in_captions")),
            "narrator_over_film": bool((raw or {}).get("narrator_over_film"))}


def watch_story(gemini, arc: dict, footage: dict, work: Path, movie: dict, *, probe=None, log=None) -> dict:
    """The arc with `events` and `watch_window` on every scene Gemini could watch (one request per scene;
    a scene that fails keeps no events and is written from the plan instead)."""
    from . import gemini as gem
    log = log or (lambda m: print(m, file=sys.stderr, flush=True))
    arc = copy.deepcopy(arc)
    for i, scene in enumerate(arc.get("scenes") or []):
        video = footage.get(scene["clip_id"])
        if not video:
            continue
        try:
            seen = watch_scene(gemini, scene, video, work, movie, probe=probe)
        except (gem.GeminiUnavailable, RuntimeError, OSError) as exc:
            log(f"Scene {i}: not watched ({str(exc)[:120]})")
            continue
        scene["watch_window"], scene["events"] = seen["window"], seen["events"]
        scene["watch_flags"] = {k: seen[k] for k in ("burned_in_captions", "narrator_over_film")}
        log(f"Scene {i} watched: {len(seen['events'])} events — " +
            "; ".join(f"{e['start']:.0f}-{e['end']:.0f}s {e['what'][:40]} ({e['importance']})" for e in seen["events"][:8]))
    return arc

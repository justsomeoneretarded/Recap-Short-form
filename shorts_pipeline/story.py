"""Story first, footage second.

A good recap Short tells ONE story across several scenes, each chosen for what it does in the
story (the offer, the refusal, the revenge, the realisation, the return), cut down to the seconds
that move it forward. The old approach (take clips that sit next to each other in the movie and
describe them) could never build that: the scenes of one story are often 20+ minutes apart.

1. plan_stories: Gemini reads the plot and the timed subtitles and plans up to N stories, each a
   spine of 3–6 beats with movie times (from the subtitles), the beat's role, and a YouTube search.
2. The beat searches go into clip discovery; placed clips are matched to beats by movie time.
3. stories_to_arcs: each beat becomes a scene cut to the beat's own stretch of the movie.
The writer then narrates each scene knowing its role in the story.
"""
from __future__ import annotations

import re

from .locate import MovieTranscript

MIN_BEATS, MAX_BEATS = 3, 6
MIN_BEAT_SECONDS, MAX_BEAT_SECONDS = 8.0, 45.0
SUBTITLE_CHARS = 120_000   # whole-movie dialogue timeline (Gemini reads ~1M tokens)

STORY_SCHEMA = {"type": "object", "properties": {"stories": {"type": "array", "items": {"type": "object", "properties": {
    "title": {"type": "string"},
    "spine": {"type": "string"},
    "hook_idea": {"type": "string"},
    "ending_idea": {"type": "string"},
    "ending_mode": {"type": "string", "enum": ["renewed_threat", "reveal", "reflection", "thematic_payoff",
                                                "resolved_payoff"]},
    "cold_open": {"type": "boolean"},
    "beats": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"},
        "role": {"type": "string"},
        "what_we_see": {"type": "string"},
        "start": {"type": "string"},
        "end": {"type": "string"},
        "search": {"type": "string"},
        "key_moment": {"type": "string"}},
        "required": ["name", "role", "what_we_see", "start", "end", "search"]}}},
    "required": ["title", "spine", "hook_idea", "ending_idea", "beats"]}}},
    "required": ["stories"]}

PLANNER = """You plan viral movie-recap YouTube Shorts (about {seconds} seconds each) for {movie}.
A great Short tells ONE gripping story told across several scenes of the movie, not one scene described.
What the best channels do (from the reference Shorts):
- They open on a concrete, visible act or object that raises a question (a finger cut off for a ring, five locks
  on a door, a man hiding from cameras), not on a character introduction. The backstory comes later, in one or
  two sentences, once the viewer wants it.
- Every beat changes the situation: a refusal, a consequence, a deadline, an obstacle, a refuge, a reversal.
  Never two beats of the same situation.
- The narrator names the specific objects and actions that are on screen, and short original movie lines
  punctuate the story at confrontations.
- The ending fits the story: a renewed threat, an ironic reveal, a reflection, a thematic payoff or a full payoff.
Rules for each story:
- A spine of {min_beats}-{max_beats} beats in movie order, each one CAUSING the next: e.g. a want or offer,
  a refusal, the consequence, the escalation, the realisation of who they messed with, the turn or return.
- The beats may be far apart in the movie. Pick each beat for what it does in the story, never just for action.
- Each beat is a short stretch of the movie ({min_s:.0f}-{max_s:.0f} s) with clear visible action that a viewer
  understands with one sentence of narration. Give its start and end as mm:ss movie times taken from the
  subtitle timeline below (the dialogue of that stretch must be in it). Beats with no dialogue: estimate from
  the surrounding lines.
- search: what a person would type on YouTube to find a clip of exactly that scene (movie title + 2-6 words).
- key_moment: the one moment of the beat to leave without narration (a reaction, a reveal), if any.
- The story must make sense to someone who never saw the movie, and must not spoil the movie's ending.
- cold_open: true if the FIRST beat is a striking moment taken from later in the story (shown first, then the
  story restarts from its cause); its start/end are still its real movie times. Otherwise beats are in order.
- hook_idea: the opening line idea: the concrete act and the question it raises, or the stakes.
- ending_mode and ending_idea: how it ends (see above) and the last line idea, ideally looping to the opening.
- Different stories must not share beats.
Plan up to {count} different stories, best first.

PLOT:
{plot}

SUBTITLE TIMELINE (mm:ss dialogue):
{timeline}"""


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def parse_clock(text) -> float | None:
    """'1:02:03', '62:03', '62:03.5' or a number of seconds → seconds."""
    if isinstance(text, (int, float)):
        return float(text)
    parts = re.findall(r"\d+(?:\.\d+)?", str(text or ""))
    if not parts or len(parts) > 3:
        return None
    value = 0.0
    for part in parts:
        value = value * 60 + float(part)
    return value


def timeline(transcript: MovieTranscript, limit: int = SUBTITLE_CHARS) -> str:
    """The whole movie's dialogue as 'mm:ss line' rows, thinned evenly if too long."""
    rows = [f"{_clock(r['start'])} {r['text']}" for r in transcript.lines_between(0, 1e9)]
    text = "\n".join(rows)
    if len(text) <= limit or not rows:
        return text
    keep = max(1, int(len(rows) * limit / len(text)))
    step = len(rows) / keep
    return "\n".join(rows[int(i * step)] for i in range(keep))


def clean_stories(raw: dict, runtime: float) -> list[dict]:
    """Valid beats only: inside the movie, in order, sensible length; stories with enough beats."""
    stories, used = [], []
    for story in (raw or {}).get("stories") or []:
        beats = []
        for b in story.get("beats") or []:
            start, end = parse_clock(b.get("start")), parse_clock(b.get("end"))
            if start is None or end is None:
                continue
            if end - start < MIN_BEAT_SECONDS:  # too short to place: widen around it
                pad = (MIN_BEAT_SECONDS - (end - start)) / 2
                start, end = start - pad, end + pad
            end = min(end, start + MAX_BEAT_SECONDS * 2)  # long stretches are trimmed to the action later
            start, end = max(0.0, start), min(runtime or end, end)
            if end - start < 4 or any(min(end, e) - max(start, s) > 0.5 * (end - start) for s, e in used):
                continue  # broken, or the same stretch as another story's beat
            cold = bool(story.get("cold_open")) and len(beats) == 1
            if beats and start < beats[-1]["movie_start"] and not cold:
                continue  # beats run in movie order (after an optional cold open)
            beats.append({"name": str(b.get("name", ""))[:60], "role": str(b.get("role", ""))[:160],
                          "what_we_see": str(b.get("what_we_see", ""))[:300], "search": str(b.get("search", ""))[:90],
                          "key_moment": str(b.get("key_moment") or "")[:160],
                          "movie_start": round(start, 1), "movie_end": round(end, 1)})
        if len(beats) >= MIN_BEATS:
            used += [(b["movie_start"], b["movie_end"]) for b in beats]
            stories.append({"title": str(story.get("title", ""))[:90], "spine": str(story.get("spine", ""))[:400],
                            "hook_idea": str(story.get("hook_idea", ""))[:200],
                            "ending_idea": str(story.get("ending_idea", ""))[:200],
                            "ending_mode": story.get("ending_mode") or "renewed_threat",
                            "cold_open": bool(story.get("cold_open")) and len(beats) > 1 and
                            beats[0]["movie_start"] > beats[1]["movie_start"], "beats": beats[:MAX_BEATS]})
    return stories


def plan_stories(gemini, research: dict, transcript: MovieTranscript, plot: str, seconds: float,
                 count: int = 5) -> list[dict]:
    movie = research["movie"]
    runtime = float(movie.get("runtime_minutes") or 0) * 60 or (transcript.cues[-1].end if transcript.cues else 0)
    prompt = PLANNER.format(seconds=round(seconds), movie=f"{movie['title']} ({movie.get('year')})",
                            min_beats=MIN_BEATS, max_beats=MAX_BEATS, min_s=MIN_BEAT_SECONDS, max_s=MAX_BEAT_SECONDS,
                            count=count, plot=plot[:20000] or "(no plot)", timeline=timeline(transcript))
    raw = gemini.generate("smart", [{"text": prompt}], schema=STORY_SCHEMA, temperature=0.5)
    return clean_stories(raw, runtime)[:count]


def beat_searches(stories: list[dict]) -> list[str]:
    """YouTube searches for every beat (movie title already in them), best stories first."""
    out = []
    for story in stories:
        for beat in story["beats"]:
            if beat["search"] and beat["search"].lower() not in (q.lower() for q in out):
                out.append(beat["search"])
    return out


def stories_to_arcs(stories: list[dict], units: list, target_seconds: float) -> list[dict]:
    """Each beat gets the placed footage covering its stretch of the movie, cut to that stretch.
    A story keeps the beats that have footage; with fewer than MIN_BEATS it is dropped."""
    arcs = []
    for story in stories:
        scenes = []
        for beat in story["beats"]:
            best, best_cover = None, 0.0
            for u in units:
                cover = min(u.movie_end, beat["movie_end"]) - max(u.movie_start, beat["movie_start"])
                if cover > best_cover + 0.5 or (best is not None and abs(cover - best_cover) <= 0.5 and u.score > best.score):
                    best, best_cover = u, cover
            if best is None or best_cover < min(6.0, 0.5 * (beat["movie_end"] - beat["movie_start"])):
                continue
            ms, me = max(best.movie_start, beat["movie_start"]), min(best.movie_end, beat["movie_end"])
            offset = best.movie_start - best.clip_start  # movie time = clip time + offset
            cs, ce = ms - offset, me - offset
            scenes.append({"clip_id": best.clip_id, "clip_title": best.clip_title,
                           "clip_start": round(cs, 2), "clip_end": round(ce, 2),
                           "movie_start": round(ms, 1), "movie_end": round(me, 1),
                           "peaks": sorted({round(p, 1) for p in best.peaks if cs <= p <= ce}),
                           "avoid": [r for r in best.avoid if r[1] > cs and r[0] < ce],
                           "moments": [m for m in best.moments if m["end"] > cs and m["start"] < ce],
                           "alternates": best.alternates,
                           "beat": {k: beat[k] for k in ("name", "role", "what_we_see", "key_moment")}})
        if len(scenes) < MIN_BEATS:
            continue
        footage = sum(s["clip_end"] - s["clip_start"] for s in scenes)
        arcs.append({"id": f"arc{len(arcs) + 1}", "movie_start": min(x["movie_start"] for x in scenes),
                     "movie_end": max(x["movie_end"] for x in scenes), "footage_seconds": round(footage, 1), "score": 1.0,
                     "short_seconds": round(min(target_seconds, 0.85 * footage), 1),
                     "shorter_than_requested": 0.85 * footage < target_seconds, "planned": True,
                     "story": {k: story.get(k) for k in ("title", "spine", "hook_idea", "ending_idea", "ending_mode",
                                                         "cold_open")},
                     "scenes": scenes})
    return arcs

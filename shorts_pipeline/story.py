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
    "required": ["title", "spine", "hook_idea", "ending_idea", "beats"]}},
    "broad_searches": {"type": "array", "items": {"type": "string"}}},
    "required": ["stories", "broad_searches"]}

BROAD_RULES = """Also give broad_searches: 6-10 short, general searches people type to find ANY footage of this movie on YouTube.
Fit them to what THIS movie actually contains, never to a genre template: an action film may get action, fights, kills,
shootout, best action; a psychological thriller with no fights gets things like intense scene, hospital scene, sad scene,
twist, ending; a horror film scariest moments, jump scares. Add compilations ("all ... scenes", best moments).
Movie title + 1-3 words; most of them WITHOUT the word "scene"; about half of them with the release year after the title
(e.g. "Fractured 2019 hospital scene") so YouTube tells this film apart from others with the same name.
Long compilations are welcome: the right seconds are cut out of them later."""

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
- The turning-point ACTIONS of the story must be beats themselves (the attack, the theft, the kill, the escape,
  the discovery, the weapon dug up), not only the conversations about them: the viewer must SEE what the story
  turns on. A story told only through people talking about events is a bad Short.
- Each beat is a short stretch of the movie ({min_s:.0f}-{max_s:.0f} s) with clear visible action that a viewer
  understands with one sentence of narration. Give its start and end as mm:ss movie times taken from the
  subtitle timeline below (the dialogue of that stretch must be in it). Beats with no dialogue: estimate from
  the surrounding lines.
- search: how clip channels title an upload of that scene: movie title (with the year if the title is common) + 2-4 plain words (e.g. "John Wick gas
  station scene", "Havoc club shootout scene"). No plot details or minor character names: nobody titles uploads so.
- key_moment: the one moment of the beat to leave without narration (a reaction, a reveal), if any.
- The story must make sense to someone who never saw the movie, and must not spoil the movie's ending.
- cold_open: true if the FIRST beat is a striking moment taken from later in the story (shown first, then the
  story restarts from its cause); its start/end are still its real movie times. Otherwise beats are in order.
- hook_idea: the opening line idea: the concrete act and the question it raises, or the stakes.
- ending_mode and ending_idea: how it ends (see above) and the last line idea, ideally looping to the opening.
- Different stories must not share beats.
Plan up to {count} different stories, best first.
{broad_rules}

{uploads}PLOT:
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


def broad_searches(raw: dict, title: str, limit: int = 10) -> list[str]:
    """Gemini's general searches for the movie, cleaned: each names the movie, 2-8 words, no repeats."""
    out: list[str] = []
    for q in (raw or {}).get("broad_searches") or []:
        q = re.sub(r"\s+", " ", str(q)).strip(" .\"'")
        if title.lower() not in q.lower():
            q = f"{title} {q}"
        if 2 <= len(q.split()) <= 8 and q.lower() not in (x.lower() for x in out):
            out.append(q)
    return out[:limit]


UPLOADS_NOTE = """FOOTAGE THAT EXISTS: these uploads of the movie were found on YouTube (title, length). A beat is only
usable if one of them shows it, so build every story from scenes these uploads very likely contain (their titles name
the scene, or a long compilation of that kind of scene). A beat no upload shows will be dropped, and a story with fewer
than {min_beats} usable beats is lost.
{listing}

"""


def uploads_listing(candidates: list[dict], limit: int = 60) -> str:
    rows = [c for c in candidates if c.get("id") and c.get("title")][:limit]
    return "\n".join(f"- {c['title'][:100]} ({int(c.get('duration') or 0)} s)" for c in rows)


def plan_stories(gemini, research: dict, transcript: MovieTranscript, plot: str, seconds: float,
                 count: int = 5, *, with_searches: bool = False, uploads: list[dict] | None = None):
    movie = research["movie"]
    runtime = float(movie.get("runtime_minutes") or 0) * 60 or (transcript.cues[-1].end if transcript.cues else 0)
    listing = uploads_listing(uploads or [])
    prompt = PLANNER.format(seconds=round(seconds), movie=f"{movie['title']} ({movie.get('year')})",
                            min_beats=MIN_BEATS, max_beats=MAX_BEATS, min_s=MIN_BEAT_SECONDS, max_s=MAX_BEAT_SECONDS,
                            count=count, plot=plot[:20000] or "(no plot)", timeline=timeline(transcript),
                            uploads=UPLOADS_NOTE.format(min_beats=MIN_BEATS, listing=listing) if listing else "",
                            broad_rules=BROAD_RULES)
    raw = gemini.generate("smart", [{"text": prompt}], schema=STORY_SCHEMA, temperature=0.5)
    stories = clean_stories(raw, runtime)[:count]
    return (stories, broad_searches(raw, movie["title"])) if with_searches else stories


SEARCH_SCHEMA = {"type": "object", "properties": {"broad_searches": {"type": "array", "items": {"type": "string"}}},
                 "required": ["broad_searches"]}


def general_searches(gemini, movie: dict, plot: str) -> list[str]:
    """Gemini's general searches for any footage of this movie (written from what it contains)."""
    prompt = (f"Movie: {movie['title']} ({movie.get('year')}). Plot:\n{plot[:6000]}\n\n" +
              BROAD_RULES +
              "\nAnswer as JSON with broad_searches.")
    raw = gemini.generate("light", [{"text": prompt}], schema=SEARCH_SCHEMA, temperature=0.4)
    return broad_searches(raw, movie["title"])


def beat_searches(stories: list[dict]) -> list[str]:
    """YouTube searches for every beat (movie title already in them), best stories first."""
    out = []
    for story in stories:
        for beat in story["beats"]:
            if beat["search"] and beat["search"].lower() not in (q.lower() for q in out):
                out.append(beat["search"])
    return out


def _offset(placement: dict, at: float) -> float | None:
    """movie time − clip time for the placed piece around clip second `at` (None if not placed)."""
    for seg in placement.get("segments") or []:
        if seg.get("matched") and seg["start"] - 5 <= at <= seg["end"] + 5:
            return seg["offset_seconds"] - seg["start"]
    if placement.get("matched") and placement.get("offset_seconds") is not None:
        return float(placement["offset_seconds"])
    return None


def confirmed_scene(beat: dict, check: dict, clip: dict | None, report: dict | None) -> dict | None:
    """A scene from footage Gemini confirmed. With dialogue the subtitle placement gives exact movie
    times and sharpens the cut; a silent scene uses Gemini's own seconds."""
    if report is not None and not report.get("accept"):
        return None  # screening found a problem (logo inside the picture, low resolution, …)
    gs, ge = check["start"], check["end"]
    longest = max(MAX_BEAT_SECONDS, beat["movie_end"] - beat["movie_start"])
    if ge - gs > longest:  # a long stretch (a whole sequence): keep its opening, where the beat starts
        ge = gs + longest
    offset = _offset((clip or {}).get("placement") or {}, (gs + ge) / 2)
    if offset is not None:
        cs, ce = beat["movie_start"] - offset, beat["movie_end"] - offset
        lo, hi = max(cs, gs - 3), min(ce, ge + 3)
        cs, ce = (lo, hi) if hi - lo >= 5 else (gs, ge)  # the plan's times were off: trust what Gemini saw
        ms, me, timed = cs + offset, ce + offset, "subtitles"
    else:
        cs, ce, ms, me, timed = gs, ge, beat["movie_start"], beat["movie_end"], "gemini"
    watch = (report or {}).get("watch") or {}
    peaks = [p.get("start") for p in ((clip or {}).get("signals") or {}).get("heatmap_peaks") or [] if p.get("start") is not None]
    return {"clip_id": check["id"], "clip_title": (clip or {}).get("title", ""),
            "clip_start": round(cs, 2), "clip_end": round(ce, 2), "movie_start": round(ms, 1), "movie_end": round(me, 1),
            "peaks": sorted({round(p, 1) for p in peaks if cs <= p <= ce}),
            "avoid": [r for r in (report or {}).get("avoid") or [] if r[1] > cs and r[0] < ce],
            "moments": [m for m in watch.get("moments") or [] if m["end"] > cs and m["start"] < ce],
            "alternates": [], "timed_by": timed, "confirmed": check.get("confidence"),
            "beat": {k: beat[k] for k in ("name", "role", "what_we_see", "key_moment")}}


def stories_to_arcs(stories: list[dict], units: list, target_seconds: float, *, confirmed: dict | None = None,
                    clips: dict | None = None, screening: dict | None = None) -> list[dict]:
    """Each beat gets footage: first the upload Gemini confirmed shows it, else the placed footage
    covering its stretch of the movie, cut to that stretch. A story keeps the beats that have
    footage; with fewer than MIN_BEATS it is dropped."""
    arcs = []
    for n, story in enumerate(stories):
        scenes = []
        for b, beat in enumerate(story["beats"]):
            check = ((confirmed or {}).get(n) or {}).get(b)
            if check:
                scene = confirmed_scene(beat, check, (clips or {}).get(check["id"]), (screening or {}).get(check["id"]))
                if scene:
                    scenes.append(scene)
                    continue
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
                           "alternates": best.alternates, "timed_by": "subtitles",
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


# ======================================================================== Gemini finds and checks the footage

YOUTUBE_ID = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})")
MAX_CHECK_SECONDS = 15 * 60   # longer uploads are checked only if nothing shorter shows the beat


def suggest_links(gemini, movie: dict, story: dict) -> dict[int, list[str]]:
    """Real YouTube videos for each beat, found with Google Search (the API cannot browse YouTube
    itself; asked from memory it invents links, so every id is verified before use)."""
    lines = "\n".join(f"{i}. {b['name']}: {b['what_we_see']} (search: {b['search']})" for i, b in enumerate(story["beats"]))
    prompt = (f"Use Google Search to find YouTube videos that show these scenes of {movie['title']} "
              f"({movie.get('year')}). Prefer clip uploads of the scene itself (not trailers, reviews, reactions "
              f"or recaps). For each scene number give up to 3 full youtube.com/watch?v= links.\n{lines}\n"
              'Answer as JSON: {"scenes": [{"scene": 0, "links": ["https://www.youtube.com/watch?v=..."]}]}')
    text = gemini.generate("light", [{"text": prompt}], tools=[{"google_search": {}}], temperature=0.2)
    found: dict[int, list[str]] = {}
    for match in re.finditer(r'"scene"\s*:\s*(\d+)\s*,\s*"links"\s*:\s*\[([^\]]*)\]', str(text)):
        ids = list(dict.fromkeys(YOUTUBE_ID.findall(match.group(2))))
        if ids:
            found[int(match.group(1))] = ids[:3]
    return found


CHECK_SCHEMA = {"type": "object", "properties": {
    "shows_scene": {"type": "boolean"}, "confidence": {"type": "number"},
    "start": {"type": "number"}, "end": {"type": "number"}, "why": {"type": "string"}},
    "required": ["shows_scene", "confidence", "start", "end"]}


def check_clip(gemini, video_id: str, movie: dict, beat: dict, duration: float | None = None) -> dict:
    """Does this upload show this beat? Where (seconds from the start of the upload)?"""
    prompt = (f"This should be footage from the movie {movie['title']} ({movie.get('year')}). Does it show this "
              f"scene: {beat['name']} — {beat['what_we_see']}? It must be the film's own footage of that scene "
              "(not a trailer, review, reaction or someone talking over it). If yes, give start and end in seconds "
              "from the start of the video (numbers) covering exactly that scene, and how sure you are (0-1).")
    video = {"fileData": {"fileUri": f"https://www.youtube.com/watch?v={video_id}"}}
    reply = gemini.generate("light", [video, {"text": prompt}], schema=CHECK_SCHEMA, temperature=0.1, low_media=True)
    start, end = float(reply.get("start") or 0), float(reply.get("end") or 0)
    if duration:
        start, end = max(0.0, min(start, duration)), max(0.0, min(end, duration))
    ok = bool(reply.get("shows_scene")) and end - start >= 3 and float(reply.get("confidence") or 0) >= 0.6
    return {"id": video_id, "ok": ok, "confidence": round(float(reply.get("confidence") or 0), 2),
            "start": round(start, 1), "end": round(end, 1), "why": str(reply.get("why") or "")[:160]}


MATCH_SCHEMA = {"type": "object", "properties": {"beats": {"type": "array", "items": {"type": "object", "properties": {
    "beat": {"type": "integer"}, "uploads": {"type": "array", "items": {"type": "integer"}}},
    "required": ["beat", "uploads"]}}}, "required": ["beats"]}
_STOP = set("the a an of and in on at to with scene clip movie film official hd 4k 1080p full best epic".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 2}


def likely_uploads(gemini, story: dict, candidates: list[dict], movie: dict) -> dict[int, list[str]]:
    """Which found uploads probably show which beat, judged from their titles (one text request; word
    overlap when Gemini cannot answer). Which search found an upload says little: generic searches
    find most of the real scene clips."""
    pool = [c for c in candidates if c.get("id")][:40]
    title_words = set(_words(movie.get("title", "")))
    ranked: dict[int, list[str]] = {}
    for i, beat in enumerate(story["beats"]):  # fallback: shared words between the beat and the title
        want = _words(f"{beat['name']} {beat['what_we_see']} {beat['search']}") - title_words
        scored = sorted(((len(want & _words(c.get("title", ""))), c["id"]) for c in pool), reverse=True)
        ranked[i] = [vid for score, vid in scored if score > 0][:3]
    if gemini is None or not pool:
        return ranked
    listing = "\n".join(f"{n}. {c.get('title', '')[:90]} ({int(c.get('duration') or 0)} s)" for n, c in enumerate(pool))
    beats = "\n".join(f"{i}. {b['name']}: {b['what_we_see']}" for i, b in enumerate(story["beats"]))
    prompt = (f"YouTube uploads found for {movie['title']} ({movie.get('year')}):\n{listing}\n\nScenes:\n{beats}\n\n"
              "For each scene, list the upload numbers most likely to contain that scene, best first (at most 3), "
              "judging by title and length. Long uploads (compilations, all scenes, first minutes) may contain several "
              "scenes. Skip reviews, reactions, recaps, trailers and interviews. Empty list if none fits.")
    try:
        from .gemini import GeminiUnavailable
        reply = gemini.generate("light", [{"text": prompt}], schema=MATCH_SCHEMA, temperature=0.1)
    except GeminiUnavailable:
        return ranked
    for row in reply.get("beats") or []:
        i = int(row.get("beat", -1))
        if 0 <= i < len(story["beats"]):
            picks = [pool[n]["id"] for n in row.get("uploads") or [] if isinstance(n, int) and 0 <= n < len(pool)]
            ranked[i] = list(dict.fromkeys(picks + ranked.get(i, [])))[:4]
    return ranked


def confirm_beats(gemini, story: dict, candidates: list[dict], movie: dict, *, per_beat: int = 3,
                  log=lambda m: None) -> dict[int, dict]:
    """For each beat, watch its likeliest uploads (judged from all titles found, plus Gemini's
    suggested links) until one is confirmed. Wrong uploads are dropped before anything is downloaded."""
    from .gemini import GeminiUnavailable
    confirmed: dict[int, dict] = {}
    by_id = {c["id"]: c for c in candidates if c.get("id")}
    likely = likely_uploads(gemini, story, candidates, movie)
    used: set[str] = set()
    for i, beat in enumerate(story["beats"]):
        ids = [c["id"] for c in candidates if i in (c.get("suggested_for") or [])] + likely.get(i, [])
        mine = [by_id[v] for v in dict.fromkeys(ids) if v in by_id
                and ((by_id[v].get("signals") or {}).get("height") or 1080) >= 720]  # soft uploads fail screening
        # Shorter uploads first (a focused scene clip); long uploads and compilations are still checked, and
        # one compilation may serve several beats.
        mine.sort(key=lambda c: (c["id"] in used and (c.get("duration") or 0) <= MAX_CHECK_SECONDS,
                                 (c.get("duration") or 0) > MAX_CHECK_SECONDS))
        log(f"beat {beat['name']}: candidates {[c['id'] for c in mine[:per_beat]]}")
        for c in mine[:per_beat]:
            try:
                result = check_clip(gemini, c["id"], movie, beat, c.get("duration"))
            except GeminiUnavailable as exc:
                log(f"beat {beat['name']}: cannot check {c['id']}: {str(exc)[:100]}")
                return confirmed
            log(f"beat {beat['name']}: {c['id']} {'YES' if result['ok'] else 'no'} "
                f"{result['start']}-{result['end']}s ({result['why'][:80]})")
            if result["ok"]:
                confirmed[i] = result
                used.add(c["id"])
                break
    return confirmed

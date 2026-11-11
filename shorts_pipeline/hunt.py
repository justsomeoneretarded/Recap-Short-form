"""One unified runner for stories: script first, an adaptive footage hunt, then fallbacks.

1. Script first. Gemini writes whole scripts (story spine + narration + what each beat must show)
   from the plot and the timed subtitles, never looking at what footage exists, so the story is
   the best one for every movie. Beat times are checked against the subtitles; a strict editor
   rewrites weak scripts.
2. Footage hunt, cheapest proof first:
   - Gemini-written general searches + each beat's own search;
   - subtitle placement proves dialogue scenes for free;
   - only for beats still missing: Google Search links, channels and playlists (when footage is
     thin), Gemini watching to confirm, and new search rounds.
3. Fallbacks, in order: a missing beat becomes a line of context (the writer does this); fewer
   than MIN_BEATS beats with footage → the next script; every script fails → a footage-aware
   re-plan from the uploads that exist; then the caller's old scene-by-scene stories.

`footage` ("auto" | "plenty" | "rare") only forces the light or heavy hunt; "auto" decides from
how many clean scene uploads the first searches find.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

COVERAGE_PLENTY = 15   # clean scene uploads after the first searches: enough to skip channels/playlists


def _log(message: str) -> None:
    print(f"[discover] {message}", file=sys.stderr, flush=True)


def plan_scripts(google, research: dict, transcript, plot: str, length: float, count: int, *,
                 uploads: list[dict] | None = None, log=_log) -> list[dict]:
    """Scripts with checked times, each read by the strict editor (rewritten when weak)."""
    from . import gemini as gem
    from .story import edit_script, plan_stories, verify_times
    movie = research["movie"]
    runtime = float(movie.get("runtime_minutes") or 0) * 60
    stories = plan_stories(google, research, transcript, plot, length, count=count, uploads=uploads)
    verify_times(stories, transcript, runtime)
    edited = []
    for story in stories:
        try:
            story = edit_script(google, story, movie)
        except gem.GeminiUnavailable as exc:
            log(f"no editor pass for '{story['title']}': {str(exc)[:100]}")
        editor = story.get("editor") or {}
        log(f"script: {story['title']} — " + " → ".join(b['name'] for b in story['beats']) +
            f" | editor {editor.get('score', '?')}/10{' (rewritten)' if editor.get('rewritten') else ''}" +
            f" | times: {[b.get('time_check') for b in story['beats']]}")
        if editor.get("one_storyline") is False:  # separate subplots stitched together: never made
            log(f"script dropped: '{story['title']}' joins separate subplots")
            continue
        edited.append(story)
    return edited


def placed_beats(story: dict, units: list) -> set[int]:
    """Beats already covered by subtitle-placed footage (no Gemini watch needed)."""
    covered = set()
    for i, beat in enumerate(story["beats"]):
        need = min(6.0, 0.5 * (beat["movie_end"] - beat["movie_start"]))
        if any(min(u.movie_end, beat["movie_end"]) - max(u.movie_start, beat["movie_start"]) >= need for u in units):
            covered.add(i)
    return covered


def merge(found: dict, more: dict) -> None:
    have = {c["id"] for c in found["candidates"]}
    found["candidates"] += [c for c in more["candidates"] if c["id"] not in have]
    found["queries"] += [q for q in more.get("queries", []) if q not in found["queries"]]
    found["rejected"] += more.get("rejected", [])
    found["errors"] += more.get("errors", [])


class Hunt:
    """Finds footage for planned scripts; keeps the shared state (candidates, placements, confirms)."""

    def __init__(self, google, research: dict, youtube, workdir: Path, *, footage: str = "auto",
                 use_whisper: bool = True, log=_log, discover=None, place=None, expand=None):
        from . import discovery
        from .placement import place_candidates
        self.google, self.research, self.youtube = google, research, youtube
        self.movie = research["movie"]
        self.workdir = Path(workdir).resolve()
        self.footage = footage if footage in ("auto", "plenty", "rare") else "auto"
        self.use_whisper, self.log = use_whisper, log
        self._discover = discover or discovery.discover
        self._place = place or place_candidates
        self._expand = expand or discovery.expand
        self.found: dict = {"candidates": [], "queries": [], "rejected": [], "errors": []}
        self.placed: dict = {"clips": [], "placed": 0, "considered": 0}
        self.expanded = False
        self.report: dict = {"footage": self.footage, "rounds": 0, "expanded": False}

    # ------------------------------------------------------------------ searching
    def search(self, queries: list[str]) -> None:
        """The first search also runs the generic templates; later rounds only their new queries."""
        queries = [q for q in dict.fromkeys(queries) if q not in self.found["queries"]]
        first = not self.found["queries"]
        if queries or first:
            merge(self.found, self._discover(self.research, self.youtube, scene_hints=queries, only_hints=not first))

    def thin(self) -> bool:
        from .discovery import coverage
        count = coverage(self.found["candidates"])
        self.report["coverage"] = count
        return self.footage == "rare" or (self.footage == "auto" and count < COVERAGE_PLENTY)

    def widen(self) -> None:
        """Channels that clip this movie, and playlists of its scenes (once)."""
        if self.expanded or self.footage == "plenty":
            return
        self.expanded = self.report["expanded"] = True
        self.found["candidates"] += self._expand(self.youtube, self.movie, self.found["candidates"], log=self.log)

    # ------------------------------------------------------------------ placing (subtitles: free proof)
    def place(self, ids: list[str], extra: int = 4) -> None:
        done = {c["id"] for c in self.placed["clips"]}
        wanted = [c for c in self.found["candidates"] if c["id"] in set(ids) and c["id"] not in done]
        spares = [c for c in self.found["candidates"] if c["id"] not in done and c["id"] not in set(ids)][:extra]
        batch = wanted + spares
        if not batch:
            return
        result = self._place(self.research, {"candidates": batch}, self.youtube, self.workdir,
                             top=len(batch), use_whisper=self.use_whisper)
        self.placed["clips"] += result["clips"]
        self.placed["placed"] += result["placed"]
        self.placed["considered"] += result["considered"]

    def units(self, screened: dict | None = None) -> list:
        from .arcs import units_from
        return units_from(self.placed["clips"], screened or {})

    # ------------------------------------------------------------------ one story
    def footage_for(self, story: dict, *, rounds: int) -> tuple[dict, set]:
        """(confirmed beats by watching, beats covered by placement) for one script."""
        from . import gemini as gem
        from .discovery import candidate_from_id
        from .story import confirm_beats, likely_uploads, missing_searches, suggest_links
        likely = likely_uploads(self.google, story, self.found["candidates"], self.movie)
        self.place([v for ids in likely.values() for v in ids[:2]])
        covered = placed_beats(story, self.units())
        missing = [i for i in range(len(story["beats"])) if i not in covered]
        confirmed: dict = {}
        watched: set = set()
        if missing:
            try:  # real links from Google Search, for the beats still missing
                known = {c["id"]: c for c in self.found["candidates"]}
                for beat_index, ids in suggest_links(self.google, self.movie, story).items():
                    if beat_index not in missing:
                        continue
                    for vid in ids:
                        if vid not in known:
                            made = candidate_from_id(self.youtube, vid, self.movie, story["beats"][beat_index]["search"])
                            if not made:
                                continue
                            known[vid] = made
                            self.found["candidates"].insert(0, made)
                        known[vid].setdefault("suggested_for", []).append(beat_index)
            except gem.GeminiUnavailable as exc:
                self.log(f"no suggested links: {str(exc)[:100]}")
            confirmed = confirm_beats(self.google, story, self.found["candidates"], self.movie, log=self.log,
                                      only=set(missing), checked=watched)
        for round_ in range(rounds):
            missing = [i for i in range(len(story["beats"])) if i not in covered and i not in confirmed]
            if not missing:
                break
            if self.thin():
                self.widen()
            try:
                retry = missing_searches(self.google, self.movie, story, missing, self.found["queries"])
            except gem.GeminiUnavailable as exc:
                self.log(f"no new searches for missing beats: {str(exc)[:100]}")
                break
            self.report["rounds"] += 1
            self.log(f"round {round_ + 2} for '{story['title']}': {len(missing)} beats missing; searches {retry}")
            if not retry:
                break
            self.search(retry)
            likely = likely_uploads(self.google, story, self.found["candidates"], self.movie)
            self.place([v for i in missing for v in likely.get(i, [])[:2]], extra=0)
            covered |= placed_beats(story, self.units()) & set(missing)
            still = [i for i in missing if i not in covered]
            if still:
                confirmed.update(confirm_beats(self.google, story, self.found["candidates"], self.movie, log=self.log,
                                               only=set(still), checked=watched))
        if confirmed:  # confirmed uploads are placed too: subtitles sharpen their cuts
            self.place([c["id"] for c in confirmed.values()], extra=0)
        self.log(f"'{story['title']}': {len(covered)} beats by subtitles, {len(confirmed)} by watching, "
                 f"{len(story['beats']) - len(covered | set(confirmed))} missing")
        return confirmed, covered


ACTION = re.compile(r"\b(crime|attack|ambush|kill|killing|murder|fight|shoot|shootout|stab|chase|escape|rescue|"
                    r"break[- ]in|theft|steal|explosion|assault|hit|inciting|breach|gunfight)", re.I)


USABLE_SHARE = 0.7    # a script needs footage for most of its scenes, and footage for most of the requested length


def usable(story: dict, have: set) -> bool:
    """Enough of the story has footage: at least 3 scenes and 70% of them (a 6-scene script needs 5).
    Half a story makes a short Short full of jumps."""
    import math
    n = len(story.get("beats") or [])
    return len(have) >= max(3, math.ceil(USABLE_SHARE * n))


def script_rank(story: dict, have: set) -> float:
    """How good a script will look on screen with the footage found: share of its scenes with footage,
    minus a heavy cost for each turning-point ACTION scene without footage (a story that has to talk
    about its attack instead of showing it), plus a little for the editor's score."""
    beats = story.get("beats") or []
    if not beats:
        return 0.0
    share = sum(1 for i in range(len(beats)) if i in have) / len(beats)
    lost_action = sum(1 for i, b in enumerate(beats) if i not in have
                      and ACTION.search(f"{b.get('role', '')} {b.get('what_we_see', '')}"))
    editor = float((story.get("editor") or {}).get("score") or 6)
    return round(10 * share - 3 * lost_action + 0.3 * editor, 2)


def rank_results(results: list[dict], wanted: int) -> list[dict]:
    """Usable scripts best first (only the best `wanted` stay usable); unusable ones after them."""
    usable = sorted((r for r in results if r["ok"]), key=lambda r: (-r["rank"], r["n"]))
    for r in usable[wanted:]:
        r["ok"] = False
    return usable + [r for r in results if r not in usable]


def run(google, research: dict, transcript, plot: str, youtube, workdir: Path, *, length: float, wanted: int,
        screen, footage: str = "auto", use_whisper: bool = True, log=_log, hunt: Hunt | None = None) -> dict:
    """Script first → hunt → fallbacks. Returns {'arcs', 'planned', 'found', 'placed', 'screened', 'report'};
    'arcs' is empty when every story path failed (the caller then uses the old stories)."""
    from . import gemini as gem
    from .story import beat_searches, general_searches, stories_to_arcs
    hunt = hunt or Hunt(google, research, youtube, workdir, footage=footage, use_whisper=use_whisper, log=log)
    report = hunt.report
    count = min(6, wanted + 1)  # one spare script per Short
    try:
        planned = plan_scripts(google, research, transcript, plot, length, count, log=log)
    except gem.GeminiUnavailable as exc:
        log(f"no script plan: {str(exc)[:160]}")
        planned = []
    try:
        broad = general_searches(google, research["movie"], plot)
    except gem.GeminiUnavailable:
        broad = []
    log(f"searches: general {broad}; per beat {beat_searches(planned)}")
    hunt.search(broad + beat_searches(planned))
    if hunt.thin():
        hunt.widen()
    rounds = 1 if footage == "plenty" else 2
    results: list[dict] = []

    def hunt_scripts(stop_when_complete: bool) -> None:
        for n, story in enumerate(planned):
            if any(r["n"] == n for r in results):
                continue
            # Spare scripts are hunted only while the scripts so far miss scenes.
            if stop_when_complete and sum(1 for r in results if r["ok"] and r["complete"]) >= wanted:
                break
            confirmed, covered = hunt.footage_for(story, rounds=rounds)
            have = covered | set(confirmed)
            results.append({"n": n, "confirmed": confirmed, "ok": usable(story, have), "scenes_before": len(have),
                            "complete": len(have) >= len(story["beats"]), "rank": script_rank(story, have)})

    hunt_scripts(True)
    # Footage counts only once it passes screening: every script with enough scenes is screened and cut,
    # then the best of what really remains wins.
    arcs, screened = _arcs(hunt, planned, results, length, screen)
    arcs = best_arcs(arcs, planned, wanted, results, screened, log, length)
    if len(arcs) < wanted and len(results) < len(planned):  # too little left of the scripts so far: the spares
        log("the scripts so far lack footage (after screening): hunting the spare scripts")
        hunt_scripts(False)
        arcs, screened = _arcs(hunt, planned, results, length, screen)
        arcs = best_arcs(arcs, planned, wanted, results, screened, log, length)
    report["path"] = "script"
    if not arcs and hunt.found["candidates"]:
        # Every script lacked footage: plan from the footage that exists instead.
        log("fallback: re-planning the story from the uploads that exist")
        report["path"] = "footage-aware re-plan"
        try:
            replanned = plan_scripts(google, research, transcript, plot, length, min(3, wanted + 1),
                                     uploads=hunt.found["candidates"], log=log)
        except gem.GeminiUnavailable as exc:
            log(f"no re-plan: {str(exc)[:120]}")
            replanned = []
        results = []
        for n, story in enumerate(replanned):
            confirmed, covered = hunt.footage_for(story, rounds=0)
            results.append({"n": n, "confirmed": confirmed, "ok": usable(story, covered | set(confirmed)),
                            "scenes_before": len(covered | set(confirmed))})
        arcs, screened = _arcs(hunt, replanned, results, length, screen)
        arcs = best_arcs(arcs, replanned, wanted, results, screened, log, length)
        planned = replanned
    if not arcs:
        report["path"] = "scene-by-scene (no story had footage)"
    arcs = arcs[:wanted]
    for arc in arcs:
        arc["found_by"] = {s["beat"]["name"]: ("watching" if s.get("confirmed") else "subtitles")
                           for s in arc["scenes"]}
    report["stories"] = [{"title": a["story"]["title"], "scenes": len(a["scenes"]),
                          "missing": [m["name"] for m in a.get("missing", [])], "found_by": a["found_by"]} for a in arcs]
    return {"arcs": arcs, "planned": planned, "found": hunt.found, "placed": hunt.placed, "screened": screened,
            "report": report}


def best_arcs(arcs: list[dict], stories: list[dict], wanted: int, results: list[dict], screened: dict, log,
              length: float = 0.0) -> list[dict]:
    """Arcs ranked by the scenes that survived screening (a missing action scene costs most); the best `wanted`.
    An arc with too few of its scenes left, or with footage for under 70% of the requested length, is dropped.
    Logs, per script, its scenes before and after screening and what screening rejected."""
    keep = [r for r in results if r["ok"]]
    rejected = {cid: "; ".join(row.get("reasons") or ["rejected"]) for cid, row in (screened or {}).items()
                if row.get("accept") is False}
    scored = []
    for arc in arcs:
        r = keep[arc["story_index"]] if arc.get("story_index") is not None and arc["story_index"] < len(keep) else None
        story = stories[r["n"]] if r else None
        if story is None:
            continue
        names = {s["beat"]["name"] for s in arc["scenes"]}
        have = {i for i, b in enumerate(story["beats"]) if b["name"] in names}
        rank = script_rank(story, have)
        footage = sum(sc["clip_end"] - sc["clip_start"] for sc in arc["scenes"])
        log(f"script {r['n'] + 1} '{story['title']}': {r.get('scenes_before', '?')} scenes found, "
            f"{len(arc['scenes'])} after screening, {footage:.0f} s of footage, rank {rank}")
        if not usable(story, have):
            log(f"script {r['n'] + 1}: too few of its scenes left after screening")
            continue
        if length and footage < USABLE_SHARE * length:
            log(f"script {r['n'] + 1}: footage for only {footage:.0f} s of a {length:.0f} s Short")
            continue
        scored.append((rank, r["n"], arc))
    for r in keep:
        if not any(n == r["n"] for _, n, _ in scored):
            log(f"script {r['n'] + 1} '{stories[r['n']]['title']}': {r.get('scenes_before', '?')} scenes found, "
                f"too few left after screening")
    if rejected:
        log("screening rejected: " + "; ".join(f"{cid}: {why}" for cid, why in list(rejected.items())[:8]))
    scored.sort(key=lambda row: (-row[0], row[1]))
    out = [arc for _, _, arc in scored[:wanted]]
    for i, arc in enumerate(out):
        arc["id"] = f"arc{i + 1}"
    return out


def _arcs(hunt: Hunt, stories: list[dict], results: list[dict], length: float, screen) -> tuple[list, dict]:
    """Screen the footage the stories use, then cut every story with enough beats into an arc."""
    from .story import stories_to_arcs
    keep = [r for r in results if r["ok"]]
    if not keep:
        return [], {}
    confirmed = {i: r["confirmed"] for i, r in enumerate(keep)}
    chosen = [stories[r["n"]] for r in keep]
    first = {c["id"] for r in keep for c in r["confirmed"].values()}
    for story in chosen:  # clips that cover beats by placement are screened first too
        for u in hunt.units():
            if any(min(u.movie_end, b["movie_end"]) - max(u.movie_start, b["movie_start"]) > 3 for b in story["beats"]):
                first.add(u.clip_id)
    screened = screen(hunt.placed, first) if screen else {}
    arcs = stories_to_arcs(chosen, hunt.units(screened), length, confirmed=confirmed,
                           clips={c["id"]: c for c in hunt.placed["clips"]}, screening=screened)
    return arcs, screened

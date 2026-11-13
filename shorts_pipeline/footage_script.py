"""Steps 4-5 of the footage-first script: Gemini writes the Short line by line from the watched events.

Gemini gets the story (spine, story map, hook and ending ideas), the story-first narration written at
planning time, and the events it logged while watching each scene's footage. It writes one merged script:
every narration line is tied to exactly ONE event that shows it and names its key word (the word whose
action happens at the event's peak). A strict editor then checks the script once against the events:
is the story complete, does every line describe its event, is anything trivial?

Local checks keep it honest: a line must point at a real event of its own scene, trivial events are
not narrated, a line may not be much longer than its footage can carry, near-duplicate lines are dropped,
and a line may not name people the events and the brief never mention. Rewrites happen here, before the
narrator records anything.
"""
from __future__ import annotations

import json
import re
import sys

WORDS_PER_SECOND = 2.9
EXTEND = 6.0          # seconds of footage around an event a line may also use (same scene)
TRIVIAL = 3           # events this unimportant are never narrated

LINE = {"type": "object", "properties": {
    "scene": {"type": "integer"}, "kind": {"type": "string", "enum": ["narration", "movie_line"]},
    "event": {"type": "string"}, "text": {"type": "string"}, "key_word": {"type": "string"},
    "line_id": {"type": "string"}},
    "required": ["scene", "kind", "event", "text", "key_word"]}
SCRIPT_SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"},
    "hook": {"type": "object", "properties": {"text": {"type": "string"}, "event": {"type": "string"},
                                              "key_word": {"type": "string"}},
             "required": ["text", "event", "key_word"]},
    "lines": {"type": "array", "items": LINE},
    "problems": {"type": "array", "items": {"type": "string"}}},
    "required": ["title", "hook", "lines"]}

WRITE_PROMPT = """You write the narration of a viral movie-recap YouTube Short (about {seconds} seconds) for {movie}.
You have the STORY (planned before anyone watched the footage), the STORY-FIRST NARRATION of each scene, and the
EVENTS that were logged by watching each scene's actual footage (times in seconds, what is visible, importance).

Write ONE script that merges both, line by line:
- Every narration line is tied to exactly ONE event of its own scene ("event": its id) and describes what that event
  SHOWS: the person, the action, the object. If a line says someone dies, it is tied to the event that shows the
  attack or the dying, and the next line to the next event (attack, fall, dying are separate lines and events).
- key_word: the word of the line whose action happens at the event's peak (e.g. "stabs", "rings", "falls").
- Keep the story-first narration's story, facts and bridges, but rewrite each sentence to what its event shows.
  At most one short clause per scene about something not on screen (who someone is, why it matters).
- Never narrate trivial or off-story events (importance {trivial} or less: walking, waiting, painting a wall...),
  and never write a line about something no event shows.
- The story must be complete for someone who never saw the movie: setup, escalation, the turn, and a cliffhanger,
  with no missing link between scenes. Hook first: one line (at most 14 words) tied to the event it describes.
- Length: about {words} words of narration in total. A line may not be longer than its event can carry: about
  max_words for that event (its seconds plus a few seconds around it). Split long thoughts over consecutive events.
- Movie lines: you may play up to 3 of the listed original movie lines ("kind": "movie_line", "line_id"), where they
  punch hardest; they need no event (use "" as event).
- Present tense, third person, short spoken sentences, no quotes, no "meanwhile", no camera talk, no names that are
  not in the story, the events or the movie lines.

STORY: {story}
SCENES (story-first narration, events and movie lines):
{scenes}"""

CHECK_PROMPT = """You are the strict editor of this movie-recap Short script for {movie}, before it is recorded.
Each narration line is tied to an event of the footage (below). Fix the script and return it in the same form:
- Every line must describe what its event shows (who, action, object). Retie or rewrite lines that do not.
- Remove trivial lines (events of importance {trivial} or less, or anything off the story).
- The story must be complete and clear for a new viewer: setup, escalation, turn, cliffhanger; add a short bridge
  where a link is missing (tied to an event of that scene).
- Keep the length (about {words} words) and each line within its event's max_words.
- List what you changed in "problems".
EVENTS:
{scenes}
SCRIPT:
{script}"""


def event_table(arc: dict, movie_lines: dict | None = None) -> tuple[dict[str, dict], list[dict]]:
    """({event id: event with scene}, per-scene rows for the prompt)."""
    events, rows = {}, []
    for i, scene in enumerate(arc.get("scenes") or []):
        mine = []
        for j, e in enumerate(scene.get("events") or []):
            eid = f"s{i}e{j}"
            seconds = e["end"] - e["start"]
            events[eid] = {**e, "scene": i, "clip_id": scene["clip_id"], "id": eid}
            mine.append({"id": eid, "seconds": round(seconds, 1), "what": e["what"], "who": e.get("who", ""),
                         "on_screen": e.get("on_screen", ""), "importance": e.get("importance", 5),
                         "max_words": max_words(e)})
        beat = scene.get("beat") or {}
        rows.append({"scene": i, "role": beat.get("role", ""), "must_show": beat.get("what_we_see", ""),
                     "story_first_narration": beat.get("narration", ""), "events": mine,
                     "movie_lines": [{"line_id": k, "text": v["text"]} for k, v in (movie_lines or {}).items()
                                     if v.get("scene") == i][:6]})
    return events, rows


def max_words(event: dict) -> int:
    return max(5, int((event["end"] - event["start"] + EXTEND) * WORDS_PER_SECOND))


def _names(text: str) -> set[str]:
    return {re.sub(r"['’]s$", "", w.lower()) for w in re.findall(r"\b[A-Z][a-zA-Z'’-]+", text or "")}


def _near_duplicate(a: str, b: str) -> bool:
    wa = {w for w in re.findall(r"[a-z']+", a.lower()) if len(w) > 2}
    wb = {w for w in re.findall(r"[a-z']+", b.lower()) if len(w) > 2}
    return len(wa) >= 4 and len(wb) >= 4 and len(wa & wb) / min(len(wa), len(wb)) > 0.8


def _trim(text: str, limit: int) -> str:
    """Cut a too-long line back to its last clause or sentence end within the limit."""
    words = text.split()
    if len(words) <= limit:
        return text
    cut = " ".join(words[:limit])
    end = max(cut.rfind(","), cut.rfind("."), cut.rfind(";"))
    cut = cut[:end] if end > len(cut) // 2 else cut
    return cut.rstrip(",;: ") + "."


def validate(raw: dict, events: dict[str, dict], movie_lines: dict, allowed: set[str]) -> tuple[dict | None, list[str]]:
    """The usable script (hook and lines tied to real events), and what was dropped or changed."""
    notes: list[str] = []
    lines, seen, played = [], [], 0
    for row in (raw or {}).get("lines") or []:
        kind, text = row.get("kind", "narration"), " ".join(str(row.get("text", "")).split())
        if kind == "movie_line":
            lid = str(row.get("line_id") or "")
            if lid in movie_lines and played < 3:
                lines.append({"kind": "movie_line", "scene": movie_lines[lid]["scene"], "line_id": lid})
                played += 1
            continue
        event = events.get(str(row.get("event")))
        if not text or event is None or event["scene"] != row.get("scene", event["scene"]):
            notes.append(f"dropped (no matching event): {text[:60]}")
            continue
        if event.get("importance", 5) <= TRIVIAL:
            notes.append(f"dropped (trivial event '{event['what'][:40]}'): {text[:60]}")
            continue
        new_names = _names(text) - allowed - {text.split()[0].lower().strip(",.")}
        if new_names:
            notes.append(f"dropped (names not in the story: {', '.join(sorted(new_names))}): {text[:60]}")
            continue
        if any(_near_duplicate(text, other) for other in seen):
            notes.append(f"dropped (repeats an earlier line): {text[:60]}")
            continue
        limit = max_words(event)
        if len(text.split()) > 1.3 * limit:
            notes.append(f"shortened to its footage ({len(text.split())} → {limit} words): {text[:60]}")
            text = _trim(text, limit)
        key = str(row.get("key_word") or "").strip().lower().strip(".,!?")
        words = [w.lower().strip(".,!?;:'\"") for w in text.split()]
        if key not in words:  # the key word must be in the line: else its longest action-like word
            key = max(words, key=len) if words else ""
        seen.append(text)
        lines.append({"kind": "narration", "scene": event["scene"], "event": event["id"], "text": text, "key_word": key})
    hook = (raw or {}).get("hook") or {}
    hook_event = events.get(str(hook.get("event")))
    hook_text = " ".join(str(hook.get("text", "")).split())
    narrated = [x for x in lines if x["kind"] == "narration"]
    if len(narrated) < 3 or not hook_text:
        return None, notes + ["too few lines tied to the footage"]
    if hook_event is None:
        hook_event = events[narrated[0]["event"]]
    hook_key = str(hook.get("key_word") or "").lower()
    if hook_key not in [w.lower().strip(".,!?") for w in hook_text.split()]:
        hook_key = max(hook_text.split(), key=len).lower().strip(".,!?")
    return {"title": str(raw.get("title") or "")[:90], "hook": {"text": hook_text, "event": hook_event["id"],
                                                                 "key_word": hook_key}, "lines": lines}, notes


def _event_ref(event: dict) -> dict:
    return {k: event[k] for k in ("id", "clip_id", "start", "end", "peak", "what")}


def to_script(merged: dict, events: dict[str, dict], old: dict) -> dict:
    """The writer's script format: narration beats per scene (their lines keep event and key word), movie
    lines as dialogue beats, the hook tied to its event (shown first as a flash-forward when it is later)."""
    beats: list[dict] = []
    for line in merged["lines"]:
        if line["kind"] == "movie_line":
            beats.append({"scene": line["scene"], "kind": "dialogue", "line": line["line_id"]})
            continue
        item = {"text": line["text"], "key_word": line["key_word"], "event": _event_ref(events[line["event"]])}
        if beats and beats[-1]["kind"] == "narration" and beats[-1]["scene"] == line["scene"]:
            beats[-1]["text"] += " " + line["text"]
            beats[-1]["lines"].append(item)
        else:
            beats.append({"scene": line["scene"], "kind": "narration", "text": line["text"], "lines": [item]})
    hook_event = events[merged["hook"]["event"]]
    return {**old, "title": merged["title"] or old.get("title", ""), "hook": merged["hook"]["text"],
            "hook_scene": hook_event["scene"],
            "hook_line": {"text": merged["hook"]["text"], "key_word": merged["hook"]["key_word"],
                          "event": _event_ref(hook_event)},
            "beats": beats, "footage_first": True}


def write(gemini, arc: dict, result: dict, movie: dict, *, seconds: float, log=None) -> tuple[dict | None, list[str]]:
    """(the new script, notes) or (None, notes) when the footage-first script could not be made; the caller
    then keeps the plan-based script."""
    from . import gemini as gem
    log = log or (lambda m: print(m, file=sys.stderr, flush=True))
    movie_lines = dict(result.get("movie_lines") or result.get("dialogue_lines") or {})
    events, rows = event_table(arc, movie_lines)
    if sum(1 for s in arc.get("scenes") or [] if s.get("events")) < max(2, len(arc.get("scenes") or []) // 2):
        return None, ["too few scenes were watched"]
    story = {k: v for k, v in (arc.get("story") or {}).items() if k in
             ("title", "spine", "story_map", "hook_idea", "ending_idea", "ending_mode", "hook")}
    allowed = _names(json.dumps(story, ensure_ascii=False)) | _names(json.dumps(rows, ensure_ascii=False)) | \
        _names(json.dumps(result.get("brief") or {}, ensure_ascii=False)) | _names(movie.get("title", ""))
    words = int(seconds * WORDS_PER_SECOND * 0.85)
    title = f"{movie.get('title')} ({movie.get('year')})"
    try:
        raw = gemini.generate("smart", [{"text": WRITE_PROMPT.format(
            seconds=int(seconds), movie=title, trivial=TRIVIAL, words=words, story=json.dumps(story, ensure_ascii=False),
            scenes=json.dumps(rows, ensure_ascii=False))}], schema=SCRIPT_SCHEMA, temperature=0.5, max_tokens=8192)
    except gem.GeminiUnavailable as exc:
        return None, [f"no footage-first script: {str(exc)[:160]}"]
    merged, notes = validate(raw, events, movie_lines, allowed)
    if merged is None:
        return None, notes
    try:  # step 5: the strict editor reads it once against the events
        checked = gemini.generate("smart", [{"text": CHECK_PROMPT.format(
            movie=title, trivial=TRIVIAL, words=words, scenes=json.dumps(rows, ensure_ascii=False),
            script=json.dumps(merged, ensure_ascii=False))}], schema=SCRIPT_SCHEMA, temperature=0.2, max_tokens=8192)
        fixed, fix_notes = validate(checked, events, movie_lines, allowed)
        if fixed is not None and len(fixed["lines"]) >= 0.7 * len(merged["lines"]):
            notes += [f"editor: {p[:120]}" for p in (checked.get("problems") or [])[:8]] + fix_notes
            merged = fixed
    except gem.GeminiUnavailable as exc:
        notes.append(f"no script check: {str(exc)[:120]}")
    script = to_script(merged, events, result.get("script") or {})
    log(f"Footage-first script: {sum(1 for x in merged['lines'] if x['kind'] == 'narration')} lines tied to events, "
        f"{sum(len(x['text'].split()) for x in merged['lines'] if x['kind'] == 'narration')} words")
    return script, notes

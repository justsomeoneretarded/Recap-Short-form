"""Before the voice is made, the script is fitted to the footage that exists.

1. Every scene's footage is checked against what the scene must show. Gemini looks at a contact
   sheet of a wider window of the clip (the planned stretch ±60 s, or the whole clip when it is
   short) and says where the moment really is, so a mis-placed stretch (the wrong part of a
   compilation) moves to the right seconds.
2. Every narration sentence is checked against that scene's frames. A sentence no footage shows is
   rewritten to say the same story fact through what IS on screen (who, action, object), so the
   picture and the words match before the narrator records anything.

A rewrite that brings in a name or a quote the script did not have is refused: the original stays.
Without Gemini or footage nothing changes.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

WINDOW_PAD = 60.0         # seconds around the planned stretch that Gemini may move the scene to
WHOLE_CLIP = 300.0        # clips up to this long are shown whole
FRAMES_PER_SCENE = 48

ALIGN_SCHEMA = {"type": "object", "properties": {"scenes": {"type": "array", "items": {"type": "object", "properties": {
    "scene": {"type": "integer"},
    "shows_scene": {"type": "boolean"},
    "start": {"type": "number"},
    "end": {"type": "number"},
    "sentences": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"}, "shown": {"type": "boolean"}, "rewrite": {"type": "string"}},
        "required": ["n", "shown"]}}},
    "required": ["scene", "shows_scene", "start", "end", "sentences"]}}}, "required": ["scenes"]}


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text or "") if x.strip()]


def _names(text: str) -> set[str]:
    return {re.sub(r"['’]s$", "", w.lower()) for w in re.findall(r"\b[A-Z][a-zA-Z'’-]+", text or "")}


def window(scene: dict, duration: float) -> tuple[float, float]:
    """The stretch of the clip Gemini sees for a scene."""
    if duration and duration <= WHOLE_CLIP:
        return 0.0, duration
    lo = max(0.0, scene["clip_start"] - WINDOW_PAD)
    hi = scene["clip_end"] + WINDOW_PAD
    return lo, min(hi, duration) if duration else hi


def scene_sentences(script: dict) -> dict[int, list[tuple[int, int, str]]]:
    """Per scene: (beat index, sentence index in the beat, sentence) of its narration."""
    out: dict[int, list[tuple[int, int, str]]] = {}
    for b, beat in enumerate(script.get("beats") or []):
        if beat.get("kind") == "dialogue":
            continue
        for k, sentence in enumerate(_sentences(beat.get("text") or "")):
            out.setdefault(beat.get("scene", 0), []).append((b, k, sentence))
    return out


def acceptable(original: str, rewrite: str, allowed: set[str]) -> bool:
    """A rewrite keeps the script's facts: no new names, no quotes, about the same length."""
    rewrite = " ".join(str(rewrite or "").split())
    if not rewrite or re.search(r"[\"“”]", rewrite):
        return False
    n_old, n_new = len(original.split()), len(rewrite.split())
    if not 0.5 * n_old <= n_new <= 1.5 * n_old + 3:
        return False
    first = rewrite.split()[0].lower().strip(",.") if rewrite.split() else ""
    new_names = _names(rewrite) - _names(original) - allowed - {first}
    return not new_names


def align_story(gemini, arc: dict, result: dict, footage: dict, work: Path, *, probe=None) -> tuple[dict, dict, list]:
    """(arc with corrected scene windows, result with the fitted script, notes). Never raises."""
    from . import gemini as gem
    from .story import fit_to_narration
    notes: list[str] = []
    if gemini is None or not footage:
        return arc, result, notes
    if probe is None:
        from .media import probe
    arc, result = copy.deepcopy(arc), copy.deepcopy(result)
    script = result["script"]
    by_scene = scene_sentences(script)
    sheets, windows, parts, rows = [], {}, [], []
    try:
        for i, scene in enumerate(arc.get("scenes") or []):
            video = footage.get(scene["clip_id"])
            if not video:
                continue
            duration = float((probe(Path(video)) or {}).get("duration") or 0)
            lo, hi = window(scene, duration)
            step = max(1.0, (hi - lo) / FRAMES_PER_SCENE)
            frames = gem._frames(video, lo, hi, step, Path(work) / f"align{i}")
            image = gem._sheet(frames, f"SCENE {i}")
            if image is None:
                continue
            windows[i] = (lo, hi)
            parts += [{"text": f"Scene {i} contact sheet (tile labels are clip seconds):"}, gem._image_part(image)]
            rows.append({"scene": i, "must_show": scene["beat"].get("what_we_see", ""),
                         "planned_seconds": [round(scene["clip_start"], 1), round(scene["clip_end"], 1)],
                         "sentences": [{"n": n, "text": s} for n, (_, _, s) in enumerate(by_scene.get(i, []))]})
            sheets.append(i)
        if not rows:
            return arc, result, notes
        parts.append({"text": (
            "You are the editor of a movie-recap Short. For every scene below you see a contact sheet of its footage "
            "(tiles labelled with clip seconds). 1) shows_scene: does the footage contain what the scene must show? "
            "start/end: the clip seconds where it is (the whole stretch the narration can play over; use the planned "
            "seconds if they are right). 2) For every narration sentence of the scene: shown = true if the frames show "
            "what it says (the person, the action, the object). If not, rewrite it: the SAME story fact, told through "
            "what the frames DO show, same tone and about the same length, present tense, no quotes, no names that are "
            "not already in the sentences. Leave rewrite empty when shown is true.\nSCENES:\n" +
            json.dumps(rows, ensure_ascii=False))})
        reply = gemini.generate("smart", parts, schema=ALIGN_SCHEMA, temperature=0.2, low_media=True)
    except gem.GeminiUnavailable as exc:
        print(f"No script alignment: {str(exc)[:160]}", file=sys.stderr)
        return arc, result, notes
    except Exception as exc:  # noqa: BLE001 - alignment is a bonus; never lose the Short over it
        print(f"No script alignment: {type(exc).__name__}: {str(exc)[:160]}", file=sys.stderr)
        return arc, result, notes
    allowed = _names(json.dumps(arc.get("story") or {}, ensure_ascii=False)) | \
        _names(" ".join(s["beat"].get("narration", "") for s in arc["scenes"])) | \
        _names(json.dumps(result.get("brief") or {}, ensure_ascii=False))
    lines = {k: v for k, v in (result.get("dialogue_lines") or {}).items()}
    for row in reply.get("scenes") or []:
        i = row.get("scene")
        if i not in windows:
            continue
        scene, (lo, hi) = arc["scenes"][i], windows[i]
        try:
            start, end = float(row.get("start")), float(row.get("end"))
        except (TypeError, ValueError):
            start = end = None
        if row.get("shows_scene") and start is not None and lo <= start < end <= hi + 0.5 and end - start >= 3:
            text = " ".join(s for _, _, s in by_scene.get(i, []))
            start, end = fit_to_narration(start, min(end, hi), lo, hi, {"narration": text})
            for line in lines.values():  # movie lines played from this scene stay inside it
                if line.get("scene") == i:
                    start, end = min(start, line["clip_start"]), max(end, line["clip_end"])
            moved = abs(start - scene["clip_start"]) > 2 or abs(end - scene["clip_end"]) > 2
            if moved:
                shift = scene["movie_start"] - scene["clip_start"]
                notes.append(f"scene {i} footage moved {scene['clip_start']:.0f}-{scene['clip_end']:.0f}s → "
                             f"{start:.0f}-{end:.0f}s (what it must show is there)")
                scene.update(clip_start=round(start, 2), clip_end=round(end, 2),
                             movie_start=round(start + shift, 1), movie_end=round(end + shift, 1), aligned=True)
        elif not row.get("shows_scene"):
            notes.append(f"scene {i}: the footage does not show '{scene['beat'].get('what_we_see', '')[:80]}'")
        sentences = by_scene.get(i, [])
        for s in row.get("sentences") or []:
            n = s.get("n")
            if not isinstance(n, int) or not 0 <= n < len(sentences) or s.get("shown") is not False:
                continue
            b, k, original = sentences[n]
            rewrite = " ".join(str(s.get("rewrite") or "").split())
            if acceptable(original, rewrite, allowed):
                beat = script["beats"][b]
                parts_ = _sentences(beat["text"])
                if k < len(parts_) and parts_[k] == original:
                    parts_[k] = rewrite
                    beat["text"] = " ".join(parts_)
                    notes.append(f"rewritten to the picture: '{original[:70]}' → '{rewrite[:70]}'")
            else:
                notes.append(f"not shown, kept (no safe rewrite): '{original[:70]}'")
    if notes:
        print("Script alignment:\n  " + "\n  ".join(notes), file=sys.stderr)
    return arc, result, notes

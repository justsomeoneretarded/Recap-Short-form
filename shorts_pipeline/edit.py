"""Edit decision list: which seconds of which clip play under each voice beat.

- The story moves forward: within a scene, footage is taken in clip order.
- Movie-line beats play their exact clip window, picture and sound in sync.
- Narration beats take the footage between the previous and the next movie line. When there
  is more footage than voice, the most interesting pieces are kept (Most Replayed and
  comment peaks, then evenly spread), cut on the clip's own shot changes. When there is less,
  the footage is gently slowed (≥0.8x) and then the scene's unused earlier footage fills in.
- Cuts follow the narration: every narration beat is split into clause slots (sentence and
  clause ends, from the voice's word timings), 1.5–4.5 s each, and every slot gets its own
  footage, so the picture changes when the story does.
- When Gemini watched the clips, each narration beat prefers the pieces that show what the
  sentence talks about (embedding or word match against the moment descriptions), strong
  moments over weak ones, and skips dead moments (nothing happening).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

MIN_SHOT, MAX_SHOT = 1.3, 2.8  # pieces cut from the footage (reference Shorts: median shot 1.5–2.9 s)
SLOT_MIN, SLOT_MAX = 1.5, 4.5  # one clause of narration on screen: merged when shorter, split when longer
CLAUSE_END = (".", "!", "?", ";", ":", ",", "—", "–")
MIN_SPEED = 0.8


def shot_changes(video: Path, start: float, end: float, threshold: float = 12.0) -> list[float]:
    """Cut times (clip clock) inside [start, end] from FFmpeg's scene detector."""
    log = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{end - start:.3f}",
                          "-vf", f"scale=320:-2,scdet=threshold={threshold}", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    times = [start + float(t) for t in re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", log)]
    return sorted(t for t in times if start < t < end)


def _pieces(a: float, b: float, cuts: list[float], avoid: list | None = None) -> list[tuple[float, float]]:
    """Split [a, b] at shot changes, then into pieces no longer than MAX_SHOT; skip `avoid` ranges."""
    if avoid:
        pieces = []
        start = a
        for lo, hi in sorted(avoid):
            if hi <= start or lo >= b:
                continue
            if lo - start >= 0.5:
                pieces += _pieces(start, lo, cuts)
            start = max(start, hi)
        if b - start >= 0.5:
            pieces += _pieces(start, b, cuts)
        return pieces
    edges = [a] + [c for c in cuts if a + 0.3 < c < b - 0.3] + [b]
    pieces = []
    for s, e in zip(edges, edges[1:]):
        while e - s > MAX_SHOT * 1.5:
            pieces.append((s, s + MAX_SHOT))
            s += MAX_SHOT
        if e - s >= 0.5:
            pieces.append((s, e))
    return pieces


STOP = set("a an the and or but so then of to in on at for with by from into onto his her their its he she they "
           "it is are was were be as that this who what when while out up down off over".split())


def _words(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z']+", text.lower()) if w not in STOP and len(w) > 2}


def word_match(text: str, what: str) -> float:
    """0..1 overlap of content words between a narration sentence and a moment description."""
    a, b = _words(text), _words(what)
    return len(a & b) / max(1, min(len(a), len(b))) if a and b else 0.0


def _moment_at(moments: list[dict], t: float) -> dict | None:
    return next((m for m in moments if m["start"] - 0.5 <= t <= m["end"] + 0.5), None)


def choose(pieces: list[tuple[float, float]], need: float, peaks: list[float], *, moments: list[dict] | None = None,
           text: str = "", similar=None) -> list[tuple[float, float]]:
    """Pick pieces (kept in story order) adding up to `need` seconds, preferring peaks, pieces that
    show what the narration says, strong moments, and spread."""
    if not pieces or need <= 0:
        return []
    moments = moments or []
    if moments:  # never spend the Short on dead moments when there is enough other footage
        lively = [p for p in pieces if (_moment_at(moments, (p[0] + p[1]) / 2) or {}).get("intensity", 5) > 2
                  or (_moment_at(moments, (p[0] + p[1]) / 2) or {}).get("story", 5) > 4]
        if sum(e - s for s, e in lively) >= need:
            pieces = lively
    total = sum(e - s for s, e in pieces)
    if total <= need:
        return list(pieces)
    span = (pieces[0][0], pieces[-1][1])
    match = similar or word_match

    def interest(piece: tuple[float, float]) -> float:
        s, e = piece
        near_peak = max((1.0 / (1.0 + abs((s + e) / 2 - p)) for p in peaks), default=0.0)
        moment = _moment_at(moments, (s + e) / 2)
        if not moment:
            return near_peak
        strength = (moment.get("intensity", 5) + moment.get("story", 5)) / 20
        relevance = match(text, moment["what"]) if text else 0.0
        return near_peak + 0.5 * strength + 1.2 * relevance

    chosen: list[tuple[float, float]] = []
    picked = 0.0
    # 1) peaks and the pieces that show what is said, 2) then evenly spread pieces so the scene
    #    still reads from start to end.
    slots_needed = max(1, round(need / ((MIN_SHOT + MAX_SHOT) / 2)))
    top = max(1, len(peaks)) if not moments else max(1, (slots_needed * 2) // 3)
    order = sorted(pieces, key=interest, reverse=True)[:top] if (peaks or moments) else []
    slots = max(1, round(need / ((MIN_SHOT + MAX_SHOT) / 2)))
    spread = [min(pieces, key=lambda p: abs((p[0] + p[1]) / 2 - (span[0] + (span[1] - span[0]) * (k + 0.5) / slots)))
              for k in range(slots)]
    for piece in order + spread + pieces:
        if picked >= need - 0.05:
            break
        if piece in chosen:
            continue
        chosen.append(piece)
        picked += piece[1] - piece[0]
    chosen.sort()
    # Trim the excess from the longest pieces (never below MIN_SHOT).
    excess = picked - need
    while excess > 0.01:
        i = max(range(len(chosen)), key=lambda k: chosen[k][1] - chosen[k][0])
        s, e = chosen[i]
        cut = min(excess, max(0.0, (e - s) - MIN_SHOT)) or min(excess, (e - s) - 0.4)
        if cut <= 0:
            break
        middle = (s + e) / 2  # trim around the middle of the piece's own action
        half = (e - s - cut) / 2
        chosen[i] = (middle - half, middle + half)
        excess -= cut
    return chosen


def _free(start: float, end: float, taken: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Parts of [start, end] not yet used in this Short."""
    spans = [(start, end)]
    for a, b in sorted(taken):
        spans = [piece for s, e in spans for piece in ((s, min(e, a)), (max(s, b), e)) if piece[1] - piece[0] > 0.5]
    return spans


def _extra_footage(arc: dict, scene_index: int, footage: dict, cuts: dict, used: dict, need: float):
    """Unused footage to cover `need` seconds: same scene first, then the story's other scenes,
    then (only if everything was used) a second pass that may repeat footage."""
    order = [scene_index] + [i for i in range(len(arc["scenes"])) if i != scene_index]
    # Last resort: ranges marked to avoid (text cards, overlays) rather than a Short with no picture.
    for allow_repeat, honour_avoid in ((False, True), (True, True), (True, False)):
        for i in order:
            scene = arc["scenes"][i]
            source = footage.get(scene["clip_id"])
            if not source:
                continue
            windows = [(scene["clip_start"], scene["clip_end"])] if allow_repeat else \
                _free(scene["clip_start"], scene["clip_end"], used.get(scene["clip_id"], []))
            for a, b in windows:
                for s, e in _pieces(a, b, cuts.get(scene["clip_id"], []), scene.get("avoid") if honour_avoid else None):
                    take = min(e - s, MAX_SHOT, need)
                    if take < 0.5 and need > 0.5:
                        continue
                    yield scene["clip_id"], source, s, s + take
                    need -= take
                    if need <= 0.25:
                        return


def in_order(pieces: list[tuple[float, float]], need: float) -> list[tuple[float, float]]:
    """The director's pieces in its order, until `need` seconds are covered (the last one trimmed)."""
    out, total = [], 0.0
    for s, e in pieces:
        if total >= need - 0.05:
            break
        take = min(e - s, need - total)
        if take < 0.5 and out:
            break
        out.append((s, s + take))
        total += take
    return out


def clause_slots(beat: dict, length: float) -> list[dict]:
    """The beat's narration cut into clause slots: [{'start', 'end', 'text'}] in beat seconds covering
    [0, length]. Splits at sentence and clause ends (word timings from the voice), merges slots under
    SLOT_MIN into a neighbour and halves slots over SLOT_MAX."""
    words = [w for w in beat.get("words") or [] if str(w.get("word", "")).strip()]
    length = max(0.0, float(length))
    groups: list[list[dict]] = []
    current: list[dict] = []
    for w in words:
        current.append(w)
        if str(w["word"]).rstrip("\"')”’").endswith(CLAUSE_END):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    slots = []
    for i, g in enumerate(groups):
        start = 0.0 if i == 0 else float(g[0]["start"])
        end = length if i == len(groups) - 1 else float(groups[i + 1][0]["start"])
        if end > start:
            slots.append({"start": start, "end": min(end, length), "text": " ".join(str(w["word"]) for w in g)})
    if not slots:
        slots = [{"start": 0.0, "end": length, "text": str(beat.get("text", ""))}] if length > 0 else []
    merged: list[dict] = []
    for slot in slots:  # too short to read as its own shot: joins the clause before it
        if merged and (slot["end"] - slot["start"] < SLOT_MIN or merged[-1]["end"] - merged[-1]["start"] < SLOT_MIN):
            merged[-1] = {"start": merged[-1]["start"], "end": slot["end"], "text": merged[-1]["text"] + " " + slot["text"]}
        else:
            merged.append(dict(slot))
    out: list[dict] = []
    for slot in merged:  # too long for one shot: halves (or more)
        span = slot["end"] - slot["start"]
        parts = max(1, int(-(-span // SLOT_MAX)))
        for k in range(parts):
            out.append({"start": round(slot["start"] + span * k / parts, 3),
                        "end": round(slot["start"] + span * (k + 1) / parts, 3),
                        "text": slot["text"] if parts == 1 else f"{slot['text']} ({k + 1}/{parts})"})
    return out


def beat_slots(voiceover: dict) -> dict[str, list[dict]]:
    """Clause slots of every narration beat, over the time until the next beat starts."""
    beats = voiceover.get("beats") or []
    out = {}
    for i, beat in enumerate(beats):
        if beat.get("kind") == "dialogue":
            continue
        gap = (beats[i + 1]["timeline_start"] - beat["timeline_start"]) if i + 1 < len(beats) else beat["duration"]
        out[beat["id"]] = clause_slots(beat, gap)
    return out


def _slot_picks(pieces: list[tuple[float, float]], slots: list[dict], speed: float, peaks, moments, similar,
                choose_fn) -> list[tuple[float, float]]:
    """Footage per clause slot, moving forward through the scene: each slot's pieces add up to the slot's
    length, so the cuts land on the clause boundaries."""
    picked: list[tuple[float, float]] = []
    for slot in slots:
        need = (slot["end"] - slot["start"]) * speed
        last = picked[-1][1] if picked else None
        unused = [p for p in pieces if not any(min(p[1], q[1]) - max(p[0], q[0]) > 0.05 for q in picked)]
        ahead = [p for p in unused if last is None or p[0] >= last - 0.05]
        pool = ahead if sum(e - s for s, e in ahead) >= need - 0.05 else unused
        got = choose_fn(pool, need, peaks, moments=moments, text=slot.get("text", ""), similar=similar)
        if not got:
            break
        picked += got
    return picked


def build_edl(arc: dict, voiceover: dict, footage: dict[str, str], cuts: dict | None = None, similar=None,
              director: dict | None = None) -> dict:
    """Shots on the output timeline: {clip_id, source, start, end, speed, timeline_start, duration, audio}."""
    cuts = cuts if cuts is not None else {}
    shots: list[dict] = []
    used: dict[str, list[tuple[float, float]]] = {}
    beats = voiceover["beats"]
    scene_cursor: dict[int, float] = {}
    for index, beat in enumerate(beats):
        scene = arc["scenes"][beat["scene"]]
        clip_id = scene["clip_id"]
        source = footage.get(clip_id)
        borrowed = False
        if not source:  # borrow another scene's clip rather than drop the Short
            spare = next((footage[s["clip_id"]] for s in arc["scenes"] if footage.get(s["clip_id"])), None)
            if not spare:
                raise ValueError(f"No footage at all for {arc.get('id')}")
            source = spare
            scene = next(s for s in arc["scenes"] if footage.get(s["clip_id"]) == spare)
            clip_id = scene["clip_id"]
            borrowed = True  # a movie line then plays over borrowed pictures, like narration
        start_t = beat["timeline_start"]
        gap = (beats[index + 1]["timeline_start"] - start_t) if index + 1 < len(beats) else beat["duration"]
        if beat["kind"] == "dialogue" and not borrowed:
            shots.append({"clip_id": clip_id, "source": source, "start": beat["clip_start"],
                          "end": beat["clip_start"] + gap, "speed": 1.0, "timeline_start": start_t,
                          "duration": gap, "audio": "full", "beat": beat["id"]})
            scene_cursor[beat["scene"]] = beat["clip_start"] + gap
            used.setdefault(clip_id, []).append((beat["clip_start"], beat["clip_start"] + gap))
            continue
        a = scene_cursor.get(beat["scene"], scene["clip_start"])
        upcoming = [b for b in beats[index + 1:] if b["kind"] == "dialogue" and b["scene"] == beat["scene"]]
        b = upcoming[0]["clip_start"] if upcoming else scene["clip_end"]
        if b - a < gap / (1 / MIN_SPEED):  # not enough fresh footage: reuse the scene from its start
            a = scene["clip_start"]
        clip_cuts = cuts.get(clip_id, [])
        pieces = _pieces(a, max(a + 0.5, b), clip_cuts, scene.get("avoid"))
        if not pieces:  # everything here is marked to avoid: the scene's own footage beats no picture
            pieces = _pieces(a, max(a + 0.5, b), clip_cuts)
        chosen_by_director = []
        for lo, hi in (director or {}).get(beat["id"], []):  # the moments that show what this sentence says
            lo, hi = max(lo, scene["clip_start"]), min(hi, scene["clip_end"])
            if hi - lo >= 0.5 and not borrowed:
                chosen_by_director += _pieces(lo, hi, clip_cuts, scene.get("avoid"))
        if sum(e - s for s, e in chosen_by_director) >= 0.6 * gap:
            available = sum(e - s for s, e in chosen_by_director)
            speed = 1.0 if available >= gap else max(MIN_SPEED, available / gap)
            need = gap * speed
            picked = in_order(chosen_by_director, need)
        else:
            available = sum(e - s for s, e in pieces)
            speed = 1.0 if available >= gap else max(MIN_SPEED, available / gap)
            need = gap * speed
            slots = clause_slots(beat, gap)
            # One stretch of footage per clause, when the voice's word times say where the clauses are and the
            # scene has footage to spare (a tight scene keeps every second instead).
            if len(slots) > 1 and beat.get("words") and available >= need + 1.0:
                picked = _slot_picks(pieces, slots, speed, scene.get("peaks", []), scene.get("moments"), similar, choose)
            else:
                picked = choose(pieces, need, scene.get("peaks", []), moments=scene.get("moments"),
                                text=beat.get("text", ""), similar=similar)
        cursor = start_t
        for s, e in picked:
            length = (e - s) / speed
            shots.append({"clip_id": clip_id, "source": source, "start": round(s, 3), "end": round(e, 3),
                          "speed": round(speed, 3), "timeline_start": round(cursor, 3), "duration": round(length, 3),
                          "audio": "duck", "beat": beat["id"]})
            used.setdefault(clip_id, []).append((s, e))
            cursor += length
        if picked and not beat.get("flash_forward"):  # the flash-forward scene is played again in its place
            scene_cursor[beat["scene"]] = picked[-1][1]
        # Not enough fresh footage between the movie lines: fill with more real footage (rest of this
        # scene, then the story's other scenes) — never by freezing or over-stretching one shot.
        remaining = start_t + gap - cursor
        if remaining > 0.25:
            for extra_clip, extra_source, s, e in _extra_footage(arc, beat["scene"], footage, cuts, used, remaining):
                shots.append({"clip_id": extra_clip, "source": extra_source, "start": round(s, 3), "end": round(e, 3),
                              "speed": 1.0, "timeline_start": round(cursor, 3), "duration": round(e - s, 3),
                              "audio": "duck", "beat": beat["id"]})
                used.setdefault(extra_clip, []).append((s, e))
                cursor += e - s
        # Absorb rounding: the last shot of the beat ends exactly where the next beat starts.
        if shots and shots[-1]["beat"] == beat["id"]:
            last = shots[-1]
            last["duration"] = round(start_t + gap - last["timeline_start"], 3)
            longest = (last["end"] - last["start"]) / MIN_SPEED  # gentle slow motion at most, never a freeze
            if last["duration"] > longest + 0.05:
                last["end"] = round(min(last["start"] + last["duration"] * MIN_SPEED,
                                        last["end"] + (last["duration"] - longest) * MIN_SPEED), 3)
                last["speed"] = round(max(MIN_SPEED, (last["end"] - last["start"]) / last["duration"]), 3)
    total = shots[-1]["timeline_start"] + shots[-1]["duration"] if shots else 0.0
    lengths = [s["duration"] for s in shots]
    missing = total - sum(lengths)
    if missing > 0.5:  # never ship a Short whose picture is shorter than its voice
        raise ValueError(f"Edit for {arc.get('id')} leaves {missing:.1f} s of the {total:.1f} s timeline without footage")
    accents = mark_accents(shots, arc, beats)
    return {"shots": shots, "duration": round(total, 3), "shot_count": len(shots), "accents": accents,
            "median_shot": round(sorted(lengths)[len(lengths) // 2], 2) if lengths else 0.0}


PUNCH_ZOOM = 0.08          # a slow push-in to 108 % over the shot
PUNCH_MIN_SHOT = 1.2       # shorter shots are cuts, not moments
PUNCH_GAP = 6.0            # seconds between two push-ins (more stops meaning anything)
TURN_WORDS = ("reveal", "realis", "realiz", "turn", "twist", "threat", "climax", "return", "discover", "payoff")


def mark_accents(shots: list[dict], arc: dict, beats: list[dict]) -> int:
    """Slow push-in on the shots that carry a story's key moments (at most one per beat, spaced out).

    A shot qualifies when what was watched there is a strong moment (intensity or story ≥ 8), when it
    shows the beat's key moment, or when it ends a turning-point beat. Returns how many were marked.
    """
    scene_of = {b["id"]: b.get("scene") for b in beats}
    scored = []
    for i, shot in enumerate(shots):
        if shot["duration"] < PUNCH_MIN_SHOT:
            continue
        scene_index = scene_of.get(shot.get("beat"))
        scene = arc["scenes"][scene_index] if isinstance(scene_index, int) and scene_index < len(arc["scenes"]) else {}
        if scene.get("clip_id") != shot["clip_id"]:
            continue  # borrowed or filler footage: its moments belong to another scene
        info = scene.get("beat") or {}
        moment = _moment_at(scene.get("moments") or [], (shot["start"] + shot["end"]) / 2) or {}
        score = 0.0
        if max(moment.get("intensity", 0), moment.get("story", 0)) >= 8:
            score += 2
        if info.get("key_moment") and moment.get("what") and word_match(info["key_moment"], moment["what"]) >= 0.34:
            score += 2
        last_of_beat = i + 1 == len(shots) or shots[i + 1].get("beat") != shot.get("beat")
        if last_of_beat and any(w in str(info.get("role", "")).lower() for w in TURN_WORDS):
            score += 1.5
        if score:
            scored.append((score, i))
    marked, beats_done = [], set()
    for score, i in sorted(scored, key=lambda r: (-r[0], r[1])):
        shot = shots[i]
        if shot.get("beat") in beats_done:
            continue
        if any(abs(shots[j]["timeline_start"] - shot["timeline_start"]) < PUNCH_GAP for j in marked):
            continue
        shot["accent"] = "punch"
        marked.append(i)
        beats_done.add(shot.get("beat"))
    return len(marked)

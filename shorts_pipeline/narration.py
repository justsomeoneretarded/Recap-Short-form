"""Turn a written script into a timed voiceover: narrator speech plus real movie lines.

- Narration: consecutive narration beats of a scene are spoken as one take with the punchy
  Chatterbox delivery (existing synthesis, retries, caching and complete-speech check).
- Pacing: each take is measured; slow takes are sped up with pitch-preserving atempo (max
  1.12x) towards ~195 words/minute, and word timings are scaled to match.
- Movie lines: cut from the clip's own audio at the subtitle's clip time (+ small padding).
- Word timing: forced alignment of the exact script text (torchaudio MMS) when available,
  otherwise the existing script-matched Whisper timings.
- Captions: 1–3 big words at a time, also for movie lines.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

TARGET_WPM = 205.0   # low end of the reference recap Shorts (206–231 incl. dialogue)
MAX_TEMPO = 1.15     # atempo (WSOLA) stays clean on speech at this size; most extra pace comes from pauses
MAX_PAUSE = 0.30     # silences longer than this inside a take are shortened ...
KEEP_PAUSE = 0.16    # ... to a natural breath (the voice itself is never stretched or cut)
EDGE_PAUSE = 0.05
DIALOGUE_PAD = 0.15
GAP_SECONDS = 0.12


_ABBREVIATIONS = {"mr.": "Mister", "mrs.": "Missus", "ms.": "Miz", "dr.": "Doctor", "st.": "Saint", "vs.": "versus",
                  "vs": "versus", "lt.": "Lieutenant", "sgt.": "Sergeant", "capt.": "Captain", "det.": "Detective",
                  "jr.": "Junior", "sr.": "Senior", "etc.": "et cetera", "no.": "number"}


def _number_words(value: int) -> str:
    """Numbers as spoken; four-digit years in pairs (1987 → nineteen eighty seven, 2014 → twenty fourteen)."""
    from .voice import _integer_words
    if 1100 <= value <= 1999 or 2010 <= value <= 2099:
        high, low = divmod(value, 100)
        tail = "hundred" if not low else " ".join(_integer_words(low)) if low >= 10 else "oh " + _integer_words(low)[0]
        return " ".join(_integer_words(high)) + " " + tail
    return " ".join(_integer_words(value))


_ORDINAL_WORDS = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
                  "nine": "ninth", "twelve": "twelfth"}


def _ordinal(value: int) -> str:
    from .voice import _integer_words
    words = _integer_words(value)
    last = words[-1]
    last = _ORDINAL_WORDS.get(last) or (last[:-1] + "ieth" if last.endswith("y") else last + "th")
    return " ".join(words[:-1] + [last])


def speakable(text: str) -> str:
    """Script text as it should be spoken: numbers, money, times, symbols and abbreviations in words.

    The narrator voice and the speech check both stumble on "3", "$1,000", "5 a.m.", "Dr." or
    "—"; writing them as spoken words before synthesis removes the most common cause of
    mismatched takes, and captions then show exactly what is said.
    """
    out = text.replace("&", " and ").replace("%", " percent").replace("—", ", ").replace("–", ", ")
    out = re.sub(r"[()\[\]{}\"“”]", " ", out)
    out = re.sub(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s?m\.?(?=\W|$)",
                 lambda m: f"{_number_words(int(m.group(1)))}" +
                 (f" {_number_words(int(m.group(2)))}" if m.group(2) and int(m.group(2)) else "") +
                 f" {m.group(3).upper()} M", out, flags=re.I)
    out = re.sub(r"\$(\d[\d,]*)(\s*(?:million|billion|thousand))?",
                 lambda m: f"{_number_words(int(m.group(1).replace(',', '')))}{m.group(2) or ''} dollars", out)
    out = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: _ordinal(int(m.group(1))), out)
    out = re.sub(r"\b\d[\d,]*\b", lambda m: _number_words(int(m.group(0).replace(",", ""))), out)
    words = []
    for word in out.split():
        words.append(_ABBREVIATIONS.get(word.lower(), word))
    spoken = re.sub(r"\s+([,.!?;:])", r"\1", " ".join(words)).replace(",,", ",").strip(" ,")
    if text.rstrip()[-1:] in ".!?" and spoken[-1:] not in ".!?":
        spoken += text.rstrip()[-1]  # keep the sentence's own ending (e.g. after "a.m.")
    spoken = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), spoken)  # "3 men." → "Three men."
    return spoken


def voice_beats(result: dict) -> list[dict]:
    """Script → ordered voice beats; consecutive narration in a scene becomes one take."""
    script = result["script"]
    beats: list[dict] = []
    hook = speakable((script.get("hook") or "").strip())
    pending: dict | None = {"kind": "narration", "scene": 0, "text": hook, "delivery": "punchy_hook"} if hook else None
    for beat in script.get("beats", []):
        if beat.get("kind") == "dialogue":
            line = result.get("dialogue_lines", {}).get(beat.get("line"))
            if not line:
                continue
            if pending:
                beats.append(pending)
                pending = None
            beats.append({"kind": "dialogue", "scene": line["scene"], "text": line["text"], "line": beat["line"],
                          "clip_start": max(0.0, line["clip_start"] - DIALOGUE_PAD),
                          "clip_end": line["clip_end"] + DIALOGUE_PAD})
            continue
        text = speakable((beat.get("text") or "").strip())
        if not text:
            continue
        if pending and pending["scene"] == beat.get("scene") and pending["delivery"] != "punchy_hook":
            pending["text"] += " " + text
        else:
            if pending:
                beats.append(pending)
            pending = {"kind": "narration", "scene": beat.get("scene", 0), "text": text, "delivery": "punchy"}
    if pending:
        beats.append(pending)
    for i, beat in enumerate(beats):
        beat["id"] = f"b{i:02d}"
    return beats


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def tempo_for(words: int, seconds: float) -> float:
    """Speed-up needed to reach the target pace, never slowing down and never above MAX_TEMPO."""
    if seconds <= 0 or words <= 0:
        return 1.0
    wpm = words * 60 / seconds
    return round(min(MAX_TEMPO, max(1.0, TARGET_WPM / wpm)), 3)


def tighten_pauses(audio: Path, target: Path) -> tuple[Path, list[tuple[float, float]]]:
    """Shorten long silences inside a narration take; never touch the voice.

    Chatterbox leaves 0.3–0.7 s gaps between sentences, which makes fast-cut Shorts drag. Every
    silent stretch longer than MAX_PAUSE (40 dB under the take's peak) is cut down to KEEP_PAUSE,
    with a few milliseconds of fade at each splice so no click is heard; leading and trailing
    silence is trimmed to EDGE_PAUSE. Returns the new file and the removed (start, length) spans,
    so word times can be moved to match.
    """
    try:
        import numpy as np
        import soundfile as sf
        data, rate = sf.read(str(audio), dtype="float32", always_2d=True)
    except Exception:  # noqa: BLE001 - unreadable here: keep the take as it is
        return audio, []
    hop = max(1, rate // 100)  # 10 ms frames
    frames = len(data) // hop
    if frames < 5:
        return audio, []
    level = np.sqrt((data[: frames * hop].reshape(frames, hop, -1) ** 2).mean(axis=(1, 2))) + 1e-9
    loud = 20 * np.log10(level) > 20 * np.log10(level.max()) - 40
    if not loud.any():
        return audio, []
    first, last = int(np.argmax(loud)), int(frames - np.argmax(loud[::-1]))
    cuts: list[tuple[int, int]] = []  # sample ranges to remove
    edge = int(EDGE_PAUSE * rate)
    if first * hop > edge:
        cuts.append((0, first * hop - edge))
    run = None
    for i in range(first, last):
        if not loud[i] and run is None:
            run = i
        elif loud[i] and run is not None:
            length = (i - run) * hop
            if length > MAX_PAUSE * rate:
                keep = int(KEEP_PAUSE * rate)
                cuts.append((run * hop + keep // 2, i * hop - keep // 2))
            run = None
    if (frames - last) * hop > edge:
        cuts.append((last * hop + edge, len(data)))
    if not cuts:
        return audio, []
    fade = max(1, int(0.006 * rate))
    pieces, position = [], 0
    for start, end in cuts:
        piece = data[position:start].copy()
        if len(piece) > 2 * fade:
            if position:  # fade in after a splice
                piece[:fade] *= np.linspace(0, 1, fade)[:, None]
            if start < len(data):  # fade out before a splice
                piece[-fade:] *= np.linspace(1, 0, fade)[:, None]
        pieces.append(piece)
        position = end
    pieces.append(data[position:])
    sf.write(str(target), np.concatenate(pieces), rate, subtype="PCM_16")
    return target, [(start / rate, (end - start) / rate) for start, end in cuts]


def shift_times(seconds: float, removed: list[tuple[float, float]]) -> float:
    """A time in the original take → the same moment after pauses were shortened."""
    shift = 0.0
    for start, length in removed:
        if seconds >= start + length:
            shift += length
        elif seconds > start:
            shift += seconds - start
    return max(0.0, seconds - shift)


def apply_tempo(audio: Path, factor: float, target: Path) -> Path:
    if factor <= 1.001:
        return audio
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-filter:a", f"atempo={factor}", str(target)],
                   check=True)
    return target


_ALIGNER: dict = {}


def _mms():
    """MMS model, tokenizer and aligner, loaded once per process (loading takes seconds; there is one call per beat)."""
    if not _ALIGNER:
        from torchaudio.pipelines import MMS_FA as bundle
        _ALIGNER.update(bundle=bundle, model=bundle.get_model(with_star=False), tokenizer=bundle.get_tokenizer(),
                        aligner=bundle.get_aligner())
    return _ALIGNER["bundle"], _ALIGNER["model"], _ALIGNER["tokenizer"], _ALIGNER["aligner"]


def forced_align(audio: Path, text: str) -> list[dict] | None:
    """Exact-text word timings with torchaudio's MMS forced aligner; None when unavailable."""
    if os.environ.get("SHORTS_FORCED_ALIGN", "1") == "0":
        return None
    try:
        import torch
        import torchaudio
        bundle, model, tokenizer, aligner = _mms()
    except Exception:  # noqa: BLE001 - optional dependency
        return None
    try:
        return _forced_align(audio, text, bundle, model, tokenizer, aligner)
    except Exception:  # noqa: BLE001 - alignment is an improvement, never a reason to fail
        return None


def _forced_align(audio: Path, text: str, bundle, model, tokenizer, aligner) -> list[dict] | None:
    import torch
    import torchaudio
    words = text.split()
    clean = [re.sub(r"[^a-z']", "", w.lower().replace("’", "'")) for w in words]
    keep = [i for i, w in enumerate(clean) if w]
    if not keep:
        return None
    waveform, rate = torchaudio.load(str(audio))
    waveform = torchaudio.functional.resample(waveform.mean(0, keepdim=True), rate, bundle.sample_rate)
    with torch.inference_mode():
        emission, _ = model(waveform)
        spans = aligner(emission[0], tokenizer([clean[i] for i in keep]))
    ratio = waveform.size(1) / emission.size(1) / bundle.sample_rate
    timed = {i: (spans[k][0].start * ratio, spans[k][-1].end * ratio) for k, i in enumerate(keep)}
    rows, last_end = [], 0.0
    for i, word in enumerate(words):
        start, end = timed.get(i, (last_end, last_end + 0.05))
        rows.append({"word": word, "start": round(start, 3), "end": round(max(end, start + 0.03), 3)})
        last_end = rows[-1]["end"]
    return rows


def _number(value, default: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if value == value and abs(value) != float("inf") else default


def tidy_words(words: list[dict], duration: float) -> list[dict]:
    """Word times in order, inside the audio, never overlapping.

    Aligners can return a word that starts a hair before the previous one ends, a token they
    cannot time (a number, a dash) on top of its neighbour, or a last word just past the end of
    the audio. Captions need clean, ordered times, so small slips are fixed here.
    """
    rows, previous = [], 0.0
    for word in words:
        given_start, given_end = _number(word.get("start"), previous), _number(word.get("end"), previous)
        start = round(min(max(given_start, previous), max(0.0, duration - 0.01)), 3)
        end = min(round(max(given_end, start + 0.01), 3), duration)  # cap after rounding
        rows.append({**word, "start": start, "end": end})
        previous = end
    return rows


def synthesize_voiceover(result: dict, footage: dict[str, str], arc: dict, narrator: str, workdir: Path,
                         model: str = "original", synthesize=None) -> dict:
    """Return a timeline of voice beats with audio paths, durations and word timings."""
    from . import voice
    synthesize = synthesize or voice.synthesize_plan
    workdir = Path(workdir)
    folder = workdir / "voiceover" / result["arc"]
    folder.mkdir(parents=True, exist_ok=True)
    beats = voice_beats(result)
    skipped: list[dict] = []
    narration = [dict(b) for b in beats if b["kind"] == "narration"]
    spoken = synthesize({"beats": narration}, narrator, workdir, model)["beats"] if narration else []
    spoken_by_id = {b["id"]: b for b in spoken}
    timeline, cursor = [], 0.0
    for beat in beats:
        if beat["kind"] == "narration":
            take = spoken_by_id[beat["id"]]
            audio, removed = tighten_pauses(Path(take["audio_path"]), folder / f"{beat['id']}-tight.wav")
            factor = tempo_for(len(beat["text"].split()), _duration(audio))
            paced = apply_tempo(audio, factor, folder / f"{beat['id']}-x{factor}.wav")
            duration = _duration(paced)
            words = forced_align(paced, beat["text"])
            provenance = "forced-alignment-mms" if words else take.get("timing_provenance")
            if not words:
                words = [{**w, "start": round(shift_times(w["start"], removed) / factor, 3),
                          "end": round(shift_times(w["end"], removed) / factor, 3)} for w in take["words"]]
            if take.get("warning"):
                skipped.append({"beat": beat["id"], "reason": take["warning"]})
            item = {**beat, "audio_path": str(paced), "duration": duration, "tempo": factor,
                    "pauses_removed": round(sum(length for _, length in removed), 2),
                    "verified": take.get("timing_provenance") != "unverified-take",
                    "words": tidy_words(words, duration),
                    "timing_provenance": provenance,
                    "wpm": round(len(beat["text"].split()) * 60 / max(0.1, duration), 1)}
        else:
            scene = arc["scenes"][beat["scene"]]
            source = footage.get(scene["clip_id"])
            if not source:
                skipped.append({"beat": beat["id"], "reason": "clip footage unavailable"})
                continue  # footage missing: skip the movie line rather than fail the Short
            audio = folder / f"{beat['id']}-line.wav"
            length = beat["clip_end"] - beat["clip_start"]
            cut = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{beat['clip_start']:.3f}", "-i", source,
                                  "-t", f"{length:.3f}", "-vn", "-ac", "2", "-ar", "48000", str(audio)])
            if cut.returncode or not audio.exists() or length <= 0.1:
                skipped.append({"beat": beat["id"], "reason": "movie line could not be cut from the clip"})
                continue  # the narration carries on without this movie line
            words = forced_align(audio, beat["text"])
            if not words:
                parts = beat["text"].split()
                step = max(0.05, (length - 2 * DIALOGUE_PAD) / max(1, len(parts)))
                words = [{"word": w, "start": round(DIALOGUE_PAD + i * step, 3),
                          "end": round(DIALOGUE_PAD + (i + 1) * step, 3)} for i, w in enumerate(parts)]
            line_duration = _duration(audio)
            item = {**beat, "audio_path": str(audio), "duration": line_duration, "words": tidy_words(words, line_duration),
                    "clip_id": scene["clip_id"], "timing_provenance": "forced-alignment-mms" if words else "even"}
        item["timeline_start"] = round(cursor, 3)
        cursor += item["duration"] + GAP_SECONDS
        timeline.append(item)
    total_words = sum(len(b["text"].split()) for b in timeline)
    report = {"arc": result["arc"], "narrator": narrator, "tts_model": model, "beats": timeline,
              "duration": round(cursor - GAP_SECONDS, 3) if timeline else 0.0,
              "words_per_minute": round(total_words * 60 / max(0.1, cursor), 1), "warnings": skipped}
    (folder / "voiceover.json").write_text(json.dumps(report, indent=2))
    return report


def write_short_captions(voiceover: dict, outdir: Path, *, aspect: str = "square") -> dict:
    """Reference-style captions: 1–3 bold words, lower-middle of the frame."""
    from .captions import write_captions
    width, height = (1080, 1080) if aspect == "square" else (1080, 1920)
    plan = {"beats": [{"id": b["id"], "text": b["text"], "words": b["words"], "duration": b["duration"],
                       "timeline_start": b["timeline_start"], "timing_provenance": b.get("timing_provenance")}
                      for b in voiceover["beats"]]}
    return write_captions(plan, outdir, width, height, max_words=3, y=0.62 if aspect == "square" else 0.72,  # 9:16: under faces
                          size_ratio=0.072 if aspect == "square" else 0.068)

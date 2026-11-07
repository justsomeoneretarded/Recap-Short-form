"""Compact, word-timed captions for square and vertical recap videos."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .voice import validate_words


def repair_words(text: str, words: list[dict], duration: float) -> tuple[list[dict], str | None]:
    """Caption-ready word times. Small timing slips are fixed; a word list that does not match
    the text is rebuilt evenly over the audio. Returns (words, repair note or None)."""
    try:
        return validate_words(text, words, duration), None
    except ValueError:
        pass
    expected = text.split()
    have = [w for w in words if str(w.get("word", "")).strip()]
    if len(have) == len(expected):  # right words, messy times: keep order, stay inside the audio
        rows, previous = [], 0.0
        for word, given in zip(expected, have):
            try:
                start, end = float(given["start"]), float(given["end"])
            except (KeyError, TypeError, ValueError):
                start, end = previous, previous
            if not (math.isfinite(start) and math.isfinite(end)):
                start, end = previous, previous
            start = min(max(start, previous), max(0.0, duration - 0.01))
            end = min(max(end, start + 0.01), duration)
            rows.append({"word": word, "start": start, "end": end})
            previous = end
        try:
            return validate_words(text, rows, duration), "word times tidied"
        except ValueError:
            pass
    step = duration / max(1, len(expected))  # last resort: spread the words evenly
    rows = [{"word": w, "start": i * step, "end": (i + 1) * step} for i, w in enumerate(expected)]
    return (validate_words(text, rows, duration) if expected else []), "word times estimated evenly"


def _srt_time(value: float) -> str:
    millis=round(value*1000)
    hours,millis=divmod(millis,3600000)
    minutes,millis=divmod(millis,60000)
    seconds,millis=divmod(millis,1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def _ass_time(value: float) -> str:
    ticks=round(value*100)
    hours,ticks=divmod(ticks,360000)
    minutes,ticks=divmod(ticks,6000)
    seconds,ticks=divmod(ticks,100)
    return f"{hours}:{minutes:02}:{seconds:02}.{ticks:02}"


def _wrap(words: list[str]) -> str:
    if len(words) <= 1 or len(" ".join(words)) <= 27:
        return " ".join(words)
    midpoint=min(range(1,len(words)),key=lambda i:abs(len(" ".join(words[:i]))-len(" ".join(words[i:]))))
    return " ".join(words[:midpoint])+"\n"+" ".join(words[midpoint:])


def _groups(words: list[dict], max_words: int = 7, max_chars: int = 48) -> list[list[dict]]:
    groups=[]
    current=[]
    for word in words:
        length=len(" ".join([w["word"] for w in current]+[word["word"]]))
        gap=float(word["start"])-float(current[-1]["end"]) if current else 0
        if current and (len(current)>=max_words or length>max_chars or gap>.35):
            groups.append(current)
            current=[]
        current.append(word)
        if word["word"].endswith((".","!","?",";")):
            groups.append(current)
            current=[]
    if current:
        groups.append(current)
    return groups


HIGHLIGHT = "&H0033D4FF&"   # warm gold (ASS colours are BGR)
WHITE = "&H00FFFFFF&"
POWER = {"dead", "dies", "died", "death", "kill", "kills", "killed", "killer", "murder", "murdered", "revenge",
         "betrayed", "betrays", "betrayal", "never", "everything", "nothing", "everyone", "nobody", "only", "last",
         "secret", "truth", "lie", "lied", "war", "blood", "gun", "guns", "bomb", "trap", "wrong", "mistake",
         "impossible", "alone", "fear", "terrified", "monster", "legend", "boogeyman", "deadliest", "dangerous",
         "biggest", "millions", "million", "billion", "stole", "stolen", "kidnapped", "missing", "escape",
         "hunt", "hunting", "hunted", "worst", "best", "real", "fake", "twist", "insane"}
SMALL = {"i", "a", "an", "the", "he", "she", "they", "we", "it", "but", "and", "so", "then", "now", "when", "his",
         "her", "their", "this", "that", "there", "what", "who", "one", "in", "on", "at", "of", "to", "for"}


def _plain(word: str) -> str:
    return re.sub(r"[^\w$%']", "", word).strip("'")


def highlight_index(group: list[dict], sentence_starts: set[int], emphasis: set[str] | None = None,
                    offset: int = 0) -> int | None:
    """The one word in a caption worth colouring (a power word, a number, a name), or None.

    `emphasis` (from the script) wins; otherwise: power words > numbers/money > names (a capital
    letter that is not just the start of a sentence). Most cues get no highlight: one gold word
    means something only when it is rare.
    """
    emphasis = {_plain(str(w)).lower() for w in emphasis or ()} - {""}
    best, best_score = None, 0
    for i, row in enumerate(group):
        raw = str(row.get("word", ""))
        word = _plain(raw)
        low = word.lower()
        if not word or low in SMALL:
            continue
        score = 0
        if emphasis and low in emphasis:
            score = 4
        elif low in POWER:
            score = 3
        elif re.search(r"\d", word) or raw.startswith("$"):
            score = 2
        elif word[:1].isupper() and len(word) > 2 and (offset + i) not in sentence_starts:
            score = 1
        if score > best_score:
            best, best_score = i, score
    return best


def _sentence_starts(words: list[dict]) -> set[int]:
    starts, new = set(), True
    for i, row in enumerate(words):
        if new:
            starts.add(i)
        new = str(row.get("word", "")).rstrip("\"')").endswith((".", "!", "?", ":", ";"))
    return starts


def _escape_ass(text: str) -> str:
    return text.upper().replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n",r"\N")


def _static_text(words: list[dict], text: str, highlight: int | None) -> str:
    if highlight is None:
        return _escape_ass(text)
    first_line_words = len(text.split("\n", 1)[0].split()) if "\n" in text else None
    parts = []
    for index, word in enumerate(words):
        if index:
            parts.append(r"\N" if index == first_line_words else " ")
        colour = HIGHLIGHT if index == highlight else WHITE
        parts.append(f"{{\\1c{colour}}}{_escape_ass(word['word'])}")
    return "".join(parts)


def _word_fade_text(words: list[dict], text: str, cue_start: float, cue_end: float, beat_start: float,
                    highlight: int | None = None) -> tuple[str, bool]:
    """Keep the full phrase laid out while revealing its words on their timings.

    This approximates the sampled reference's moving reveal with word alpha,
    rather than claiming to reproduce its unknown character-mask animation.
    Very short cues stay fully visible so the animation cannot hide their text.
    """
    duration=round((cue_end-cue_start)*1000)
    starts=[max(0,round((beat_start+float(word["start"])-cue_start)*1000)) for word in words]
    if duration<300 or duration-starts[-1]<80:
        return _static_text(words,text,highlight),False
    first_line_words=len(text.split("\n",1)[0].split()) if "\n" in text else None
    parts=[]
    for index,(word,entrance) in enumerate(zip(words,starts)):
        available=duration-entrance
        fade=min(120,available//3)
        visible=min(60,available//3)
        # Earlier words leave first, but every word gets time at full opacity.
        exit_start=max(entrance+fade+visible,duration-fade-(len(words)-1-index)*30)
        exit_end=min(duration,exit_start+fade)
        if index:
            parts.append(r"\N" if index==first_line_words else " ")
        colour="" if highlight is None else f"\\1c{HIGHLIGHT if index==highlight else WHITE}"
        parts.append(
            f"{{{colour}\\alpha&HFF&\\t({entrance},{entrance+fade},\\alpha&H00&)"
            f"\\t({exit_start},{exit_end},\\alpha&HFF&)}}{_escape_ass(word['word'])}"
        )
    return "".join(parts),True


def write_captions(plan: dict, outdir: Path, width: int, height: int, *, max_words: int = 7,
                   y: float = .60, size_ratio: float = .0296, font: str = "DejaVu Sans",
                   highlights: bool = True) -> dict:
    """Burned-in ASS and plain SRT captions. Shorts v2 uses 1–3 large words per caption (max_words=3)."""
    if width<=0 or height<=0:
        raise ValueError("Caption canvas dimensions must be positive.")
    style=plan.get("caption_style","reference_word_fade")
    if style not in {"reference_word_fade","static"}:
        raise ValueError("caption_style must be 'reference_word_fade' or 'static'.")
    outdir=Path(outdir)
    outdir.mkdir(parents=True,exist_ok=True)
    cues=[]
    provenance=[]
    previous_end=0.0
    repairs=[]
    highlighted=0
    for beat in plan.get("beats",[]):
        start=float(beat["timeline_start"])
        duration=float(beat["duration"])
        if not all(map(math.isfinite,(start,duration))) or duration<=0:
            repairs.append({"beat_id":beat.get("id"),"repair":"skipped: no usable length"})
            continue
        if start<previous_end-.04:  # overlapping beats: captions follow the earlier one
            start=previous_end
        words,note=repair_words(str(beat.get("text","")),beat.get("words",[]),duration)
        if note:
            repairs.append({"beat_id":beat.get("id"),"repair":note})
        provenance.append({"beat_id":beat.get("id"),"timing":beat.get("timing_provenance","provided-word-timings")})
        starts=_sentence_starts(words)
        emphasis={_plain(str(w)).lower() for w in beat.get("emphasis") or []} or None
        offset=0
        for group in _groups(words, max_words, 18 if max_words <= 3 else 48):
            cue_start=start+group[0]["start"]
            cue_end=min(start+duration,start+group[-1]["end"])
            mark=highlight_index(group,starts,emphasis,offset) if highlights else None
            highlighted+=mark is not None
            cues.append((cue_start,cue_end,_wrap([w["word"] for w in group]),group,start,start+duration,mark))
            offset+=len(group)
        previous_end=start+duration
    srt=outdir/"captions.srt"
    srt.write_text("\n\n".join(f"{i}\n{_srt_time(cue[0])} --> {_srt_time(cue[1])}\n{cue[2]}" for i,cue in enumerate(cues,1))+"\n",encoding="utf-8")
    size=max(12,round(min(width,height)*size_ratio))
    header=f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Recap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H60000000,&H80000000,-1,-1,0,0,100,100,1,0,1,0.6,1.2,5,50,50,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines=[]
    short_static_cues=0
    for index,(start,end,text,words,beat_start,beat_end,mark) in enumerate(cues):
        if style=="reference_word_fade":
            next_start=cues[index+1][0] if index+1<len(cues) else beat_end
            end=min(end+.1,beat_end,next_start)
            clean,animated=_word_fade_text(words,text,start,end,beat_start,mark)
            short_static_cues+=not animated
        else:
            clean=_static_text(words,text,mark)
        position=f"{{\\an5\\pos({width//2},{round(height*y)})}}"
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Recap,,0,0,0,,{position}{clean}")
    ass=outdir/"captions.ass"
    ass.write_text(header+"\n".join(lines)+"\n",encoding="utf-8")
    (outdir/"caption-timing.json").write_text(json.dumps({
        "note":"Whisper timing is an ASR estimate, not phonetic forced alignment. Supplied timings are validated structurally, not acoustically.",
        "caption_style":style,
        "repairs":repairs,
        "highlighted_cues":highlighted,
        "total_cues":len(cues),
        "animation":{
            "implementation":"Custom word-alpha approximation of sampled reference reveal/fade; the original creator's mask algorithm is unknown." if style=="reference_word_fade" else "Static full-phrase captions.",
            "word_timing":"Provided or aligned word starts drive the reveal; full phrase layout remains fixed.",
            "max_fade_ms":120 if style=="reference_word_fade" else 0,
            "max_ass_hold_ms":100 if style=="reference_word_fade" else 0,
            "short_cues_rendered_static":short_static_cues,
            "srt":"Original phrase text and word-boundary intervals, without animation or extra hold."
        },
        "beats":provenance
    },indent=2))
    return {"srt":srt,"ass":ass,"repairs":repairs}

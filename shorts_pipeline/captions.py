"""Compact, word-timed captions for square and vertical recap videos."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .voice import validate_words


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


def _groups(words: list[dict]) -> list[list[dict]]:
    groups=[]
    current=[]
    for word in words:
        length=len(" ".join([w["word"] for w in current]+[word["word"]]))
        gap=float(word["start"])-float(current[-1]["end"]) if current else 0
        if current and (len(current)>=7 or length>48 or gap>.35):
            groups.append(current)
            current=[]
        current.append(word)
        if word["word"].endswith((".","!","?",";")):
            groups.append(current)
            current=[]
    if current:
        groups.append(current)
    return groups


def write_captions(plan: dict, outdir: Path, width: int, height: int) -> dict:
    if width<=0 or height<=0:
        raise ValueError("Caption canvas dimensions must be positive.")
    outdir=Path(outdir)
    outdir.mkdir(parents=True,exist_ok=True)
    cues=[]
    provenance=[]
    previous_end=0.0
    for beat in plan.get("beats",[]):
        start=float(beat["timeline_start"])
        duration=float(beat["duration"])
        if not all(map(math.isfinite,(start,duration))) or start<0 or duration<=0 or start<previous_end-.04:
            raise ValueError("Caption timeline must have positive, ordered beat intervals.")
        words=validate_words(str(beat.get("text","")),beat.get("words",[]),duration)
        provenance.append({"beat_id":beat.get("id"),"timing":beat.get("timing_provenance","provided-word-timings")})
        for group in _groups(words):
            cue_start=start+group[0]["start"]
            cue_end=min(start+duration,start+group[-1]["end"])
            cues.append((cue_start,cue_end,_wrap([w["word"] for w in group])))
        previous_end=start+duration
    srt=outdir/"captions.srt"
    srt.write_text("\n\n".join(f"{i}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}" for i,(start,end,text) in enumerate(cues,1))+"\n",encoding="utf-8")
    size=max(12,round(min(width,height)*.0296))
    header=f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Recap,DejaVu Sans,{size},&H00FFFFFF,&H00FFFFFF,&H60000000,&H80000000,-1,-1,0,0,100,100,1,0,1,0.6,1.2,5,50,50,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines=[]
    for start,end,text in cues:
        clean=text.upper().replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n",r"\N")
        position=f"{{\\an5\\pos({width//2},{round(height*.60)})}}"
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Recap,,0,0,0,,{position}{clean}")
    ass=outdir/"captions.ass"
    ass.write_text(header+"\n".join(lines)+"\n",encoding="utf-8")
    (outdir/"caption-timing.json").write_text(json.dumps({"note":"Whisper timing is an ASR estimate, not phonetic forced alignment. Supplied timings are validated structurally, not acoustically.","beats":provenance},indent=2))
    return {"srt":srt,"ass":ass}

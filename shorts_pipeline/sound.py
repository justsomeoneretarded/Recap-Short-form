"""Music bed and hits: the sound that makes a Short feel produced.

- A music track matched to the story's mood (chosen by Gemini when it writes the script), looped
  to the Short's length, faded in and out, and ducked automatically whenever the narrator or a
  movie line speaks (sidechain compression keyed on the voice mix).
- Subtle whooshes on scene changes, synthesized here (filtered noise), so no licence is needed.

Tracks come from a music library folder: shorts_pipeline/assets/music/<mood>/*.(mp3|wav|m4a|ogg)
(or SHORTS_MUSIC_DIR). Only royalty-free tracks that allow commercial use belong there; each
folder may hold a LICENSES.txt. Without tracks for a mood the Short has no music bed (the review
says so) — the movie's own score is never boosted instead.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

MOODS = ("tense", "action", "dark", "sad", "mysterious", "triumphant")
NEIGHBOURS = {"tense": ("mysterious", "dark", "action"), "action": ("tense", "triumphant"),
              "dark": ("tense", "mysterious", "sad"), "sad": ("dark", "mysterious"),
              "mysterious": ("tense", "dark"), "triumphant": ("action", "tense")}
AUDIO = (".mp3", ".wav", ".m4a", ".ogg", ".flac")
MUSIC_GAIN_DB = -20.0      # under the voice (the ducker takes it down further while anyone speaks)
HIT_GAIN_DB = -14.0


def library() -> Path:
    return Path(os.environ.get("SHORTS_MUSIC_DIR") or Path(__file__).parent / "assets" / "music")


def pick_track(mood: str | None, key: str = "", folder: Path | None = None) -> Path | None:
    """A track for the mood (or the nearest mood that has tracks); the same story always gets the same
    track (stable choice from `key`), different stories spread over the library."""
    folder = folder or library()
    order = [mood] if mood in MOODS else []
    order += [m for m in NEIGHBOURS.get(mood or "", ()) if m not in order] + [m for m in MOODS if m not in order]
    for name in order:
        tracks = sorted(p for p in (folder / name).glob("*") if p.suffix.lower() in AUDIO) if (folder / name).is_dir() else []
        if tracks:
            index = int(hashlib.sha1(key.encode()).hexdigest(), 16) % len(tracks)
            return tracks[index]
    return None


def scene_changes(edl: dict, voiceover: dict, arc: dict | None = None) -> list[float]:
    """Timeline seconds where the story moves to another scene (one whoosh each, never in the first second)."""
    times, last = [], None
    for beat in voiceover.get("beats") or []:
        if last is not None and beat.get("scene") != last and beat.get("timeline_start", 0) > 1.0:
            times.append(round(float(beat["timeline_start"]), 3))
        last = beat.get("scene")
    return times


def _run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-600:]}")


def whoosh(folder: Path) -> Path:
    """A soft rising whoosh (0.6 s of band-passed noise with a swept centre), made once and cached."""
    target = Path(folder) / "whoosh.wav"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=color=pink:duration=0.6:sample_rate=48000",
          "-af", "highpass=f=300,lowpass=f=6000,afade=t=in:d=0.35:curve=exp,afade=t=out:st=0.4:d=0.2,"
                 "aformat=channel_layouts=stereo,volume=0.6", str(target)])
    return target


def mix_filter(duration: float, hits: list[float], *, has_music: bool) -> str:
    """FFmpeg filter: [0:a] = voice + film mix, [1:a] = music (if any), [2..] = one whoosh per hit."""
    chains = ["[0:a]aresample=48000,asplit=2[main][key]"]
    parts = ["[main]"]
    if has_music:
        fade_out = max(0.0, duration - 2.5)
        chains.append(f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={MUSIC_GAIN_DB}dB,"
                      f"afade=t=in:d=1.5,afade=t=out:st={fade_out:.3f}:d=2.5,"
                      f"apad=whole_dur={duration:.3f},atrim=duration={duration:.3f}[bed]")
        # Duck the bed whenever the voice mix is loud (narration or a movie line).
        chains.append("[bed][key]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[ducked]")
        parts.append("[ducked]")
    else:
        chains.append("[key]anullsink")
    first = 2 if has_music else 1
    for n, at in enumerate(hits):
        delay = max(0, round((at - 0.35) * 1000))  # the whoosh peaks on the cut
        chains.append(f"[{first + n}:a]volume={HIT_GAIN_DB}dB,adelay={delay}|{delay}[h{n}]")
        parts.append(f"[h{n}]")
    chains.append("".join(parts) + f"amix=inputs={len(parts)}:duration=first:normalize=0[a]")
    return ";".join(chains)


def add_sound(video: Path, target: Path, *, music: Path | None, hits: list[float], duration: float,
              work: Path) -> dict:
    """Music bed (ducked) and whooshes onto an already mixed video. Returns what was added."""
    if not music and not hits:
        return {"music": None, "hits": 0}
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(video)]
    if music:
        args += ["-stream_loop", "-1", "-i", str(music)]
    sound = whoosh(work) if hits else None
    for _ in hits:
        args += ["-i", str(sound)]
    _run(args + ["-filter_complex", mix_filter(duration, hits, has_music=bool(music)), "-map", "0:v", "-map", "[a]",
                 "-t", f"{duration:.3f}", "-c:v", "copy", "-c:a", "pcm_s16le", str(target)])
    return {"music": music.name if music else None, "hits": len(hits)}

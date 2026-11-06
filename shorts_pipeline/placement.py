"""Place discovered clips inside the movie and find their best moments.

For each top candidate:
1. Captions (manual, then automatic) → match against the movie's subtitles.
2. No usable captions or no match → download the audio only and transcribe it with Whisper.
3. Top comments → timestamps viewers point at; combined with the Most Replayed heatmap.

Clips that cannot be placed keep their audience score and are marked "unplaced"; arcs can
still use them by title and plot order, at lower confidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .discovery import YouTube, comment_peaks
from .locate import MovieTranscript, parse_cues, timed_words, tokens

WHISPER_MODEL = os.environ.get("SHORTS_PLACEMENT_WHISPER_MODEL", "base.en")


def whisper_words(audio: Path, model: str = WHISPER_MODEL, threads: int | None = None) -> list[tuple[float, str]]:
    from .source_speech import _transcribe
    result = _transcribe(audio, model, threads or int(os.environ.get("SHORTS_CPU_THREADS", "4")))
    rows: list[tuple[float, str]] = []
    for segment in result["segments"]:
        for word in segment.get("words") or []:
            for token in tokens(word.get("word") or ""):
                rows.append((float(word.get("start") or segment.get("start") or 0.0), token))
    return rows


def _audio(youtube: YouTube, video_id: str, folder: Path) -> Path | None:
    folder.mkdir(parents=True, exist_ok=True)
    existing = sorted(folder.glob(f"{video_id}.audio.*"))
    if existing:
        return existing[0]
    youtube.extract(f"https://www.youtube.com/watch?v={video_id}", skip_download=False,
                    format="bestaudio[abr<=160]/bestaudio", outtmpl=str(folder / f"{video_id}.audio.%(ext)s"),
                    max_filesize=150 * 1024 * 1024)
    found = sorted(folder.glob(f"{video_id}.audio.*"))
    return found[0] if found else None


def place_clip(candidate: dict, movie: MovieTranscript | None, youtube: YouTube, folder: Path, *,
               use_whisper: bool = True, transcribe=whisper_words) -> dict:
    """Return placement evidence for one candidate (never raises for a single clip)."""
    result: dict = {"method": None, "matched": False}
    if movie is None:
        return {**result, "reason": "no movie subtitles"}
    try:
        captions = youtube.captions(candidate["id"], folder / "captions")
    except RuntimeError as exc:
        captions, result["caption_error"] = None, str(exc)[:160]
    if captions:
        clip = timed_words(parse_cues(captions.read_text(errors="ignore")))
        located = movie.locate(clip)
        result.update(method="captions", caption_file=captions.name, **located)
    if not result["matched"] and use_whisper:
        try:
            audio = _audio(youtube, candidate["id"], folder / "audio")
            if audio:
                located = movie.locate(transcribe(audio))
                result.update(method="whisper", **located)
        except Exception as exc:  # noqa: BLE001 - one failing clip must not stop the run
            result["whisper_error"] = str(exc)[:160]
    if result.get("matched"):
        result["context"] = movie.context(result["movie_start"], result["movie_end"])
    return result


def place_candidates(research: dict, discovered: dict, youtube: YouTube, workdir: Path, *, top: int = 12,
                     comments_for: int = 8, use_whisper: bool = True, transcribe=whisper_words) -> dict:
    subtitles = research.get("subtitles", {}).get("path")
    movie = MovieTranscript.from_subtitles(Path(subtitles).read_text(errors="ignore")) if subtitles else None
    folder = Path(workdir) / "placement" / str(research["movie"]["tmdb_id"])
    cache = folder / "placements.json"
    done = json.loads(cache.read_text()) if cache.exists() else {}
    placed = []
    for rank, candidate in enumerate(discovered["candidates"][:top]):
        row = dict(candidate)
        if candidate["id"] in done:
            row.update(done[candidate["id"]])
        else:
            evidence = {"placement": place_clip(candidate, movie, youtube, folder, use_whisper=use_whisper,
                                                transcribe=transcribe)}
            if rank < comments_for:
                try:
                    evidence["comment_peaks"] = comment_peaks(youtube.comments(candidate["id"]), candidate.get("duration"))
                except RuntimeError as exc:
                    evidence["comment_peaks"], evidence["comment_error"] = [], str(exc)[:160]
            done[candidate["id"]] = evidence
            folder.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(done, indent=1))
            row.update(evidence)
        placed.append(row)
    placed_count = sum(1 for p in placed if p["placement"].get("matched"))
    return {"clips": placed, "placed": placed_count, "considered": len(placed),
            "timeline": sorted(({"id": p["id"], "title": p["title"], "start": p["placement"]["movie_start"],
                                 "end": p["placement"]["movie_end"]} for p in placed if p["placement"].get("matched")),
                               key=lambda x: x["start"])}

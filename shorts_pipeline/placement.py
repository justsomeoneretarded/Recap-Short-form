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


def _media(youtube: YouTube, video_id: str, workdir: Path) -> Path | None:
    """Download the clip once (video ≤1080p); Whisper, screening and the edit all reuse this file."""
    return youtube.download(video_id, Path(workdir) / "footage")


def place_clip(candidate: dict, movie: MovieTranscript | None, youtube: YouTube, folder: Path, *,
               use_whisper: bool = True, transcribe=whisper_words) -> dict:
    """Return placement evidence for one candidate (never raises for a single clip).

    Compilations are split into segments and each segment is placed on its own.
    """
    from .compilations import place_segments, split
    result: dict = {"method": None, "matched": False}
    if movie is None:
        return {**result, "reason": "no movie subtitles"}
    words: list[tuple[float, str]] = []
    captions = None
    # Captions are one more YouTube request; signed-out runners are usually refused, so only
    # try them with cookies (or when forced). Whisper on the downloaded clip gives the same words.
    if getattr(youtube, "signed_in", False) or os.environ.get("SHORTS_TRY_CAPTIONS") == "1":
        try:
            captions = youtube.captions(candidate["id"], folder / "captions")
        except RuntimeError as exc:
            result["caption_error"] = str(exc)[:160]
    else:
        result["caption_error"] = "skipped (no YouTube cookies)"
    if captions:
        words = timed_words(parse_cues(captions.read_text(errors="ignore")))
        result.update(method="captions", caption_file=captions.name, **movie.locate(words))
    needs_audio = not result["matched"] or (candidate.get("compilation") and len(words) < 30)
    if needs_audio and use_whisper:
        try:
            audio = _media(youtube, candidate["id"], folder.parent.parent)
            if audio:
                heard = transcribe(audio)
                located = movie.locate(heard)
                if located.get("matched") or not result["matched"]:
                    words = heard
                    result.update(method="whisper", **located)
        except Exception as exc:  # noqa: BLE001 - one failing clip must not stop the run
            result["whisper_error"] = str(exc)[:160]
    if candidate.get("compilation") and words:
        segments = place_segments(split(candidate, words), words, movie)
        result["segments"] = segments
        result["segments_placed"] = sum(1 for s in segments if s.get("matched"))
        if result["segments_placed"] and not result["matched"]:
            first = next(s for s in segments if s.get("matched"))
            result.update(matched=True, movie_start=first["movie_start"], movie_end=first["movie_end"],
                          confidence=first.get("confidence"))
    if result.get("matched") and not candidate.get("compilation"):
        drift = dialogue_drift(movie, words)
        if drift is not None:
            result["drift_seconds"] = drift
    if result.get("matched"):
        result["context"] = movie.context(result["movie_start"], result["movie_end"])
    return result


def dialogue_drift(movie: MovieTranscript, words: list[tuple[float, str]]) -> float | None:
    """How far the clip's first and second half disagree about where they are in the movie. A sped-up
    or cut-up re-upload drifts; a plain clip does not (≈0). None when either half cannot be placed."""
    if len(words) < 40:
        return None
    half = len(words) // 2
    first, second = movie.locate(words[:half]), movie.locate(words[half:])
    if not (first.get("matched") and second.get("matched")):
        return None
    return round(abs(first["offset_seconds"] - second["offset_seconds"]), 1)


def _prefetch(youtube: YouTube, video_id: str, workdir: Path) -> None:
    try:
        _media(youtube, video_id, workdir)
    except Exception:  # noqa: BLE001 - placement retries and records the error itself
        pass


def place_candidates(research: dict, discovered: dict, youtube: YouTube, workdir: Path, *, top: int = 12,
                     comments_for: int = 3, use_whisper: bool = True, transcribe=whisper_words) -> dict:
    subtitles = research.get("subtitles", {}).get("path")
    movie = MovieTranscript.from_subtitles(Path(subtitles).read_text(errors="ignore")) if subtitles else None
    folder = Path(workdir) / "placement" / str(research["movie"]["tmdb_id"])
    cache = folder / "placements.json"
    done = json.loads(cache.read_text()) if cache.exists() else {}
    placed = []
    import time
    from concurrent.futures import ThreadPoolExecutor
    deadline = time.monotonic() + float(os.environ.get("SHORTS_PLACEMENT_BUDGET", "1500"))
    # Download the next clips in the background while Whisper listens to the current one
    # (network and CPU overlap). Screening and the edit reuse the same files.
    ahead = int(os.environ.get("SHORTS_PREFETCH", "10")) if use_whisper else 0
    pool = ThreadPoolExecutor(max_workers=2) if ahead else None
    pending = {}
    for candidate in discovered["candidates"][:min(top, ahead)]:
        if candidate["id"] not in done:
            pending[candidate["id"]] = pool.submit(_prefetch, youtube, candidate["id"], Path(workdir))
    for rank, candidate in enumerate(discovered["candidates"][:top]):
        if candidate["id"] in pending:
            pending.pop(candidate["id"]).result()  # never download the same file twice at once
        row = dict(candidate)
        if candidate["id"] not in done and time.monotonic() > deadline:
            row["placement"] = {"matched": False, "reason": "time budget reached"}
            placed.append(row)
            continue
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
    if pool:
        pool.shutdown(wait=True)
    placed_count = sum(1 for p in placed if p["placement"].get("matched"))
    return {"clips": placed, "placed": placed_count, "considered": len(placed),
            "timeline": sorted(({"id": p["id"], "title": p["title"], "start": p["placement"]["movie_start"],
                                 "end": p["placement"]["movie_end"]} for p in placed if p["placement"].get("matched")),
                               key=lambda x: x["start"])}

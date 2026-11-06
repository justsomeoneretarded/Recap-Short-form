"""Place a clip inside the full movie by matching its dialogue against the movie's subtitles.

Matching 4-word phrases each vote for an offset (movie time − clip time). A dominant offset
means the clip is that stretch of the movie; the subtitles then supply the dialogue just
before and after it, which gives the writer real context instead of guesses.

Works on SRT/VTT text (movie subtitles, YouTube captions) and on Whisper word timings.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

GRAM = 4
BIN_SECONDS = 2.0
_TIME = re.compile(r"(?:(\d+):)?(\d\d):(\d\d)[,.](\d{3})")
_TAGS = re.compile(r"<[^>]+>|\{[^}]*\}")
_SOUNDS = re.compile(r"\[[^\]]*\]|\([^)]*\)|♪[^♪]*♪?")
_SPEAKER = re.compile(r"^\s*-?\s*[A-Z][A-Z .'-]{1,24}:\s*", re.M)


def _seconds(match: re.Match) -> float:
    h, m, s, ms = match.groups()
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def tokens(text: str) -> list[str]:
    """Lower-case spoken words; drops tags, sound descriptions [GUNSHOT] and speaker labels."""
    text = _SPEAKER.sub(" ", _SOUNDS.sub(" ", _TAGS.sub(" ", text)))
    text = text.lower().replace("’", "'")
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text)


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def parse_cues(text: str) -> list[Cue]:
    """SRT or WebVTT → cues. Works with or without blank lines between cues.

    Very short cues (YouTube's 10 ms hand-over cues) are dropped.
    """
    cues: list[Cue] = []
    lines = text.replace("\r", "").replace("\ufeff", "").split("\n")
    current: tuple[float, float] | None = None
    body: list[str] = []

    def flush() -> None:
        if current and current[1] - current[0] >= 0.05:
            cues.append(Cue(current[0], current[1], "\n".join(body).strip()))

    for i, line in enumerate(lines):
        if "-->" in line:
            times = list(_TIME.finditer(line))
            if len(times) >= 2:
                flush()
                current, body = (_seconds(times[0]), _seconds(times[1])), []
                continue
        is_index = line.strip().isdigit() and i + 1 < len(lines) and "-->" in lines[i + 1]
        if current is not None and line.strip() and not is_index:
            body.append(line.strip())
    flush()
    return cues


def timed_words(cues: list[Cue]) -> list[tuple[float, str]]:
    """Cues → [(time, word)]. Lines repeated from the previous cue (rolling captions) are skipped."""
    rows: list[tuple[float, str]] = []
    previous: set[str] = set()
    for cue in cues:
        lines = [line.strip() for line in cue.text.split("\n") if line.strip()]
        fresh = [line for line in lines if _TAGS.sub("", line).strip() not in previous]
        previous = {_TAGS.sub("", line).strip() for line in lines}
        words = tokens(" ".join(fresh))
        span = max(0.0, cue.end - cue.start)
        rows.extend((cue.start + span * i / max(1, len(words)), w) for i, w in enumerate(words))
    return rows


class MovieTranscript:
    """The movie's subtitles, indexed by 4-word phrase for fast clip placement."""

    def __init__(self, words: list[tuple[float, str]], cues: list[Cue] | None = None):
        self.words = words
        self.cues = cues or []
        self.index: dict[tuple[str, ...], list[float]] = {}
        for i in range(len(words) - GRAM + 1):
            key = tuple(w for _, w in words[i:i + GRAM])
            self.index.setdefault(key, []).append(words[i][0])

    @classmethod
    def from_subtitles(cls, text: str) -> "MovieTranscript":
        cues = parse_cues(text)
        return cls(timed_words(cues), cues)

    def lines_between(self, start: float, end: float) -> list[dict]:
        """Subtitle lines fully inside [start, end] with clean text (sound tags and speaker labels removed)."""
        rows = []
        for cue in self.cues:
            if cue.start >= start and cue.end <= end:
                text = " ".join(_SPEAKER.sub(" ", _SOUNDS.sub(" ", _TAGS.sub(" ", cue.text))).split()).strip(" -")
                if len(tokens(text)) >= 2:
                    rows.append({"start": cue.start, "end": cue.end, "text": text})
        return rows

    def dialogue_between(self, start: float, end: float) -> str:
        return " ".join(w for t, w in self.words if start <= t <= end)

    def locate(self, clip: list[tuple[float, str]], *, minimum_phrases: int = 3) -> dict:
        """Where does this clip's dialogue occur in the movie?

        Returns matched=False when there is too little dialogue or no clear winner (two offsets
        with similar support, e.g. a line repeated in the film).
        """
        votes: Counter = Counter()
        grams = max(0, len(clip) - GRAM + 1)
        for i in range(grams):
            key = tuple(w for _, w in clip[i:i + GRAM])
            positions = self.index.get(key, [])
            if 0 < len(positions) <= 3:  # common phrases ("i don't know what") carry no position
                for movie_time in positions:
                    votes[round((movie_time - clip[i][0]) / BIN_SECONDS)] += 1
        result = {"matched": False, "clip_words": len(clip), "clip_phrases": grams}
        if not votes:
            return {**result, "reason": "no shared phrases" if grams else "too little dialogue"}
        ranked = votes.most_common()
        best_bin, _ = ranked[0]
        support = sum(v for b, v in votes.items() if abs(b - best_bin) <= 2)
        rival = max((v for b, v in votes.items() if abs(b - best_bin) > 2), default=0)
        share = support / max(1, grams)
        offset = best_bin * BIN_SECONDS
        result.update(offset_seconds=offset, matching_phrases=support, share=round(share, 2),
                      rival_phrases=rival)
        if support < minimum_phrases or rival * 2 > support:
            return {**result, "reason": "ambiguous" if rival * 2 > support else "too few matching phrases"}
        start, end = offset + clip[0][0], offset + clip[-1][0]
        return {**result, "matched": True, "movie_start": round(start, 2), "movie_end": round(end, 2),
                "confidence": "high" if share >= 0.4 and support >= 8 else "medium"}

    def context(self, start: float, end: float, pad: float = 45.0) -> dict:
        return {"before": self.dialogue_between(max(0.0, start - pad), start - 0.01)[-400:],
                "after": self.dialogue_between(end + 0.01, end + pad)[:400]}


def locate_captions(movie: MovieTranscript, caption_text: str) -> dict:
    """Convenience: place a clip from its caption file and attach the surrounding dialogue."""
    clip = timed_words(parse_cues(caption_text))
    result = movie.locate(clip)
    if result["matched"]:
        result["context"] = movie.context(result["movie_start"], result["movie_end"])
    return result

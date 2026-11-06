import json
from pathlib import Path

from shorts_pipeline import placement as p
from shorts_pipeline.locate import MovieTranscript

LINES = [f"line {i} the bounty hotel rule number {i} goes live tonight friend {i}" for i in range(300)]


def srt():
    def stamp(s):
        return f"00:{int(s // 60):02d}:{int(s % 60):02d},000"
    return "\n".join(f"{i+1}\n{stamp(i*4)} --> {stamp(i*4+3)}\n{t}\n" for i, t in enumerate(LINES))


def vtt(first, last):
    def stamp(s):
        return f"00:{int(s // 60):02d}:{int(s % 60):02d}.000"
    body = [f"{stamp(k*4)} --> {stamp(k*4+3)}\n{LINES[i]}\n" for k, i in enumerate(range(first, last))]
    return "WEBVTT\n\n" + "\n".join(body)


class FakeYouTube:
    def __init__(self, captions):
        self.captions_text, self.calls = captions, []

    def captions(self, vid, folder):
        self.calls.append(("captions", vid))
        text = self.captions_text.get(vid)
        if text is None:
            return None
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{vid}.en.vtt"
        path.write_text(text)
        return path

    def extract(self, target, **kw):
        vid = target.rsplit("=", 1)[-1]
        self.calls.append(("audio", vid))
        Path(kw["outtmpl"].replace("%(ext)s", "m4a")).write_bytes(b"audio")
        return {}

    def comments(self, vid, count=40):
        return [{"text": "0:42 best part", "like_count": 100}]


def test_captions_place_clip_then_whisper_fallback_then_cache(tmp_path):
    (tmp_path / "movie.srt").write_text(srt())
    research = {"movie": {"tmdb_id": 7}, "subtitles": {"path": str(tmp_path / "movie.srt")}}
    discovered = {"candidates": [{"id": "cap", "title": "with captions", "duration": 120},
                                 {"id": "silent", "title": "no captions", "duration": 120},
                                 {"id": "music", "title": "no dialogue", "duration": 120}]}
    youtube = FakeYouTube({"cap": vtt(100, 120)})
    whisper_calls = []

    def transcribe(audio):
        whisper_calls.append(audio.name)
        if audio.name.startswith("silent"):
            movie = MovieTranscript.from_subtitles(srt())
            return [(t - 200 * 4, w) for t, w in movie.words if 200 * 4 <= t < 215 * 4]
        return []

    result = p.place_candidates(research, discovered, youtube, tmp_path, transcribe=transcribe)
    by_id = {c["id"]: c for c in result["clips"]}
    assert by_id["cap"]["placement"]["method"] == "captions" and abs(by_id["cap"]["placement"]["movie_start"] - 400) < 3
    assert by_id["silent"]["placement"]["method"] == "whisper" and abs(by_id["silent"]["placement"]["movie_start"] - 800) < 3
    assert not by_id["music"]["placement"]["matched"]
    assert by_id["cap"]["comment_peaks"][0]["second"] == 42
    assert [t["id"] for t in result["timeline"]] == ["cap", "silent"] and result["placed"] == 2
    calls = len(youtube.calls)
    again = p.place_candidates(research, discovered, youtube, tmp_path, transcribe=transcribe)
    assert len(youtube.calls) == calls and again["placed"] == 2  # cached


def test_without_subtitles_nothing_is_guessed(tmp_path):
    result = p.place_candidates({"movie": {"tmdb_id": 1}, "subtitles": {}}, {"candidates": [{"id": "a", "title": "x"}]},
                                FakeYouTube({}), tmp_path, comments_for=0)
    assert result["placed"] == 0 and result["clips"][0]["placement"]["reason"] == "no movie subtitles"

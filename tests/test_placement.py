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
    signed_in = True  # captions are only requested with cookies

    def __init__(self, captions):
        self.captions_text, self.calls = captions, []

    def download(self, vid, folder):
        self.calls.append(("video", vid))
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{vid}.mp4"
        path.write_bytes(b"video")
        return path

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
    assert not any(kind == "audio" for kind, _ in youtube.calls)  # one download per clip, no separate audio
    assert [t["id"] for t in result["timeline"]] == ["cap", "silent"] and result["placed"] == 2
    calls = len(youtube.calls)
    again = p.place_candidates(research, discovered, youtube, tmp_path, transcribe=transcribe)
    assert len(youtube.calls) == calls and again["placed"] == 2  # cached


def test_without_subtitles_nothing_is_guessed(tmp_path):
    result = p.place_candidates({"movie": {"tmdb_id": 1}, "subtitles": {}}, {"candidates": [{"id": "a", "title": "x"}]},
                                FakeYouTube({}), tmp_path, comments_for=0)
    assert result["placed"] == 0 and result["clips"][0]["placement"]["reason"] == "no movie subtitles"


def test_compilation_segments_are_placed(tmp_path):
    (tmp_path / "movie.srt").write_text(srt())
    research = {"movie": {"tmdb_id": 8}, "subtitles": {"path": str(tmp_path / "movie.srt")}}
    first, second = vtt(20, 35), vtt(250, 265)
    # Two scenes back to back in one video: shift the second scene by 60 s.
    import re
    shifted = re.sub(r"00:(\d\d):(\d\d)", lambda m: f"00:{int(m.group(1)) + 1:02d}:{m.group(2)}", second.split("\n\n", 1)[1])
    captions = first + "\n" + shifted
    discovered = {"candidates": [{"id": "comp", "title": "all scenes", "duration": 120, "compilation": True,
                                  "signals": {"chapters": [{"start": 0, "title": "A"}, {"start": 60, "title": "B"}]}}]}
    result = p.place_candidates(research, discovered, FakeYouTube({"comp": captions}), tmp_path, comments_for=0,
                                use_whisper=False)
    placement = result["clips"][0]["placement"]
    assert placement["segments_placed"] == 2
    starts = sorted(round(s["movie_start"]) for s in placement["segments"])
    assert abs(starts[0] - 80) < 3 and abs(starts[1] - 1000) < 3


def test_captions_skipped_without_cookies(tmp_path):
    (tmp_path / "movie.srt").write_text(srt())
    youtube = FakeYouTube({"cap": vtt(100, 120)})
    youtube.signed_in = False
    research = {"movie": {"tmdb_id": 9}, "subtitles": {"path": str(tmp_path / "movie.srt")}}
    result = p.place_candidates(research, {"candidates": [{"id": "cap", "title": "x", "duration": 60}]}, youtube,
                                tmp_path, comments_for=0, transcribe=lambda audio: [])
    placement = result["clips"][0]["placement"]
    assert placement["caption_error"].startswith("skipped") and ("captions", "cap") not in youtube.calls


def test_clips_are_downloaded_ahead_once_each(tmp_path):
    (tmp_path / "movie.srt").write_text(srt())
    research = {"movie": {"tmdb_id": 8}, "subtitles": {"path": str(tmp_path / "movie.srt")}}
    discovered = {"candidates": [{"id": f"c{i}", "title": "clip", "duration": 60} for i in range(5)]}
    class Reuse(FakeYouTube):
        signed_in = False

        def download(self, vid, folder):  # like the real client: an existing file is not fetched again
            path = folder / f"{vid}.mp4"
            return path if path.exists() else super().download(vid, folder)

    youtube = Reuse({})
    p.place_candidates(research, discovered, youtube, tmp_path, transcribe=lambda audio: [], comments_for=0)
    videos = [vid for kind, vid in youtube.calls if kind == "video"]
    assert sorted(videos) == [f"c{i}" for i in range(5)]  # prefetched, never twice


def test_dialogue_drift_flags_sped_up_uploads():
    from shorts_pipeline.placement import dialogue_drift
    from shorts_pipeline.locate import MovieTranscript
    lines = [f"{i+1}\n00:{(100+i*3)//60:02d}:{(100+i*3)%60:02d},000 --> 00:{(101+i*3)//60:02d}:{(101+i*3)%60:02d},500\n"
             f"unique words number {i} alpha{i} beta{i} gamma{i}" for i in range(60)]
    movie = MovieTranscript.from_subtitles("\n\n".join(lines))
    plain = [w for w in movie.words]
    assert dialogue_drift(movie, [(t - 100, w) for t, w in plain]) == 0.0
    sped = [((t - 100) / 1.1, w) for t, w in plain]   # 10 % faster: the second half drifts
    assert dialogue_drift(movie, sped) >= 4

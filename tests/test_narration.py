import shutil
import subprocess
from pathlib import Path

import pytest

from shorts_pipeline import narration as n

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

RESULT = {"arc": "arc1",
          "script": {"hook": "A bleeding man sprints through the rain.", "beats": [
              {"scene": 0, "kind": "narration", "text": "He has one hour before every killer comes."},
              {"scene": 0, "kind": "narration", "text": "So he runs to the library."},
              {"scene": 0, "kind": "dialogue", "line": "s0l1"},
              {"scene": 1, "kind": "narration", "text": "A doctor stitches him, but the clock strikes six."}]},
          "dialogue_lines": {"s0l1": {"scene": 0, "text": "I still have time.", "clip_start": 4.0, "clip_end": 5.5}}}
ARC = {"scenes": [{"clip_id": "clipA"}, {"clip_id": "clipB"}]}


def tone(path: Path, seconds: float):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
                    str(path)], check=True)


def fake_synthesize(plan, narrator, workdir, model):
    out = []
    for beat in plan["beats"]:
        words = beat["text"].split()
        seconds = len(words) * 0.4  # 150 wpm: slower than the target
        path = Path(workdir) / f"{beat['id']}.wav"
        tone(path, seconds)
        out.append({**beat, "audio_path": str(path), "duration": seconds, "timing_provenance": "fake",
                    "words": [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate(words)]})
    return {"beats": out}


def test_voice_beats_merge_scene_narration_and_keep_lines():
    beats = n.voice_beats(RESULT)
    assert [b["kind"] for b in beats] == ["narration", "narration", "dialogue", "narration"]
    assert beats[0]["delivery"] == "punchy_hook" and beats[1]["text"].startswith("He has one hour")
    assert "library" in beats[1]["text"] and beats[2]["clip_start"] == pytest.approx(3.85)


def test_tempo_speeds_up_slow_takes_only_and_is_capped():
    assert n.tempo_for(30, 12) == 1.12   # 150 wpm → capped at 1.12
    assert n.tempo_for(30, 9.5) == pytest.approx(1.029, abs=0.01)
    assert n.tempo_for(40, 10) == 1.0    # already 240 wpm: never slowed down


def test_voiceover_timeline_and_captions(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_FORCED_ALIGN", "0")
    clip = tmp_path / "clipA.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", "10", "-shortest", str(clip)], check=True)
    report = n.synthesize_voiceover(RESULT, {"clipA": str(clip)}, ARC, "warguy", tmp_path, synthesize=fake_synthesize)
    beats = report["beats"]
    assert [b["kind"] for b in beats] == ["narration", "narration", "dialogue", "narration"]
    assert beats[0]["tempo"] == 1.12 and beats[0]["duration"] < len(beats[0]["text"].split()) * 0.4
    assert beats[2]["duration"] == pytest.approx(1.8, abs=0.1) and beats[2]["clip_id"] == "clipA"
    starts = [b["timeline_start"] for b in beats]
    assert starts == sorted(starts) and report["words_per_minute"] > 150
    files = n.write_short_captions(report, tmp_path / "captions", aspect="vertical")
    ass = Path(files["ass"]).read_text()
    assert "PlayResY: 1920" in ass and "STILL" in ass
    cue_lines = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    import re
    texts = [re.sub(r"\{[^}]*\}", "", l.split(",,", 1)[1].split(",", 4)[-1]).replace("\\N", " ") for l in cue_lines]
    assert cue_lines and all(1 <= len(t.split()) <= 3 for t in texts), texts


def test_preview_mixes_beats_at_their_positions(tmp_path):
    from shorts_pipeline.cli import _preview
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    tone(a, 1.0)
    tone(b, 1.0)
    target = tmp_path / "preview.wav"
    _preview({"beats": [{"audio_path": str(a), "timeline_start": 0.0}, {"audio_path": str(b), "timeline_start": 2.0}]},
             target)
    assert abs(n._duration(target) - 3.0) < 0.1


def _heard(words, step=0.3):
    return [{"word": w, "start": i * step, "end": i * step + 0.25} for i, w in enumerate(words)]


def test_narrator_check_accepts_small_recognition_slips_but_not_skipped_speech():
    import pytest
    from shorts_pipeline.voice import _align_script
    text = "John Wick limps into the Continental and Winston refuses him shelter so he runs again tonight"
    # A misheard name and a quiet "the" not heard: still the whole script.
    heard = _heard("Jon Wick limps into Continental and Winston refuses him shelter so he runs again tonight".split())
    words = _align_script(text, heard, 6.0, tolerant=True)
    assert [w["word"] for w in words] == text.split()
    assert all(b["start"] >= a["end"] - 0.04 for a, b in zip(words, words[1:]))
    with pytest.raises(ValueError):  # strict mode (imported audio) stays strict
        _align_script(text, heard, 6.0)
    skipped = _heard("John Wick limps into the Continental tonight".split())
    with pytest.raises(ValueError):  # half the script missing is a bad take
        _align_script(text, skipped, 6.0, tolerant=True)

    dropped = _heard("John Wick limps into the Continental and Winston refuses him so he runs again tonight".split())
    with pytest.raises(ValueError):  # a missing content word ("shelter") fails
        _align_script(text, dropped, 6.0, tolerant=True)
    split = _heard("John Wick limps into the Continental and Wins ton refuses him shelter so he runs again tonight".split())
    assert len(_align_script(text, split, 6.0, tolerant=True)) == len(text.split())  # one name heard as two words


def test_word_times_are_tidied_for_captions():
    from shorts_pipeline.narration import tidy_words
    from shorts_pipeline.voice import validate_words
    rough = [{"word": "He", "start": 0.0, "end": 0.3}, {"word": "fires", "start": 0.25, "end": 0.6},
             {"word": "3", "start": 0.6, "end": 0.65}, {"word": "shots", "start": 0.55, "end": 0.9},
             {"word": "now.", "start": 0.9, "end": 1.31}]
    clean = tidy_words(rough, 1.2)
    assert validate_words("He fires 3 shots now.", clean, 1.2) == clean  # ordered, inside the audio

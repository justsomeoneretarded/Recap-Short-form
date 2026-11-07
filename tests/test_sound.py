import json
import shutil
import subprocess

import pytest

from shorts_pipeline import sound


def test_track_follows_the_mood_then_its_neighbours_and_is_stable(tmp_path):
    (tmp_path / "dark").mkdir()
    (tmp_path / "dark" / "a.mp3").write_bytes(b"x")
    (tmp_path / "dark" / "b.mp3").write_bytes(b"x")
    (tmp_path / "action").mkdir()
    (tmp_path / "action" / "c.wav").write_bytes(b"x")
    assert sound.pick_track("action", "k", tmp_path).name == "c.wav"
    first = sound.pick_track("tense", "story-1", tmp_path)        # no tense tracks: nearest mood with tracks
    assert first.parent.name == "dark" and sound.pick_track("tense", "story-1", tmp_path) == first
    assert sound.pick_track("sad", "k", tmp_path / "nothing") is None


def test_whooshes_land_on_scene_changes_only():
    voice = {"beats": [{"scene": 0, "timeline_start": 0.0}, {"scene": 0, "timeline_start": 4.0},
                       {"scene": 1, "timeline_start": 9.5}, {"scene": 2, "timeline_start": 20.0}]}
    assert sound.scene_changes({}, voice) == [9.5, 20.0]


def test_mix_ducks_the_music_under_the_voice():
    graph = sound.mix_filter(30.0, [9.5], has_music=True)
    assert "sidechaincompress" in graph and "[bed][key]" in graph and "amix=inputs=3" in graph


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs FFmpeg")
def test_music_and_whooshes_are_mixed_into_a_real_video(tmp_path):
    video, music = tmp_path / "v.mkv", tmp_path / "m.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=4",
                    "-f", "lavfi", "-i", "sine=f=300:d=4", "-c:v", "libx264", "-c:a", "pcm_s16le", "-shortest",
                    str(video)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=120:d=1.5", str(music)], check=True)
    out = sound.add_sound(video, tmp_path / "o.mkv", music=music, hits=[2.0], duration=4.0, work=tmp_path)
    assert out == {"music": "m.wav", "hits": 1}
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json",
                                       str(tmp_path / "o.mkv")], capture_output=True, text=True).stdout)
    assert abs(float(probe["format"]["duration"]) - 4.0) < 0.2   # music looped to length, never longer

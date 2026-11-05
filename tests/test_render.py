"""Small synthetic media tests. Fixtures contain tones, not generated narration."""
from pathlib import Path
from array import array
import shutil
import subprocess

import pytest

from shorts_pipeline.render import _probe, allocate_shots, crop_filter, render_plan


def test_coverage_never_loops_or_stretches_unreasonably():
    with pytest.raises(ValueError, match="add source shots"):
        allocate_shots([{"start": 0, "end": 1}], 3, 10, 30)
    shots = allocate_shots([{"start": 0, "end": 2}], 2.2, 10, 30)
    assert .85 <= shots[0]["speed"] <= 1
    assert shots[0]["end"] <= 2
    assert sum(s["frames"] for s in shots) == 66


def test_invalid_source_range_and_focus_are_rejected():
    for shot in ({"start": -1, "end": 2}, {"start": 0, "end": 12}, {"start": 0, "end": 2, "focus_x": "nan"}):
        with pytest.raises(ValueError):
            allocate_shots([shot], 1, 10, 30)
    assert "*0.200000" in crop_filter(1080, 1920, .2)
    with pytest.raises(ValueError):
        crop_filter(1079, 1080)


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-threads", "1", "-filter_threads", "1", *map(str,args)], check=True)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
def test_full_render_preserves_dialogue_and_supplied_audio(tmp_path):
    source = tmp_path/"synthetic-source.mp4"
    voice = tmp_path/"synthetic-tone.wav"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=4", "-f", "lavfi", "-i", "sine=frequency=250:sample_rate=48000:duration=4",
            "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", source)
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=700:sample_rate=48000:duration=1.5", voice)
    plan = {"title": "Synthetic integration fixture", "beats": [
        {"id": "n1", "kind": "narration", "text": "Synthetic test tone.", "audio_path": str(voice), "duration": 1.5,
         "timeline_start": 0, "shots": [{"start": 0, "end": 1}, {"start": 1, "end": 2}]},
        {"id": "d1", "kind": "dialogue", "text": "", "duration": 1, "timeline_start": 1.5, "shots": [{"start": 2, "end": 3}]}]}
    out = tmp_path/"output"
    out.mkdir()
    (out/"captions.ass").write_text("""[Script Info]
ScriptType: v4.00+
PlayResX: 180
PlayResY: 320
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,15,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,-1,0,0,100,100,0,0,1,1,1,5,5,5,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,SYNTHETIC TEST
""", encoding="utf-8")
    result = render_plan(plan, source, out, width=180, height=320, fps=30)
    assert result["video"].is_file()
    assert result["qc"]["status"] == "passed"
    assert abs(result["qc"]["duration_seconds"]-2.5) < .18
    assert result["qc"]["width"] == 180
    assert result["qc"]["height"] == 320
    assert len(result["covers"]) == 3
    assert result["contact_sheet"].is_file()
    assert result["provenance"].is_file()
    assert result["qc"]["captions_burned"]
    # Check that supplied narration dominates its section and the original
    # source tone returns during the retained-dialogue section.
    def frequency(at):
        data = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(result["video"]),
                                        "-t", "0.3", "-vn", "-f", "s16le", "-ac", "1", "-ar", "8000", "-"])
        samples = array("h", data)
        crossings = sum(a < 0 <= b for a,b in zip(samples, samples[1:]))
        return crossings/.3
    assert 650 < frequency(.5) < 750
    assert 220 < frequency(1.8) < 280


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
def test_narration_audio_mismatch_fails_before_render(tmp_path):
    source, voice = tmp_path/"source.mp4", tmp_path/"voice.wav"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=160x160:rate=30:duration=1", "-c:v", "libx264", "-threads", "1", source)
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=500:duration=1", voice)
    plan = {"beats": [{"kind": "narration", "audio_path": str(voice), "duration": 4, "shots": [{"start": 0, "end": 1}]}]}
    with pytest.raises(ValueError, match="does not match"):
        render_plan(plan, source, tmp_path/"out", width=160, height=160, fps=30)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
@pytest.mark.parametrize("shot_start", [0, 1])
def test_short_or_absent_source_bed_never_truncates_narration(tmp_path, shot_start):
    source, voice = tmp_path/"sparse-source.mp4", tmp_path/"voice.wav"
    # Four seconds of video, but only half a second of original source sound.
    # The second parameter selects footage entirely after that sound has ended.
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=160x160:rate=30:duration=4",
            "-f", "lavfi", "-i", "sine=frequency=250:sample_rate=48000:duration=0.5",
            "-c:v", "libx264", "-threads", "1", "-c:a", "aac", source)
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=700:sample_rate=48000:duration=2", voice)
    plan = {"beats": [{"id": "n1", "kind": "narration", "audio_path": str(voice), "duration": 2,
                       "shots": [{"start": shot_start, "end": shot_start+2}]}]}
    result = render_plan(plan, source, tmp_path/"out", width=160, height=160, fps=30)
    assert _probe(result["video"])["audio_end"] >= 1.99
    assert result["qc"]["audio_end_seconds"] >= result["qc"]["last_voice_endpoint_seconds"]-.02
    late_audio = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", "1.5", "-i", str(result["video"]),
                                         "-t", "0.3", "-vn", "-f", "s16le", "-ac", "1", "-ar", "8000", "-"])
    samples = array("h", late_audio)
    assert len(samples) >= 2300
    crossings = sum(a < 0 <= b for a,b in zip(samples, samples[1:]))
    assert 650 < crossings/.3 < 750  # The late narration survives, not silence.


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")
def test_retained_dialogue_rejects_missing_source_audio(tmp_path):
    source = tmp_path/"sparse-source.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=160x160:rate=30:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=250:sample_rate=48000:duration=0.5",
            "-c:v", "libx264", "-threads", "1", "-c:a", "aac", source)
    plan = {"beats": [{"kind": "dialogue", "duration": 2, "shots": [{"start": 0, "end": 2}]}]}
    with pytest.raises(ValueError, match="missing source audio"):
        render_plan(plan, source, tmp_path/"out", width=160, height=160, fps=30)

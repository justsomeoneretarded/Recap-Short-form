import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("cv2")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from shorts_pipeline import edit, narration, render_short as rs  # noqa: E402
from tests.test_narration import ARC as N_ARC, RESULT, fake_synthesize  # noqa: E402


def test_render_end_to_end_true_60fps_both_aspects(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_FORCED_ALIGN", "0")
    monkeypatch.setenv("SHORTS_X264_PRESET", "ultrafast")
    monkeypatch.setattr(rs, "SIZES", {"square": (240, 240), "vertical": (180, 320)})
    clips = {}
    for name in ("clipA", "clipB"):
        path = tmp_path / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
                        "-f", "lavfi", "-i", "sine=frequency=330", "-t", "14", "-shortest", "-pix_fmt", "yuv420p",
                        str(path)], check=True)
        clips[name] = str(path)
    arc = {"scenes": [{"clip_id": "clipA", "clip_start": 0.0, "clip_end": 14.0, "peaks": []},
                      {"clip_id": "clipB", "clip_start": 0.0, "clip_end": 14.0, "peaks": []}]}
    voiceover = narration.synthesize_voiceover(RESULT, clips, N_ARC, "warguy", tmp_path, synthesize=fake_synthesize)
    edl = edit.build_edl(arc, voiceover, clips)
    captions = {"square": Path(narration.write_short_captions(voiceover, tmp_path / "cs")["ass"])}
    reports = rs.render_short(edl, voiceover, {}, captions, tmp_path / "out", interpolation="blend")
    for aspect, (w, h) in (("square", (240, 240)), ("vertical", (180, 320))):
        r = reports[aspect]
        assert (r["width"], r["height"]) == (w, h) and r["fps"] == pytest.approx(60, abs=0.1)
        assert abs(r["duration"] - edl["duration"]) < 0.25
        assert r["duplicate_frames"] < 0.2  # blended interpolation, not frame copies
        assert -16.5 < r["integrated_lufs"] < -11.5 and r["true_peak_db"] <= -0.5


def test_rife_only_on_moving_shots_within_budget_and_at_native_size(tmp_path, monkeypatch):
    still, moving = tmp_path / "still.mp4", tmp_path / "moving.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:size=640x360:rate=24",
                    "-f", "lavfi", "-i", "sine", "-t", "4", "-shortest", "-pix_fmt", "yuv420p", str(still)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
                    "-f", "lavfi", "-i", "sine", "-t", "4", "-shortest", "-pix_fmt", "yuv420p", str(moving)], check=True)
    assert rs.motion(still, 0, 2) < rs.CALM_MOTION < rs.motion(moving, 0, 2)
    calls = []

    def fake_rife(frames, audio, target, frames_out, size):
        from PIL import Image
        first = sorted(frames.glob("*.jpg"))
        calls.append(Image.open(first[0]).width)  # frames go to RIFE at native crop size
        assert len(first) >= 30 and audio.exists()
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "24", "-i", str(frames / "%06d.jpg"), "-i", str(audio),
                        "-vf", f"fps=60,scale={size[0]}:{size[1]}", "-c:a", "pcm_s16le", "-shortest", str(target)], check=True)

    monkeypatch.setattr(rs, "rife_available", lambda: True)
    monkeypatch.setattr(rs, "_rife", fake_rife)
    monkeypatch.setattr(rs, "SIZES", {"square": (240, 240), "vertical": (360, 640)})
    shots = [{"clip_id": c, "source": str(p), "start": 0.0, "end": 1.5, "speed": 1.0, "timeline_start": i * 1.5,
              "duration": 1.5, "audio": "duck"} for i, (c, p) in enumerate([("s", still), ("m", moving), ("m", moving)])]
    edl = {"shots": shots}
    plans = rs.plan_shots(edl, {}, ("vertical",))
    rows = rs.render_parts(edl, plans, "vertical", [0, 1], tmp_path / "parts")
    assert [r["why"] for r in rows] == ["calm shot", "rife"]
    if plans["1"]["vertical"]["mode"] == "track":
        assert calls == [202]  # 640x360 source → 202x360 crop interpolated, then enlarged to 360x640
    late = rs.render_parts(edl, plans, "vertical", [2], tmp_path / "parts", budget=-1)
    assert late[0]["why"] == "time budget" and late[0]["interpolation"] == "blend"
    assert rs.probe(tmp_path / "parts" / "vertical-shot-0001.mkv")["width"] == 360

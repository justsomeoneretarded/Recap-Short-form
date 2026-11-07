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

    def fake_rife(frames, audio, target, frames_out, size, real_size=None):
        from PIL import Image
        first = sorted(frames.glob("*.png"))
        calls.append(real_size[0])  # frames go to RIFE at native crop size (padded to a multiple of 32)
        assert Image.open(first[0]).width % 32 == 0
        assert len(first) >= 30 and audio.exists()
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "24", "-i", str(frames / "%06d.png"), "-i", str(audio),
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


def test_corrupted_rife_frames_are_rejected(tmp_path):
    import numpy as np
    from PIL import Image
    src, good, bad = tmp_path / "in", tmp_path / "good", tmp_path / "bad"
    for d in (src, good, bad):
        d.mkdir()
    rng = np.random.default_rng(0)
    base = rng.integers(0, 255, (90, 160, 3), dtype=np.uint8)
    frames = [np.roll(base, i, axis=1) for i in range(6)]  # a slow pan
    for i, f in enumerate(frames):
        Image.fromarray(f).save(src / f"{i + 1:06d}.png")
    for k in range(15):  # 2.5x frames: honest in-betweens are the nearest real frame
        Image.fromarray(frames[min(5, round(k / 2.5))]).save(good / f"{k + 1:08d}.png")
        streak = np.repeat(frames[0][:1], 90, axis=0) if k % 3 else frames[min(5, round(k / 2.5))]
        Image.fromarray(streak).save(bad / f"{k + 1:08d}.png")  # rows smeared like run 15
    assert rs.rife_frames_ok(src, good)[0]
    assert not rs.rife_frames_ok(src, bad)[0]


def test_a_failed_rife_shot_falls_back_to_blending(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24",
                    "-f", "lavfi", "-i", "sine", "-t", "3", "-shortest", "-pix_fmt", "yuv420p", str(clip)], check=True)

    def broken_rife(*args, **kwargs):
        raise RuntimeError("RIFE output rejected: frame 3 does not match its neighbours")

    monkeypatch.setattr(rs, "_rife", broken_rife)
    shot = {"source": str(clip), "start": 0.0, "end": 1.5, "speed": 1.0, "duration": 1.5, "audio": "duck"}
    row = rs.render_shot(shot, {"mode": "track", "x_start": 0.5, "x_end": 0.5}, (0, 0, 1, 1), (180, 320),
                         tmp_path / "shot.mkv", use_rife=True)
    assert row["interpolation"] == "blend" and "rejected" in row["fallback"]


def test_dark_garbage_frames_are_rejected_too():
    import numpy as np
    from PIL import Image
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        src, bad = Path(tmp) / "in", Path(tmp) / "bad"
        src.mkdir(); bad.mkdir()
        rng = np.random.default_rng(1)
        base = (rng.integers(0, 40, (90, 160, 3))).astype(np.uint8)  # a dark scene
        for i in range(4):
            Image.fromarray(np.roll(base, i, axis=1)).save(src / f"{i + 1:06d}.png")
        for k in range(10):  # every output frame smeared into rows, like run 16's Conjuring shot
            Image.fromarray(np.repeat(base[k % 90:k % 90 + 1], 90, axis=0)).save(bad / f"{k + 1:08d}.png")
        assert not rs.rife_frames_ok(src, bad)[0]

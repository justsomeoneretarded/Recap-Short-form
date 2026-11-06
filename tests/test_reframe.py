import shutil
import subprocess

import numpy as np
import pytest

pytest.importorskip("cv2")
from shorts_pipeline import reframe as r  # noqa: E402


def moving_box_frames(x_from, x_to, count=6, w=480, h=270):
    frames = []
    for i in range(count):
        frame = np.full((h, w, 3), 20, dtype=np.uint8)
        x = int(x_from + (x_to - x_from) * i / (count - 1))
        frame[100:170, x:x + 40] = 230 if i % 2 else 200  # bright moving object
        frames.append(frame)
    return frames


def test_window_fraction():
    assert r.window_fraction(16 / 9, 1.0) == pytest.approx(0.5625)
    assert r.window_fraction(16 / 9, 9 / 16) == pytest.approx(0.3164, abs=1e-3)
    assert r.window_fraction(1.0, 1.0) == 1.0


def test_attention_tracks_the_action_side():
    plan = r.plan_shot(moving_box_frames(330, 380), (0, 0, 1, 1), 1.0)
    assert plan["mode"] == "track" and plan["x_start"] > 0.6


def test_pan_follows_motion_but_is_speed_limited():
    plan = r.plan_shot(moving_box_frames(60, 400), (0, 0, 1, 1), 1.0)
    assert plan["mode"] == "track" and plan["x_end"] > plan["x_start"]
    assert plan["x_end"] - plan["x_start"] <= 0.25 + 1e-6


def test_wide_spread_action_falls_back_to_fit_for_vertical():
    frames = []
    for i in range(6):
        frame = np.full((270, 480, 3), 20, dtype=np.uint8)
        frame[:, :60] = 200 if i % 2 else 120
        frame[:, 420:] = 120 if i % 2 else 200
        frames.append(frame)
    assert r.plan_shot(frames, (0, 0, 1, 1), 9 / 16)["mode"] == "fit"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("mode", ["track", "fit"])
def test_filter_graph_renders_requested_size(tmp_path, mode):
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24", "-t", "1",
                    str(src)], check=True)
    plan = {"mode": mode, "x_start": 0.3, "x_end": 0.6}
    graph = r.filter_graph(plan, 640, 360, (0, 0, 1, 1), 540, 960, 1.0)
    out = tmp_path / "out.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter_complex", graph, "-map", "[v]",
                    str(out)], check=True)
    dims = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert dims == "540,960"

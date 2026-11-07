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


def test_wide_spread_action_is_followed_in_both_shapes():
    frames = []
    for i in range(6):
        frame = np.full((270, 480, 3), 20, dtype=np.uint8)
        frame[:, :60] = 200 if i % 2 else 120
        frame[:, 420:] = 120 if i % 2 else 200
        frames.append(frame)
    assert r.plan_shot(frames, (0, 0, 1, 1), 9 / 16)["mode"] == "track"  # no blurred bars in 9:16
    assert r.plan_shot(frames, (0, 0, 1, 1), 1.0)["mode"] == "track"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("mode", ["track", "fit", "stack"])
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


def test_fit_shots_trim_the_edges_when_the_clip_has_a_corner_logo():
    from shorts_pipeline.reframe import filter_graph
    plain = filter_graph({"mode": "fit"}, 1920, 1080, (0, 0, 1, 1), 1080, 1920, 2.0)
    trimmed = filter_graph({"mode": "fit", "trim": 0.08}, 1920, 1080, (0, 0, 1, 1), 1080, 1920, 2.0)
    assert "crop=1612:906" in trimmed and "crop=1612" not in plain


def test_no_shape_uses_blurred_bars(monkeypatch):
    import numpy as np
    from shorts_pipeline import reframe as r
    frames = [np.zeros((270, 480, 3), dtype=np.uint8)] * 4
    # two equal faces far apart → stacked; a clearly bigger face → followed
    monkeypatch.setattr(r, "faces", lambda f: [(0.10, 0.3, 0.22, 0.5), (0.78, 0.3, 0.90, 0.5)])
    plan = r.plan_shot(frames, (0, 0, 1, 1), 1080 / 1920)
    assert plan["mode"] == "stack" and plan["x_top"] < 0.5 < plan["x_bottom"]
    square = r.plan_shot(frames, (0, 0, 1, 1), 1.0)  # square: the two people side by side, no blur
    assert square["mode"] == "stack" and square["layout"] == "columns"
    monkeypatch.setattr(r, "faces", lambda f: [(0.10, 0.2, 0.30, 0.6), (0.80, 0.4, 0.86, 0.5)])
    plan = r.plan_shot(frames, (0, 0, 1, 1), 1080 / 1920)
    assert plan["mode"] == "track" and plan["x_start"] < 0.4


def test_stack_filter_renders_two_tiles(tmp_path):
    import subprocess
    from shorts_pipeline.reframe import filter_graph
    g = filter_graph({"mode": "stack", "x_top": 0.2, "x_bottom": 0.8}, 1920, 1080, (0, 0, 1, 1), 1080, 1920, 1.0)
    out = tmp_path / "stack.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=24", "-t", "1",
                    "-filter_complex", g, "-map", "[v]", "-frames:v", "1", str(out)], check=True)
    from PIL import Image
    assert Image.open(out).size == (1080, 1920)


def test_side_by_side_filter_renders_a_square(tmp_path):
    import subprocess
    from PIL import Image
    from shorts_pipeline.reframe import filter_graph
    g = filter_graph({"mode": "stack", "layout": "columns", "x_top": 0.2, "x_bottom": 0.8}, 1920, 1080, (0, 0, 1, 1),
                     1080, 1080, 1.0)
    out = tmp_path / "side.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=24", "-t", "1",
                    "-filter_complex", g, "-map", "[v]", "-frames:v", "1", str(out)], check=True)
    assert Image.open(out).size == (1080, 1080)



def test_one_big_face_is_never_stacked_twice(monkeypatch):
    import numpy as np
    from shorts_pipeline import reframe as r
    frames = [np.zeros((360, 640, 3), np.uint8) for _ in range(6)]
    # A close-up wider than the 9:16 window, a stray second detection in one frame only.
    boxes = [[(150, 40, 490, 330)]] * 5 + [[(150, 40, 490, 330), (20, 100, 60, 140)]]
    calls = iter(boxes)
    monkeypatch.setattr(r, "faces", lambda frame: next(calls))
    plan = r.plan_shot(frames, (0.0, 0.0, 1.0, 1.0), 1080 / 1920)
    assert plan["mode"] == "track"


def test_punch_in_only_when_asked():
    assert r.punch_in({}, 1080, 1920, 2.0) == ""
    assert "eval=frame" in r.punch_in({"punch": 0.08}, 1080, 1920, 2.0)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
@pytest.mark.parametrize("mode", ["track", "fit"])
def test_punch_in_and_deflicker_keep_the_frame_size(tmp_path, mode):
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24", "-t", "1",
                    str(src)], check=True)
    graph = r.filter_graph({"mode": mode, "punch": 0.08, "deflicker": True}, 640, 360, (0, 0, 1, 1), 540, 960, 1.0)
    out = tmp_path / "out.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter_complex", graph, "-map", "[v]",
                    str(out)], check=True)
    dims = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert dims == "540,960"

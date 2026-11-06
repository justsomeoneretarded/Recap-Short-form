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

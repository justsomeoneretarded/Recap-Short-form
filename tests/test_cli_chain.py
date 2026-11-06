"""voice → render → package exactly as the workflow chains them (models faked, media real)."""
import json
import shutil
import subprocess

import pytest

pytest.importorskip("cv2")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

from shorts_pipeline import cli, render_short, voice  # noqa: E402
from tests.test_narration import RESULT, fake_synthesize  # noqa: E402


def test_voice_render_package_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_FORCED_ALIGN", "0")
    monkeypatch.setenv("SHORTS_X264_PRESET", "ultrafast")
    monkeypatch.setattr(voice, "synthesize_plan", fake_synthesize)
    monkeypatch.setattr(render_short, "SIZES", {"square": (240, 240), "vertical": (180, 320)})
    discover, scripts = tmp_path / "discover", tmp_path / "write"
    discover.mkdir()
    scripts.mkdir()
    clips = {}
    for name in ("clipA", "clipB"):
        path = tmp_path / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
                        "-f", "lavfi", "-i", "sine=frequency=330", "-t", "14", "-shortest", "-pix_fmt", "yuv420p",
                        str(path)], check=True)
        clips[name] = str(path)
    arc = {"id": "arc1", "movie_start": 0, "movie_end": 30, "scenes": [
        {"clip_id": "clipA", "clip_title": "A", "clip_start": 0.0, "clip_end": 14.0, "movie_start": 0, "movie_end": 14, "peaks": []},
        {"clip_id": "clipB", "clip_title": "B", "clip_start": 0.0, "clip_end": 14.0, "movie_start": 16, "movie_end": 30, "peaks": []}]}
    (discover / "arcs.json").write_text(json.dumps({"arcs": [arc]}))
    (discover / "screening.json").write_text(json.dumps([{"id": k, "accept": True, "path": v} for k, v in clips.items()]))
    (discover / "research.json").write_text(json.dumps({"movie": {"title": "Nobody", "year": 2021, "genres": ["Action"],
                                                                  "cast": [], "keywords": []}}))
    (scripts / "scripts.json").write_text(json.dumps([{**RESULT, "check": {"issues": []},
                                                       "script": {**RESULT["script"], "title": "He Was a Nobody. Now They Know."},
                                                       "drafts": []}]))
    cli.run_voice(discover, scripts, tmp_path / "voice", tmp_path / "work")
    rendered = cli.run_render(discover, tmp_path / "voice", tmp_path / "render", tmp_path / "work", interpolation="blend")
    assert rendered["rendered"][0]["outputs"]["square"]["fps"] == pytest.approx(60, abs=0.1)
    packaged = cli.run_package(discover, scripts, tmp_path / "voice", tmp_path / "render", tmp_path / "shorts", length=30)
    folder = tmp_path / "shorts" / "arc1"
    for name in ("final-square.mp4", "final-vertical.mp4", "cover-vertical-hook.jpg", "description.txt",
                 "title-options.txt", "tags.txt", "review.html", "contact-sheet.jpg", "captions-square.srt"):
        assert (folder / name).exists(), name
    assert packaged["packages"][0]["title"] == "He Was a Nobody. Now They Know."

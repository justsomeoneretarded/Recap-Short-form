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


def test_parallel_chunks_match_single_machine(tmp_path, monkeypatch):
    """edit-plan → render-part ×(2 aspects × 3 chunks) → finish → package, as the parallel workflow runs it."""
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
    (discover / "research.json").write_text(json.dumps({"movie": {"title": "Nobody", "year": 2021, "genres": [],
                                                                  "cast": [], "keywords": []}}))
    (scripts / "scripts.json").write_text(json.dumps([{**RESULT, "check": {"issues": []}, "drafts": [],
                                                       "script": {**RESULT["script"], "title": "A. B."}}]))
    cli.run_voice(discover, scripts, tmp_path / "voice", tmp_path / "work")
    cli.run_edit_plan(discover, tmp_path / "voice", tmp_path / "edit", tmp_path / "work")
    # Render machines have no screening paths: they "download" footage (faked by copying).
    from shorts_pipeline import discovery

    def fake_download(self, clip_id, folder):
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{clip_id}.mp4"
        shutil.copyfile(clips[clip_id], target)
        return target

    monkeypatch.setattr(discovery.YouTube, "download", fake_download)
    total = 0
    for aspect in ("square", "vertical"):
        for chunk in range(3):
            total += cli.run_render_part(tmp_path / "edit", "arc1", aspect, chunk, 3, tmp_path / "parts",
                                         tmp_path / "work2")["shots"]
    edit = json.loads((tmp_path / "edit" / "arc1" / "edit.json").read_text())
    assert total == 2 * len(edit["edl"]["shots"])  # chunks cover every shot exactly once
    done = cli.run_finish(tmp_path / "edit", tmp_path / "voice", tmp_path / "parts", "arc1", tmp_path / "render")
    assert set(done["outputs"]) == {"square", "vertical"}
    assert done["outputs"]["vertical"]["fps"] == pytest.approx(60, abs=0.1)
    cli.run_package(discover, scripts, tmp_path / "voice", tmp_path / "render", tmp_path / "shorts", length=30,
                    parts=tmp_path / "parts")
    assert (tmp_path / "shorts" / "arc1" / "final-vertical.mp4").exists()
    from PIL import Image
    assert Image.open(tmp_path / "shorts" / "arc1" / "cover-square-clean.jpg").size == (1080, 1080)


def test_footage_shipped_to_this_machine_is_used_without_youtube(tmp_path, monkeypatch):
    from shorts_pipeline import cli, discovery

    def no_youtube(*_a, **_k):
        raise AssertionError("YouTube must not be contacted")

    monkeypatch.setattr(discovery, "YouTube", no_youtube)
    (tmp_path / "footage").mkdir()
    (tmp_path / "footage" / "abc123.mp4").write_bytes(b"x")
    assert cli._footage(["abc123"], {}, tmp_path) == {"abc123": str(tmp_path / "footage" / "abc123.mp4")}


def test_rejected_story_is_replaced_by_a_spare(tmp_path, monkeypatch):
    import json as _json
    from shorts_pipeline import cli, writer, gemini
    source = tmp_path / "discover"
    source.mkdir()
    (source / "research.json").write_text(_json.dumps({"movie": {"title": "M", "year": 2000}}))
    arcs = [{"id": f"arc{i + 1}", "movie_start": 0, "movie_end": 60, "scenes": []} for i in range(4)]
    (source / "arcs.json").write_text(_json.dumps({"arcs": arcs}))
    monkeypatch.setattr(gemini, "client", lambda: None)
    tried = []

    def fake_write(arc, *a, **k):
        tried.append(arc["id"])
        bad = arc["id"] == "arc1"
        return {"arc": arc["id"], "script": {"title": "T", "hook": "h", "beats": []}, "rejected": bad,
                "rejected_because": ["names not in the brief"] if bad else [],
                "check": {"issues": [], "total_words": 1, "target_words": 1, "score": 1}, "dialogue_lines": {}}
    monkeypatch.setattr(writer, "write_short", fake_write)
    out = cli.run_write(source, tmp_path / "write", arc_index=0, spare_every=2)
    assert tried == ["arc1", "arc3"] and [s["arc"] for s in out["scripts"]] == ["arc3"]


def test_picture_edit_repicks_weak_clauses_once(monkeypatch, tmp_path):
    from shorts_pipeline import cli
    from shorts_pipeline import gemini as gem
    text = "He opens the trunk, finds the guns. He drives away."
    words = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(text.split())]
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0, "timeline_start": 0.0, "duration": 6.0,
                        "text": text, "words": words}]}
    arc = {"id": "a", "scenes": [{"clip_id": "A", "clip_start": 0.0, "clip_end": 60.0, "peaks": []}]}
    calls = []
    monkeypatch.setattr(gem, "client", lambda: object())
    monkeypatch.setattr(gem, "frame_sheets", lambda *a, **k: [{"scene": 0, "times": [1.0], "image": None}])

    def pick(google, arc_, voice_, slots, sheets, only=None, avoid=None):
        calls.append("repick" if avoid else "scene")
        ids = sorted(only)
        base = 30.0 if avoid else 5.0
        return {sid: {"start": base + 4 * n, "end": base + 4 * n + (slots["b0"][int(sid[-1])]["end"] - slots["b0"][int(sid[-1])]["start"]),
                      "match": 9 if avoid else 7, "shown": True} for n, sid in enumerate(ids)}
    monkeypatch.setattr(gem, "pick_frames", pick)
    monkeypatch.setattr(gem, "check_cuts", lambda *a, **k: {"b0#0": {"match": 3, "problem": "no trunk"},
                                                           "b0#1": {"match": 8, "problem": ""}})
    director, report, fixed = cli._picture_edit(arc, voice, {"A": "a.mp4"}, {}, None, tmp_path / "a")
    assert calls == ["scene", "repick"] and fixed == ["b0"]       # one request per scene, then one re-pick
    assert director["b0"][0][0] == 30.0                         # the weak clause got its better stretch
    assert {r["clause"]: r["match"] for r in report}["b0#0"] == 9


def test_one_scene_failing_keeps_the_picture_edit_of_the_others(monkeypatch, tmp_path):
    from shorts_pipeline import cli
    from shorts_pipeline import gemini as gem
    voice = {"beats": [{"id": "b0", "scene": 0}, {"id": "b1", "scene": 1}]}
    slots = {"b0": [{"start": 0, "end": 3, "text": "a"}], "b1": [{"start": 0, "end": 3, "text": "b"}]}
    tried = []

    def pick(google, arc_, voice_, slots_, sheets, only=None, avoid=None):
        tried.append(sorted(only))
        if "b0#0" in only:
            raise gem.GeminiUnavailable("network: read timed out")
        return {"b1#0": {"start": 1.0, "end": 4.0, "match": 8, "shown": True}}
    monkeypatch.setattr(gem, "pick_frames", pick)
    monkeypatch.setattr(gem, "frame_sheets", lambda *a, **k: [{"scene": k.get("only"), "times": [], "image": None}])
    picks = cli._scene_picks(object(), {}, voice, slots, [{"scene": 0}, {"scene": 1}], {}, tmp_path)
    assert tried == [["b0#0"], ["b0#0"], ["b1#0"]]                 # scene 0 retried smaller, then given up
    assert list(picks) == ["b1#0"]

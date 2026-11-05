import json
import base64
import io
import math
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from shorts_pipeline import planner, sources


def test_segments_cover_full_source_without_gaps():
    spans = sources._segments([1.0, 1.0, -1, 20, 8.5], 13.1)
    assert spans[0][0] == 0
    assert spans[-1][1] == 13.1
    assert all(a < b and b-a <= 6.000001 for a, b in spans)
    assert all(left[1] == right[0] for left, right in zip(spans, spans[1:]))


@pytest.mark.parametrize("duration,maximum", [(0, 6), (math.inf, 6), (10, math.nan), (10, 0)])
def test_bad_segment_limits_rejected(duration, maximum):
    with pytest.raises(ValueError):
        sources._segments([], duration, maximum)


@pytest.mark.parametrize("value", ["http://example.com/a.mp4", "https://user:password@example.com/a.mp4", "ftp://example.com/a.mp4"])
def test_remote_sources_require_https_without_embedded_credentials(tmp_path, value):
    with pytest.raises(ValueError, match="HTTPS"):
        sources.resolve_source(value, tmp_path)


def test_local_source_provenance_includes_content_hash(tmp_path, monkeypatch):
    video = tmp_path / "movie.mp4"
    video.write_bytes(b"source-video-bytes")
    monkeypatch.setattr(sources, "_video_info", lambda p: {"duration": 10, "width": 320, "height": 180, "has_audio": True})
    assert sources.resolve_source(str(video), tmp_path / "work") == video.resolve()
    provenance = json.loads((tmp_path / "work/sources/source.json").read_text())
    assert provenance["sha256"] == sources.file_digest(video)
    assert provenance["bytes"] == len(b"source-video-bytes")


def test_failed_download_is_not_cached(tmp_path, monkeypatch):
    import requests

    def fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", fail)
    with pytest.raises(RuntimeError, match="Could not download"):
        sources.resolve_source("https://example.com/movie.mp4", tmp_path)
    assert not list((tmp_path / "sources").glob("source-*.mp4"))
    assert not list((tmp_path / "sources").glob("source-*.json"))


def test_index_fallback_explains_method_and_preserves_every_time_span(tmp_path, monkeypatch):
    video = tmp_path / "movie.mp4"
    video.write_bytes(b"movie")
    monkeypatch.setattr(sources, "_video_info", lambda p: {"duration": 14, "width": 320, "height": 180, "has_audio": True})
    def unavailable(*args):
        raise ImportError("optional package absent")
    monkeypatch.setattr(sources, "_adaptive_boundaries", unavailable)
    monkeypatch.setattr(sources, "_ffmpeg_boundaries", lambda p, d: [2, 10])
    def run(args, **kwargs):
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(args, 0, json.dumps({"streams": [{"avg_frame_rate": "30/1"}]}), "")
        Path(args[-1]).write_bytes(b"jpeg")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(sources, "_run", run)
    scenes = sources.index_source(video, tmp_path / "work")
    assert scenes[0]["start"] == 0
    assert scenes[-1]["end"] == 14
    assert all(a["end"] == b["start"] for a, b in zip(scenes, scenes[1:]))
    saved = json.loads((tmp_path / "work/source-index.json").read_text())
    assert "approximate" in saved["method"]
    assert saved["fallback_reason"] == "ImportError"


def test_ffmpeg_detector_debounces_adjacent_frame_triggers(monkeypatch):
    stderr = "pts_time:0.1\npts_time:1.0\npts_time:1.0167\npts_time:1.35\npts_time:3.0"
    monkeypatch.setattr(sources, "_run", lambda *a, **k: subprocess.CompletedProcess([], 0, "", stderr))
    assert sources._ffmpeg_boundaries(Path("video"), 5) == [1.0, 1.35, 3.0]


def _plan(shots=None, kind="narration"):
    return {"title": "A threat", "beats": [{"id": "B1", "kind": kind, "text": "He closes the door.", "shots": shots or [{"start": 1, "end": 3}]}]}


@pytest.mark.parametrize("shot", [{"start": -1, "end": 2}, {"start": 1, "end": 11},
    {"start": 2, "end": 2}, {"start": 1, "end": float("nan")},
    {"start": 1, "end": 2, "focus_x": 1.5}])
def test_storyboard_rejects_invalid_source_ranges(shot):
    with pytest.raises(ValueError):
        planner.validate_storyboard(_plan([shot]), 10)


def test_dialogue_requires_one_contiguous_source_span():
    with pytest.raises(ValueError, match="exactly one"):
        planner.validate_storyboard(_plan([{"start": 0, "end": 1}, {"start": 2, "end": 3}], "dialogue"), 10)
    validated = planner.validate_storyboard(_plan(kind="dialogue"), 10)
    assert validated["beats"][0]["duration"] == 2


def test_duplicate_beat_ids_rejected():
    value = _plan()
    value["beats"] *= 2
    with pytest.raises(ValueError, match="Duplicate"):
        planner.validate_storyboard(value, 10)


def test_unknown_scene_id_is_never_substituted():
    raw = {"beats": [{"text": "A threat approaches.", "scene_ids": ["S9999"]}]}
    with pytest.raises(ValueError, match="unknown scene"):
        planner._normalize_model_plan(raw, [{"id": "S0001", "start": 0, "end": 5}], Path("source"), {"target_seconds": 15}, 5)


def test_reverse_chronology_within_a_beat_is_rejected():
    scenes = [{"id": "S1", "start": 0, "end": 10}, {"id": "S2", "start": 10, "end": 20}]
    raw = {"beats": [{"text": "He approaches.", "scene_ids": ["S2", "S1"]}]}
    with pytest.raises(ValueError, match="reverses source chronology"):
        planner._normalize_model_plan(raw, scenes, Path("source"), {"target_seconds": 15}, 20)


def test_missing_models_has_actionable_error(monkeypatch):
    monkeypatch.setattr(planner, "_request_json", lambda *a, **k: {"models": [{"name": "other:latest"}]})
    with pytest.raises(RuntimeError, match="ollama pull qwen3-vl:2b-instruct-q4_K_M"):
        planner._require_models("http://127.0.0.1:11434", ["qwen3-vl:2b-instruct-q4_K_M"])


def test_scene_limit_fails_before_any_model_calls(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("No model calls expected when scene limit exceeded")
    monkeypatch.setattr(planner, "_request_json", fail)
    with pytest.raises(ValueError, match="No scenes have been silently skipped"):
        planner.make_plan({"max_scenes": 1}, Path("unused"), [{"id": "S1"}, {"id": "S2"}], tmp_path)


def test_plan_cache_binds_source_and_models_and_preserves_review_status(tmp_path, monkeypatch):
    source = tmp_path / "movie.mp4"
    source.write_bytes(b"source")
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (900, 600), "blue").save(frame)
    scenes = [{"id": "S0001", "start": 0, "end": 20, "frame_path": str(frame), "sample_time": 10}]
    request = {"title": "A door", "brief": "Escalate a threat", "target_seconds": 15, "script_model": "gemma4:12b"}
    text = "He quietly closes the heavy door as footsteps approach outside. He checks the lock and waits. Another shadow crosses the window while the handle begins to turn."
    calls = []
    def api(url, payload=None, **kwargs):
        calls.append((url, payload))
        if url.endswith("/api/tags"):
            return {"models": [{"name": "qwen3-vl:2b-instruct-q4_K_M"}, {"name": "gemma4:12b"}]}
        if payload.get("images"):
            return {"response": "A man beside a door; no other action is established."}
        if "prompt" not in payload:
            return {}
        return {"response": json.dumps({"title": "A door", "description": "An approaching threat.", "beats": [
            {"id": "B1", "text": text, "scene_ids": ["S0001"], "delivery": "dramatic"}]})}
    monkeypatch.setattr(planner, "_request_json", api)
    monkeypatch.setattr(planner, "_video_info", lambda p: {"duration": 20})
    first = planner.make_plan(request, source, scenes, tmp_path / "work")
    assert first["beats"][0]["shots"] == [{"start": 0.0, "end": 20.0, "focus_x": .5}]
    assert "requires editorial review" in first["planning"]["grounding"]
    assert "one midpoint" in first["planning"]["coverage"]
    call_count = len(calls)
    second = planner.make_plan(request, source, scenes, tmp_path / "work")
    assert second == first
    assert len(calls) == call_count


@pytest.mark.parametrize("first_text", ["", "A partial description"])
def test_vision_empty_length_response_retries_without_using_thinking(tmp_path, monkeypatch, first_text):
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (900, 600), "blue").save(frame)
    scene = {"id": "S1", "frame_path": str(frame), "sample_time": 2}
    cache = tmp_path / "planning"
    responses = iter([
        {"response": first_text, "thinking": "Not a visual description.", "done_reason": "length",
         "prompt_eval_count": 500, "eval_count": 256},
        {"response": "A man stands beside a closed door.", "done_reason": "stop",
         "prompt_eval_count": 500, "eval_count": 12},
    ])
    budgets = []
    def generate(url, payload, **kwargs):
        budgets.append(payload["options"]["num_predict"])
        with Image.open(io.BytesIO(base64.b64decode(payload["images"][0]))) as sent:
            assert sent.size == (384, 256)
        return next(responses)
    monkeypatch.setattr(planner, "_request_json", generate)
    description = planner._describe(scene, planner.DEFAULT_VISION_MODEL, "http://localhost:11434", cache)
    assert description == "A man stands beside a closed door."
    assert budgets == [256, 512]
    saved = list(cache.glob("description-*.json"))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text())["description"] == description
    assert json.loads(saved[0].read_text())["image_preprocessing"]["input_size"] == [384, 256]
    with Image.open(frame) as retained:
        assert retained.size == (900, 600)
    diagnostics = sorted((cache / "diagnostics").glob("*.json"))
    assert len(diagnostics) == 2
    assert json.loads(diagnostics[0].read_text())["done_reason"] == "length"
    assert json.loads(diagnostics[0].read_text())["_request_image"]["input_size"] == [384, 256]


@pytest.mark.parametrize("response", ["", None, "A partial description that exhausts its budget"])
def test_vision_two_failed_responses_leave_no_description_cache(tmp_path, monkeypatch, response):
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (320, 180), "blue").save(frame)
    scene = {"id": "S1", "frame_path": str(frame)}
    cache = tmp_path / "planning"
    calls = []
    def generate(url, payload, **kwargs):
        calls.append(payload)
        return {"response": response, "thinking": "Do not use this.", "done_reason": "length",
                "prompt_eval_count": 500, "eval_count": payload["options"]["num_predict"]}
    monkeypatch.setattr(planner, "_request_json", generate)
    with pytest.raises(RuntimeError) as error:
        planner._describe(scene, planner.DEFAULT_VISION_MODEL, "http://localhost:11434", cache)
    message = str(error.value)
    for expected in ["after two attempts", "done_reason='length'", "prompt_eval_count=500",
                     "eval_count=512", "response_keys=", planner.DEFAULT_VISION_MODEL]:
        assert expected in message
    assert len(calls) == 2
    assert not list(cache.glob("description-*.json"))
    assert len(list((cache / "diagnostics").glob("*.json"))) == 2

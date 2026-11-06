import pytest

from shorts_pipeline import edit as e

ARC = {"scenes": [{"clip_id": "A", "clip_start": 0.0, "clip_end": 60.0, "peaks": [40.0]},
                  {"clip_id": "B", "clip_start": 10.0, "clip_end": 20.0, "peaks": []}]}
VOICE = {"beats": [
    {"id": "b0", "kind": "narration", "scene": 0, "timeline_start": 0.0, "duration": 5.9},
    {"id": "b1", "kind": "narration", "scene": 0, "timeline_start": 6.0, "duration": 9.9},
    {"id": "b2", "kind": "dialogue", "scene": 0, "timeline_start": 16.0, "duration": 2.0, "clip_start": 30.0},
    {"id": "b3", "kind": "narration", "scene": 1, "timeline_start": 18.1, "duration": 12.0}]}
FOOTAGE = {"A": "a.mp4", "B": "b.mp4"}


def test_choose_prefers_peaks_keeps_order_and_hits_length():
    pieces = e._pieces(0, 30, [5, 9, 14, 21, 26])
    picked = e.choose(pieces, 8.0, [22.0])
    assert picked == sorted(picked)
    assert sum(b - a for a, b in picked) == pytest.approx(8.0, abs=0.05)
    assert any(a <= 22 <= b for a, b in picked)


def test_edl_is_continuous_dialogue_in_sync_and_forward_moving():
    edl = e.build_edl(ARC, VOICE, FOOTAGE, cuts={"A": [3, 7, 12, 18, 24, 41, 47, 55]})
    shots = edl["shots"]
    for prev, nxt in zip(shots, shots[1:]):
        assert nxt["timeline_start"] == pytest.approx(prev["timeline_start"] + prev["duration"], abs=0.02)
    line = next(s for s in shots if s["beat"] == "b2")
    assert line["audio"] == "full" and line["start"] == 30.0 and line["speed"] == 1.0
    scene_a = [s for s in shots if s["clip_id"] == "A" and s["audio"] == "duck"]
    assert all(s["end"] <= 30.0 + 1e-6 for s in scene_a)  # narration before the line uses footage before it
    assert edl["duration"] == pytest.approx(30.1, abs=0.05)


def test_short_footage_is_slowed_gently_not_frozen():
    edl = e.build_edl(ARC, VOICE, FOOTAGE)
    scene_b = [s for s in edl["shots"] if s["clip_id"] == "B"]
    assert all(s["speed"] >= e.MIN_SPEED for s in scene_b)
    assert sum(s["duration"] for s in scene_b) == pytest.approx(12.0, abs=0.05)

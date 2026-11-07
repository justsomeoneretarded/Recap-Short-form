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


def test_long_narration_before_an_early_movie_line_uses_more_footage_not_a_freeze():
    # The Conjuring case: 31 s of narration, but the first movie line starts 1.7 s into the clip.
    arc = {"scenes": [{"clip_id": "A", "clip_start": 0.0, "clip_end": 120.0, "peaks": []}]}
    voice = {"beats": [
        {"id": "b0", "kind": "narration", "scene": 0, "timeline_start": 0.0, "duration": 31.0},
        {"id": "b1", "kind": "dialogue", "scene": 0, "timeline_start": 31.1, "duration": 4.0, "clip_start": 1.73},
        {"id": "b2", "kind": "narration", "scene": 0, "timeline_start": 35.2, "duration": 20.0}]}
    edl = e.build_edl(arc, voice, {"A": "a.mp4"}, cuts={"A": [5, 9, 14, 20, 26, 33, 41, 50, 58, 66, 75, 90]})
    shots = edl["shots"]
    assert edl["duration"] == pytest.approx(55.2, abs=0.05)
    for shot in shots:  # every shot is real motion: never a frame held for seconds
        assert shot["speed"] >= e.MIN_SPEED - 1e-6
        assert shot["duration"] <= (shot["end"] - shot["start"]) / e.MIN_SPEED + 0.06
    for prev, nxt in zip(shots, shots[1:]):
        assert nxt["timeline_start"] == pytest.approx(prev["timeline_start"] + prev["duration"], abs=0.02)


def test_text_cards_in_the_footage_are_never_used():
    arc = {"scenes": [{"clip_id": "A", "clip_start": 0.0, "clip_end": 60.0, "peaks": [], "avoid": [[20.0, 32.0]]}]}
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0, "timeline_start": 0.0, "duration": 40.0}]}
    edl = e.build_edl(arc, voice, {"A": "a.mp4"}, cuts={"A": [5, 10, 15, 25, 35, 45, 50]})
    assert all(s["end"] <= 20.0 + 1e-6 or s["start"] >= 32.0 - 1e-6 for s in edl["shots"])
    assert edl["duration"] == pytest.approx(40.0, abs=0.05)


def test_narration_gets_footage_even_when_the_whole_clip_is_marked_to_avoid():
    from shorts_pipeline.edit import build_edl
    arc = {"id": "a", "scenes": [{"clip_id": "c", "clip_start": 0.0, "clip_end": 60.0, "peaks": [],
                                  "avoid": [[0.0, 61.0]]}]}
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0, "timeline_start": 0.0, "duration": 20.0,
                        "text": "x"}]}
    edl = build_edl(arc, voice, {"c": "/c.mp4"}, {})
    assert abs(sum(s["duration"] for s in edl["shots"]) - 20.0) < 0.1


def test_director_moments_play_in_its_order_under_their_sentence():
    from shorts_pipeline.edit import build_edl
    arc = {"id": "a", "scenes": [{"clip_id": "c", "clip_start": 0.0, "clip_end": 60.0, "peaks": [], "avoid": []}]}
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0, "timeline_start": 0.0, "duration": 4.0,
                        "text": "He smashes the floor."}]}
    edl = build_edl(arc, voice, {"c": "/c.mp4"}, {}, director={"b0": [(40.0, 42.0), (10.0, 12.0)]})
    assert [(s["start"], s["end"]) for s in edl["shots"]] == [(40.0, 42.0), (10.0, 12.0)]


def test_key_moments_get_one_spaced_push_in():
    from shorts_pipeline.edit import build_edl
    scene = {"clip_id": "c", "clip_start": 0.0, "clip_end": 60.0, "peaks": [], "avoid": [],
             "beat": {"role": "the reveal", "key_moment": "Viggo laughs on the phone"},
             "moments": [{"start": 10.0, "end": 13.0, "what": "Viggo laughs on the phone", "intensity": 5, "story": 9},
                         {"start": 20.0, "end": 23.0, "what": "a car drives", "intensity": 3, "story": 3}]}
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0, "timeline_start": 0.0, "duration": 3.0},
                       {"id": "b1", "kind": "narration", "scene": 0, "timeline_start": 3.0, "duration": 3.0}]}
    edl = build_edl({"id": "a", "scenes": [scene]}, voice, {"c": "/c.mp4"}, {},
                    director={"b0": [(10.0, 13.0)], "b1": [(20.0, 23.0)]})
    punched = [s for s in edl["shots"] if s.get("accent") == "punch"]
    assert [s["start"] for s in punched] == [10.0]   # the strong moment; the second is too close in time anyway
    assert edl["accents"] == 1

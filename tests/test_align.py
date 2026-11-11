"""Script fitted to the footage before voicing (fakes for Gemini and FFmpeg)."""
from shorts_pipeline import align as al
from shorts_pipeline import gemini as gem


class Google:
    def __init__(self, reply):
        self.reply, self.parts = reply, None

    def generate(self, role, parts, **kw):
        self.parts = parts
        return self.reply


def _fake_frames(monkeypatch):
    monkeypatch.setattr(gem, "_frames", lambda video, lo, hi, step, folder: [(lo + 0.5, "f.jpg")])
    monkeypatch.setattr(gem, "_sheet", lambda frames, label: object())
    monkeypatch.setattr(gem, "_image_part", lambda image: {"inlineData": {}})


def story():
    arc = {"story": {"title": "T"}, "scenes": [
        {"clip_id": "A", "clip_start": 300.0, "clip_end": 310.0, "movie_start": 4500.0, "movie_end": 4510.0,
         "beat": {"what_we_see": "Robert slides a phone across the kitchen counter to Dave",
                  "narration": "Robert slides the phone to Dave."}}]}
    result = {"arc": "arc1", "brief": {}, "dialogue_lines": {}, "script": {"hook": "h", "beats": [
        {"scene": 0, "kind": "narration",
         "text": "Robert sits in Dave's kitchen. He slides the phone across the counter. Dave smiles at him."}]}}
    return arc, result


def test_a_misplaced_scene_moves_to_the_right_seconds_and_unshown_sentences_follow_the_picture(monkeypatch, tmp_path):
    _fake_frames(monkeypatch)
    arc, result = story()
    google = Google({"scenes": [{"scene": 0, "shows_scene": True, "start": 340.0, "end": 352.0, "sentences": [
        {"n": 0, "shown": True},
        {"n": 1, "shown": True},
        {"n": 2, "shown": False, "rewrite": "Dave stares at the phone and says nothing."}]}]})
    new_arc, new_result, notes = al.align_story(google, arc, result, {"A": "a.mp4"}, tmp_path,
                                                probe=lambda p: {"duration": 600.0})
    scene = new_arc["scenes"][0]
    assert scene["clip_start"] == 340.0 and scene["clip_end"] >= 352.0           # moved to where the moment is
    assert scene["movie_start"] == 4540.0                                         # movie time moves with it
    assert new_result["script"]["beats"][0]["text"].endswith("Dave stares at the phone and says nothing.")
    assert arc["scenes"][0]["clip_start"] == 300.0                                # the input is not changed
    assert any("rewritten" in n for n in notes)


def test_a_rewrite_that_invents_a_name_is_refused(monkeypatch, tmp_path):
    _fake_frames(monkeypatch)
    arc, result = story()
    google = Google({"scenes": [{"scene": 0, "shows_scene": True, "start": 300.0, "end": 312.0, "sentences": [
        {"n": 2, "shown": False, "rewrite": "Agent Kowalski watches from the hallway."}]}]})
    _, new_result, notes = al.align_story(google, arc, result, {"A": "a.mp4"}, tmp_path,
                                          probe=lambda p: {"duration": 600.0})
    assert new_result["script"]["beats"][0]["text"].endswith("Dave smiles at him.")
    assert any("kept" in n for n in notes)


def test_without_gemini_nothing_changes(tmp_path):
    arc, result = story()
    assert al.align_story(None, arc, result, {"A": "a.mp4"}, tmp_path) == (arc, result, [])


def test_short_clips_are_shown_whole_long_ones_around_the_scene():
    scene = {"clip_start": 400.0, "clip_end": 420.0}
    assert al.window(scene, 240.0) == (0.0, 240.0)
    assert al.window(scene, 1800.0) == (340.0, 480.0)

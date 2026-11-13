"""Footage-first writing: watched events, line-by-line script, peak-aligned edit (fakes, no network)."""
import pytest

from shorts_pipeline import edit as e
from shorts_pipeline import footage_script as fs
from shorts_pipeline import narration as n
from shorts_pipeline import watch as w


def test_events_come_back_in_clip_seconds_and_in_order():
    raw = {"events": [
        {"start": 40, "end": 44, "peak": 50, "what": "Susan falls", "who": "Susan", "on_screen": "hotel", "importance": 9},
        {"start": 10, "end": 18, "peak": 12, "what": "two men grab Susan", "who": "Susan, killers", "on_screen": "room",
         "importance": 10},
        {"start": 5, "end": 5.2, "peak": 5, "what": "blink", "who": "", "on_screen": "", "importance": 1}]}
    events = w.clean_events(raw, 300.0, 360.0)
    assert [x["start"] for x in events] == [310.0, 340.0]                    # +window start, sorted, tiny one dropped
    assert events[1]["peak"] == 344.0                                         # peak kept inside its event


def test_the_watched_window_surrounds_the_scene_and_stays_small():
    assert w.window({"clip_start": 100.0, "clip_end": 130.0}, 600.0) == (70.0, 160.0)
    lo, hi = w.window({"clip_start": 100.0, "clip_end": 400.0}, 1800.0)
    assert hi - lo == w.MAX_WINDOW


def arc_with_events():
    return {"story": {"title": "T", "spine": "Robert avenges Susan"}, "scenes": [
        {"clip_id": "A", "clip_start": 300.0, "clip_end": 340.0, "watch_window": [270.0, 370.0],
         "beat": {"role": "inciting crime", "what_we_see": "Susan is attacked", "narration": "Susan is attacked."},
         "events": [{"start": 300.0, "end": 306.0, "peak": 303.0, "what": "two men stab Susan", "who": "Susan",
                     "on_screen": "hotel room", "importance": 10},
                    {"start": 306.0, "end": 312.0, "peak": 310.0, "what": "Susan collapses and dies", "who": "Susan",
                     "on_screen": "floor", "importance": 9},
                    {"start": 312.0, "end": 316.0, "peak": 314.0, "what": "a man paints a wall", "who": "Miles",
                     "on_screen": "wall", "importance": 2}]},
        {"clip_id": "B", "clip_start": 10.0, "clip_end": 40.0, "beat": {"role": "turn", "what_we_see": "the phone rings"},
         "events": [{"start": 12.0, "end": 20.0, "peak": 16.0, "what": "Dave's phone rings on the counter",
                     "who": "Robert, Dave", "on_screen": "kitchen", "importance": 9}]}]}


def raw_script(**over):
    lines = [{"scene": 0, "kind": "narration", "event": "s0e0", "text": "Two killers trap Susan and stab her.",
              "key_word": "stab"},
             {"scene": 0, "kind": "narration", "event": "s0e1", "text": "She collapses on the floor and dies.",
              "key_word": "collapses"},
             {"scene": 0, "kind": "narration", "event": "s0e2", "text": "Miles paints a colourful wall.",
              "key_word": "paints"},
             {"scene": 1, "kind": "narration", "event": "s1e0", "text": "Then Dave's phone rings on the counter.",
              "key_word": "rings"},
             {"scene": 0, "kind": "narration", "event": "s9e9", "text": "Something nobody filmed.", "key_word": "x"}]
    return {"title": "The Traitor", "hook": {"text": "His best friend's phone rings.", "event": "s1e0", "key_word": "rings"},
            "lines": lines, **over}


def test_every_kept_line_is_tied_to_a_real_event_and_trivial_ones_are_dropped():
    events, _ = fs.event_table(arc_with_events())
    merged, notes = fs.validate(raw_script(), events, {}, {"susan", "dave", "miles", "two", "then", "she", "his"})
    texts = [x["text"] for x in merged["lines"]]
    assert texts == ["Two killers trap Susan and stab her.", "She collapses on the floor and dies.",
                     "Then Dave's phone rings on the counter."]
    assert any("trivial" in x for x in notes) and any("no matching event" in x for x in notes)
    assert merged["hook"]["event"] == "s1e0"


def test_a_line_longer_than_its_footage_is_shortened_before_voicing():
    events, _ = fs.event_table(arc_with_events())
    long = raw_script(lines=[{"scene": 0, "kind": "narration", "event": "s0e0", "key_word": "stab",
                              "text": "Two killers trap Susan, " + " ".join(["and they stab her again"] * 12) + "."}] +
                      raw_script()["lines"][1:2] + raw_script()["lines"][3:4])
    merged, notes = fs.validate(long, events, {}, {"susan", "dave", "two", "then", "she"})
    assert len(merged["lines"][0]["text"].split()) <= fs.max_words(events["s0e0"]) + 1
    assert any("shortened" in x for x in notes)


def test_the_script_keeps_each_lines_event_through_to_the_voice_beats():
    events, _ = fs.event_table(arc_with_events())
    merged, _ = fs.validate(raw_script(), events, {}, {"susan", "dave", "two", "then", "she", "his"})
    script = fs.to_script(merged, events, {"ending": "reveal"})
    assert script["hook_scene"] == 1 and script["beats"][0]["lines"][1]["event"]["what"].startswith("Susan collapses")
    beats = n.voice_beats({"script": script})
    assert beats[0]["flash_forward"] and beats[0]["lines"][0]["key_word"] == "rings"
    assert [x["key_word"] for x in beats[1]["lines"]] == ["stab", "collapses"]


def words_for(text, start=0.0, step=0.4):
    return [{"word": x, "start": round(start + i * step, 3), "end": round(start + i * step + 0.3, 3)}
            for i, x in enumerate(text.split())]


def test_the_event_peak_plays_exactly_when_the_key_word_is_spoken():
    arc = arc_with_events()
    events, _ = fs.event_table(arc)
    lines = [{"text": "Two killers trap Susan and stab her.", "key_word": "stab", "event": events["s0e0"]},
             {"text": "She collapses on the floor and dies.", "key_word": "collapses", "event": events["s0e1"]}]
    text = " ".join(x["text"] for x in lines)
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0, "timeline_start": 0.0, "duration": 6.0,
                        "text": text, "words": words_for(text), "lines": lines}]}
    shots = e.build_edl(arc, voice, {"A": "a.mp4", "B": "b.mp4"})["shots"]
    stab = next(s for s in shots if s.get("event") == "s0e0")
    key_time = 5 * 0.4                                                         # "stab" is the 6th word
    assert stab["start"] + (key_time - stab["timeline_start"]) * stab["speed"] == pytest.approx(303.0, abs=0.05)
    dies = next(s for s in shots if s.get("event") == "s0e1")
    assert dies["start"] + (8 * 0.4 - dies["timeline_start"]) * dies["speed"] == pytest.approx(310.0, abs=0.05)
    assert shots[-1]["timeline_start"] + shots[-1]["duration"] == pytest.approx(6.0, abs=0.01)


def test_a_long_line_takes_more_of_the_same_scene_before_anything_else():
    arc = arc_with_events()
    events, _ = fs.event_table(arc)
    text = " ".join(["word"] * 40)                                              # 16 s of speech over a 8 s event
    lines = [{"text": text, "key_word": "word", "event": events["s1e0"]}]
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 1, "timeline_start": 0.0, "duration": 16.0,
                        "text": text, "words": words_for(text), "lines": lines}]}
    shots = e.build_edl(arc, voice, {"A": "a.mp4", "B": "b.mp4"})["shots"]
    assert {s["clip_id"] for s in shots} == {"B"} and shots[0]["end"] - shots[0]["start"] > 8


class FakeGemini:
    def __init__(self, replies):
        self.replies, self.prompts, self.uploaded = list(replies), [], []

    def generate(self, role, parts, **kw):
        self.prompts.append(parts[-1]["text"])
        return self.replies.pop(0)

    def upload(self, path):
        self.uploaded.append(str(path))
        return {"uri": "files/x", "name": "files/x"}

    def delete(self, record):
        pass


def test_write_then_the_editor_check_fixes_the_script():
    checked = raw_script(lines=raw_script()["lines"][:2] + raw_script()["lines"][3:4], problems=["removed the wall line"])
    google = FakeGemini([raw_script(), checked])
    result = {"script": {"title": "old", "ending": "reveal"}, "brief": {"movie": "The Equalizer 2 (2018)"}}
    script, notes = fs.write(google, arc_with_events(), result, {"title": "The Equalizer 2", "year": 2018}, seconds=60,
                             log=lambda m: None)
    assert script["footage_first"] and len(google.prompts) == 2
    assert "EVENTS" in google.prompts[1] and any(x.startswith("editor:") for x in notes)
    assert all(line["event"]["id"] for b in script["beats"] for line in b["lines"])


def test_watching_cuts_each_scene_and_keeps_the_events(monkeypatch, tmp_path):
    monkeypatch.setattr(w, "cut_segment", lambda video, lo, hi, target: target)
    google = FakeGemini([{"events": [{"start": 30, "end": 36, "peak": 33, "what": "two men stab Susan", "who": "Susan",
                                      "on_screen": "hotel", "importance": 10}],
                          "burned_in_captions": False, "narrator_over_film": False}])
    arc = {"scenes": [{"clip_id": "A", "clip_start": 300.0, "clip_end": 340.0, "beat": {"what_we_see": "the attack"}}]}
    seen = w.watch_story(google, arc, {"A": "a.mp4"}, tmp_path, {"title": "T", "year": 2018},
                         probe=lambda p: {"duration": 900.0}, log=lambda m: None)
    scene = seen["scenes"][0]
    assert scene["watch_window"] == [270.0, 370.0] and scene["events"][0]["peak"] == 303.0
    assert "the attack" in google.prompts[0] and "events" not in arc["scenes"][0]

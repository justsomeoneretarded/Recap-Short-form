"""Small, messy problems are repaired and reported; they never stop a Short."""
import random

from shorts_pipeline.captions import repair_words, write_captions
from shorts_pipeline.narration import tidy_words
from shorts_pipeline.voice import validate_words

TEXTS = ["He fires 3 shots — then 2 more.", "Mr. O'Neil's 1,000-dollar deal goes wrong!", "Run.",
         "Dr. Lorraine Warren hears it: knock, knock, knock.", "Kate Macer (FBI) crosses into Juárez at 5 a.m."]


def _messy(text, duration, rng):
    words, t = [], 0.0
    for word in text.split():
        start = t + rng.uniform(-0.2, 0.2)
        end = start + rng.uniform(-0.05, 0.5)
        if rng.random() < 0.1:
            start, end = float("nan"), end
        words.append({"word": word, "start": start, "end": end})
        t += duration / len(text.split())
    if rng.random() < 0.3:
        words.pop(rng.randrange(len(words)))  # a word the aligner lost
    return words


def test_any_messy_word_timing_becomes_valid_captions(tmp_path):
    rng = random.Random(7)
    for trial in range(300):
        text = rng.choice(TEXTS)
        duration = rng.uniform(0.4, 6.0)
        words, _ = repair_words(text, _messy(text, duration, rng), duration)
        assert validate_words(text, words, duration) == words


def test_tidy_keeps_words_inside_the_audio():
    rng = random.Random(3)
    for _ in range(300):
        duration = rng.uniform(0.2, 5)
        rough = [{"word": f"w{i}", "start": rng.choice([rng.uniform(-1, duration + 1), float("nan"), None]),
                  "end": rng.uniform(-1, duration + 1)} for i in range(rng.randint(1, 12))]
        clean = tidy_words(rough, duration)
        assert all(0 <= w["start"] < w["end"] <= duration + 1e-9 for w in clean)
        assert all(b["start"] >= a["end"] - 0.011 for a, b in zip(clean, clean[1:]))  # captions allow 0.04
        validate_words(" ".join(w["word"] for w in clean), clean, duration)


def test_captions_survive_bad_beats_and_report_repairs(tmp_path):
    plan = {"beats": [
        {"id": "b0", "text": "He fires 3 shots.", "timeline_start": 0.0, "duration": 1.5,
         "words": [{"word": "He", "start": 0, "end": 0.3}, {"word": "fires", "start": 0.2, "end": 0.6},
                   {"word": "3", "start": 0.6, "end": 0.6}, {"word": "shots.", "start": 0.5, "end": 1.9}]},
        {"id": "b1", "text": "Nothing lines up here", "timeline_start": 1.45, "duration": 1.0, "words": []},
        {"id": "b2", "text": "Broken", "timeline_start": 2.5, "duration": 0.0, "words": []}]}
    out = write_captions(plan, tmp_path, 1080, 1920, max_words=3)
    assert out["srt"].read_text().count("-->") >= 3
    assert {r["beat_id"] for r in out["repairs"]} == {"b0", "b1", "b2"}

from shorts_pipeline import compilations as c
from shorts_pipeline.locate import MovieTranscript

LINES = [f"scene {i} unique words alpha{i} beta{i} gamma{i} delta{i}" for i in range(400)]


def movie():
    def stamp(s):
        return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d},000"
    return MovieTranscript.from_subtitles("\n".join(f"{i+1}\n{stamp(i*4)} --> {stamp(i*4+3)}\n{t}\n"
                                                    for i, t in enumerate(LINES)))


def test_description_chapters_need_ordered_stamps_from_the_start():
    text = "Best scenes!\n0:00 Bus fight\n2:15 - Kitchen\n4:40 | Finale\nFollow us"
    assert [r["start"] for r in c.description_chapters(text)] == [0, 135, 280]
    assert c.description_chapters("watch at 3:20 and 1:00 lol\n5:00 x") == []


def test_compilation_segments_are_placed_separately_and_strangers_dropped():
    m = movie()
    # 0–60 s: movie lines 10–24; 60–120 s: another film (unknown words); 120–180 s: movie lines 300–314
    words = []
    for k, i in enumerate(range(10, 25)):
        words += [(k * 4 + j * 0.3, w) for j, w in enumerate(LINES[i].split())]
    words += [(60 + k * 2, f"stranger{k}") for k in range(25)]
    for k, i in enumerate(range(300, 315)):
        words += [(120 + k * 4 + j * 0.3, w) for j, w in enumerate(LINES[i].split())]
    candidate = {"duration": 180, "signals": {"chapters": [{"start": 0, "title": "A"}, {"start": 60, "title": "B"},
                                                            {"start": 120, "title": "C"}]}}
    placed = c.place_segments(c.split(candidate, words), words, m)
    assert [p["matched"] for p in placed] == [True, False, True]
    assert abs(placed[0]["movie_start"] - 40) < 3 and abs(placed[2]["movie_start"] - 1200) < 3


def test_dialogue_gap_fallback_merges_short_pieces():
    words = [(t, "w") for t in [1, 2, 3, 30, 31, 32, 33, 70, 71]]
    segments = c.segments_from_dialogue_gaps(words, 90)
    assert [s["source"] for s in segments] == ["dialogue gaps"] * len(segments)
    assert all(s["end"] - s["start"] >= 15 for s in segments[:-1])

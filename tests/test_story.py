from shorts_pipeline import story as st
from shorts_pipeline.arcs import Unit
from shorts_pipeline.locate import MovieTranscript

SRT = "\n\n".join(f"{i + 1}\n00:{i // 60:02d}:{i % 60:02d},000 --> 00:{i // 60:02d}:{i % 60:02d},900\nline number {i} here"
                  for i in range(0, 3000, 30))


def beat(name, start, end, search=""):
    return {"name": name, "role": f"{name} role", "what_we_see": "x", "start": start, "end": end,
            "search": search or f"John Wick {name}", "key_moment": ""}


def test_clock_parsing():
    assert st.parse_clock("12:05") == 725 and st.parse_clock("1:02:03") == 3723 and st.parse_clock(90) == 90
    assert st.parse_clock("soon") is None


def test_clean_keeps_ordered_beats_and_allows_one_cold_open():
    raw = {"stories": [
        {"title": "A", "spine": "s", "hook_idea": "h", "ending_idea": "e", "cold_open": True,
         "beats": [beat("basement", "30:00", "30:30"), beat("gas station", "12:00", "12:30"),
                   beat("break-in", "17:00", "17:40"), beat("back in time", "05:00", "05:20"),
                   beat("chop shop", "22:00", "22:30")]},
        {"title": "B", "spine": "s", "hook_idea": "h", "ending_idea": "e",
         "beats": [beat("same gas station", "12:05", "12:25"), beat("x", "40:00", "40:20")]}]}
    stories = st.clean_stories(raw, 6000)
    assert len(stories) == 1  # B shares a beat and is too short without it
    names = [b["name"] for b in stories[0]["beats"]]
    assert names == ["basement", "gas station", "break-in", "chop shop"] and stories[0]["cold_open"]


def test_short_beats_are_widened_and_long_ones_capped():
    raw = {"stories": [{"title": "A", "spine": "", "hook_idea": "", "ending_idea": "",
                        "beats": [beat("a", "10:00", "10:02"), beat("b", "20:00", "40:00"), beat("c", "50:00", "50:20")]}]}
    b = st.clean_stories(raw, 6000)[0]["beats"]
    assert b[0]["movie_end"] - b[0]["movie_start"] >= st.MIN_BEAT_SECONDS
    assert b[1]["movie_end"] - b[1]["movie_start"] <= 2 * st.MAX_BEAT_SECONDS


def test_beats_get_footage_cut_to_their_own_stretch():
    story = st.clean_stories({"stories": [{"title": "A", "spine": "", "hook_idea": "", "ending_idea": "",
                                           "beats": [beat("a", "10:00", "10:30"), beat("b", "20:00", "20:30"),
                                                     beat("c", "30:00", "30:30"), beat("missing", "45:00", "45:30")]}]},
                             6000)
    # a 3-minute clip covering beat a (movie 9:00-12:00 = clip 0-180), and clips for b and c
    units = [Unit("A", "clip a", 0, 180, 540, 720, 0.5, 1080), Unit("B", "clip b", 5, 65, 1190, 1250, 0.5, 1080),
             Unit("C", "clip c", 0, 40, 1795, 1835, 0.5, 1080)]
    arcs = st.stories_to_arcs(story, units, 150)
    assert len(arcs) == 1
    scenes = arcs[0]["scenes"]
    assert [s["clip_id"] for s in scenes] == ["A", "B", "C"]
    assert scenes[0]["clip_start"] == 60 and scenes[0]["clip_end"] == 90  # only the beat's 30 s of the long clip
    assert scenes[0]["beat"]["role"] == "a role" and arcs[0]["planned"]


def test_plan_stories_uses_the_subtitle_timeline(monkeypatch):
    transcript = MovieTranscript.from_subtitles(SRT)
    seen = {}

    class Fake:
        def generate(self, role, parts, **kw):
            seen["prompt"] = parts[0]["text"]
            return {"stories": [{"title": "T", "spine": "", "hook_idea": "", "ending_idea": "",
                                 "beats": [beat("a", "01:00", "01:30"), beat("b", "10:00", "10:30"),
                                           beat("c", "20:00", "20:30")]}]}
    research = {"movie": {"title": "John Wick", "year": 2014, "runtime_minutes": 100}}
    stories = st.plan_stories(Fake(), research, transcript, "plot text", 150, count=2)
    assert len(stories) == 1 and "00:30 line number 30 here" in seen["prompt"] and "concrete" in seen["prompt"]
    assert st.beat_searches(stories)[0] == "John Wick a"


def test_timeline_is_thinned_evenly_when_too_long():
    transcript = MovieTranscript.from_subtitles(SRT)
    text = st.timeline(transcript, limit=500)
    assert len(text) <= 600 and text.startswith("00:00")

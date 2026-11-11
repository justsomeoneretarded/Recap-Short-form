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


class FakeGemini:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def generate(self, role, parts, **kw):
        self.calls.append((role, parts, kw))
        return self.answers.pop(0)


def one_story():
    return st.clean_stories({"stories": [{"title": "T", "spine": "", "hook_idea": "", "ending_idea": "",
                                          "beats": [beat("gas", "12:00", "12:30", "John Wick gas station"),
                                                    beat("break-in", "17:00", "17:30", "John Wick break in"),
                                                    beat("basement", "30:00", "30:30", "John Wick basement")]}]}, 6000)[0]


def test_suggested_links_are_parsed_from_the_answer():
    g = FakeGemini(['Here: {"scenes": [{"scene": 0, "links": ["https://www.youtube.com/watch?v=abcdefghijk", '
                    '"https://youtu.be/ZYXWVUTSRQP"]}, {"scene": 2, "links": []}]}'])
    links = st.suggest_links(g, {"title": "John Wick", "year": 2014}, one_story())
    assert links == {0: ["abcdefghijk", "ZYXWVUTSRQP"]}
    assert g.calls[0][2]["tools"] == [{"google_search": {}}]


def test_beats_are_confirmed_by_watching_before_any_download():
    story = one_story()
    candidates = [{"id": "wrongclip01", "title": "John Wick gas station Mustang", "duration": 200},
                  {"id": "rightclip01", "title": "John Wick gas station scene", "duration": 150},
                  {"id": "breakin0001", "title": "something", "suggested_for": [1], "duration": 120}]
    g = FakeGemini([{"beats": [{"beat": 0, "uploads": [0, 1]}]},
                    {"shows_scene": False, "confidence": 0.9, "start": 0, "end": 0},
                    {"shows_scene": True, "confidence": 0.9, "start": 12, "end": 41},
                    {"shows_scene": True, "confidence": 0.4, "start": 5, "end": 30}])  # too unsure
    confirmed = st.confirm_beats(g, story, candidates, {"title": "John Wick", "year": 2014})
    assert confirmed == {0: {"id": "rightclip01", "ok": True, "confidence": 0.9, "start": 12.0, "end": 41.0, "why": ""}}
    assert "youtube.com/watch?v=wrongclip01" in g.calls[1][1][0]["fileData"]["fileUri"]


def test_confirmed_scene_uses_subtitles_with_dialogue_and_gemini_when_silent():
    beat_ = one_story()["beats"][0]  # movie 720-750
    check = {"id": "rightclip01", "ok": True, "confidence": 0.9, "start": 12.0, "end": 45.0}
    spoken = {"title": "gas", "placement": {"matched": True, "offset_seconds": 700.0}, "signals": {}}
    scene = st.confirmed_scene(beat_, check, spoken, {"accept": True, "watch": {"moments": []}})
    assert (scene["clip_start"], scene["clip_end"], scene["timed_by"]) == (20.0, 48.0, "subtitles") or \
        (scene["clip_start"], scene["clip_end"]) == (20.0, 48.0)
    silent = {"title": "basement", "placement": {"matched": False}, "signals": {}}
    scene = st.confirmed_scene(beat_, check, silent, None)
    assert (scene["clip_start"], scene["clip_end"], scene["timed_by"]) == (12.0, 45.0, "gemini")
    assert st.confirmed_scene(beat_, check, spoken, {"accept": False}) is None


def test_story_arc_prefers_confirmed_footage_and_falls_back_to_placed_units():
    story = one_story()
    units = [Unit("B", "break", 0, 60, 1000, 1060, 0.5, 1080), Unit("C", "base", 0, 60, 1780, 1840, 0.5, 1080)]
    confirmed = {0: {0: {"id": "G", "ok": True, "confidence": 0.8, "start": 3.0, "end": 30.0}}}
    arcs = st.stories_to_arcs([story], units, 150, confirmed=confirmed, clips={"G": {"placement": {}}}, screening={})
    assert [s["clip_id"] for s in arcs[0]["scenes"]] == ["G", "B", "C"]
    assert arcs[0]["scenes"][0]["timed_by"] == "gemini"


def test_silent_scene_lines_are_never_played_out_of_sync():
    from shorts_pipeline import writer as w
    transcript = MovieTranscript.from_subtitles("1\n00:12:05,000 --> 00:12:07,000\nIt is not for sale my friend\n")
    arc = {"id": "a", "movie_start": 720, "movie_end": 750, "short_seconds": 60, "scenes": [
        {"clip_id": "G", "clip_title": "t", "clip_start": 3, "clip_end": 33, "movie_start": 720, "movie_end": 750,
         "timed_by": "gemini"}]}
    brief = w.build_brief(arc, {"movie": {"title": "John Wick", "year": 2014, "cast": []}}, transcript)
    assert brief.lines and not any(l["playable"] for l in brief.lines.values())



def test_scene_clips_found_by_generic_searches_are_matched_by_title():
    story = one_story()
    found = [{"id": "club", "title": "Havoc (2025) | Brutal Club Fight Scene", "queries": ["Havoc 2025 fight scene"]},
             {"id": "gas", "title": "John Wick - Gas Station Scene (HD)", "queries": ["John Wick scene"]}]
    ranked = st.likely_uploads(None, story, found, {"title": "John Wick"})  # no Gemini: shared words
    assert ranked[0] == ["gas"]
    g = FakeGemini([{"beats": [{"beat": 1, "uploads": [0]}, {"beat": 9, "uploads": [1]}]}])
    ranked = st.likely_uploads(g, story, found, {"title": "John Wick", "year": 2014})
    assert ranked[1][0] == "club" and ranked[0] == ["gas"]


def test_broad_searches_name_the_movie_and_are_not_hardcoded():
    raw = {"broad_searches": ["action", "Havoc fight scenes", "Havoc best action", "havoc fight scenes", "x" * 3,
                              "a very long search with far too many words in it to be useful"]}
    assert st.broad_searches(raw, "Havoc") == ["Havoc action", "Havoc fight scenes", "Havoc best action", "Havoc xxx"]


def test_plan_can_return_the_general_searches_too():
    transcript = MovieTranscript.from_subtitles(SRT)

    class Fake:
        def generate(self, role, parts, **kw):
            return {"broad_searches": ["kills", "Havoc shootout"],
                    "stories": [{"title": "T", "spine": "", "hook_idea": "", "ending_idea": "",
                                 "beats": [beat("a", "01:00", "01:30"), beat("b", "10:00", "10:30"),
                                           beat("c", "20:00", "20:30")]}]}
    stories, searches = st.plan_stories(Fake(), {"movie": {"title": "Havoc", "year": 2025, "runtime_minutes": 100}},
                                        transcript, "", 150, with_searches=True)
    assert len(stories) == 1 and searches == ["Havoc kills", "Havoc shootout"]


def test_story_is_planned_from_the_uploads_that_exist():
    transcript = MovieTranscript.from_subtitles(SRT)
    seen = {}

    class Fake:
        def generate(self, role, parts, **kw):
            seen["prompt"] = parts[0]["text"]
            return {"broad_searches": [], "stories": []}
    st.plan_stories(Fake(), {"movie": {"title": "Havoc", "year": 2025, "runtime_minutes": 100}}, transcript, "", 150,
                    uploads=[{"id": "a", "title": "Havoc (2025) | Brutal Club Fight Scene", "duration": 180}])
    assert "FOOTAGE THAT EXISTS" in seen["prompt"] and "Brutal Club Fight Scene (180 s)" in seen["prompt"]


def test_general_searches_come_from_one_light_request():
    g = FakeGemini([{"broad_searches": ["Fractured 2019 hospital scene", "intense scene"]}])
    assert st.general_searches(g, {"title": "Fractured", "year": 2019}, "plot") == \
        ["Fractured 2019 hospital scene", "Fractured intense scene"]
    assert g.calls[0][0] == "light" and "never to a genre template" in g.calls[0][1][0]["text"]


def test_long_confirmed_stretch_is_capped_and_soft_uploads_are_not_watched():
    beat_ = one_story()["beats"][0]
    scene = st.confirmed_scene(beat_, {"id": "x", "start": 29.0, "end": 174.0, "confidence": 0.9}, None, None)
    assert scene["clip_end"] - scene["clip_start"] <= st.MAX_BEAT_SECONDS
    g = FakeGemini([{"beats": [{"beat": 0, "uploads": [0, 1]}]}, {"shows_scene": True, "confidence": 0.9, "start": 1, "end": 20}])
    cands = [{"id": "soft", "title": "John Wick gas station 354p", "signals": {"height": 354}},
             {"id": "sharp", "title": "John Wick gas station", "signals": {"height": 1080}}]
    confirmed = st.confirm_beats(g, one_story(), cands, {"title": "John Wick", "year": 2014})
    assert confirmed[0]["id"] == "sharp"


def test_missing_beats_get_new_searches_different_from_the_tried_ones():
    g = FakeGemini([{"searches": ["John Wick break in", "John Wick 2014 home invasion", "Keanu puppy scene"]}])
    out = st.missing_searches(g, {"title": "John Wick", "year": 2014}, one_story(), [1], ["John Wick break in"])
    assert out == ["John Wick 2014 home invasion", "John Wick Keanu puppy scene"]


def test_confirm_round_only_checks_the_missing_beats_and_never_rewatches():
    watched = {(1, "breakin0001")}
    g = FakeGemini([{"beats": [{"beat": 1, "uploads": [0, 1]}]},
                    {"shows_scene": True, "confidence": 0.8, "start": 2, "end": 30}])
    cands = [{"id": "breakin0001", "title": "John Wick break in"}, {"id": "breakin0002", "title": "John Wick break in 2"}]
    got = st.confirm_beats(g, one_story(), cands, {"title": "John Wick", "year": 2014}, only={1}, checked=watched)
    assert list(got) == [1] and got[1]["id"] == "breakin0002" and (1, "breakin0002") in watched


def test_beat_moves_to_where_its_movie_lines_really_are_and_invented_quotes_are_dropped():
    transcript = MovieTranscript.from_subtitles("1\n00:12:05,000 --> 00:12:07,000\nShe is not for sale my friend\n")
    story = {"beats": [{"name": "gas", "movie_start": 1500.0, "movie_end": 1530.0,
                        "movie_lines": ["She's not for sale, my friend.", "A line nobody ever said in this film"]}]}
    st.verify_times([story], transcript, 6000)
    b = story["beats"][0]
    assert b["movie_lines"] == ["She's not for sale, my friend."] and b["time_check"] == "moved to its lines"
    assert b["movie_start"] <= 725 <= b["movie_end"]


def test_editor_rewrites_weak_scripts_and_keeps_strong_ones():
    story = one_story()
    story["hook"] = "Old hook"
    weak = FakeGemini([{"score": 5, "problems": ["flat hook"], "hook": "New hook", "narration": ["a", "b", "c"]}])
    out = st.edit_script(weak, story, {"title": "John Wick", "year": 2014})
    assert out["editor"]["rewritten"] and out["hook"] == "New hook" and out["beats"][1]["narration"] == "b"
    strong = FakeGemini([{"score": 9, "problems": [], "hook": "x", "narration": ["a", "b", "c"]}])
    assert st.edit_script(strong, story, {"title": "John Wick"})["hook"] == "Old hook"
    assert "Example 1" in weak.calls[0][1][0]["text"]  # the user's reference Shorts are the style examples


def test_style_examples_come_from_the_reference_transcripts():
    text = st.style_examples()
    assert "severing his own ring finger" in text and "[0.00" not in text


def test_uploads_of_other_films_are_never_watched_for_a_beat():
    movie = {"title": "The Equalizer 2", "year": 2018}
    assert st.names_movie("The Equalizer 2 (2018) - Trap House Scene", movie)
    assert st.names_movie("EQUALIZER II final fight", movie)
    assert not st.names_movie("Training Day (2001) - Denzel Washington scene", movie)
    assert not st.names_movie("The Equalizer (2014) hardware store", movie)   # the first film, not this one


def test_editor_flags_a_mash_up_of_two_subplots():
    g = FakeGemini([{"score": 7, "problems": ["two stories"], "hook": "h", "narration": ["a", "b", "c"],
                     "one_storyline": False}])
    story = {"title": "t", "hook": "h", "beats": [{"name": n, "role": "r", "what_we_see": "w", "narration": "x y z"}
                                                  for n in ("bankers", "miles", "gun")]}
    assert st.edit_script(g, story, {"title": "The Equalizer 2", "year": 2018})["editor"]["one_storyline"] is False


def test_a_scene_is_widened_until_its_narration_fits_the_footage():
    beat_ = {"narration": " ".join(["word"] * 87)}           # about 30 s of speech
    assert st.fit_to_narration(100.0, 110.0, 90.0, 200.0, beat_) == (100.0, 131.0)   # forward first
    assert st.fit_to_narration(100.0, 110.0, 80.0, 112.0, beat_) == (81.0, 112.0)    # then backward
    assert st.fit_to_narration(100.0, 140.0, 90.0, 200.0, beat_) == (100.0, 140.0)   # already long enough


def test_the_films_ending_is_never_used():
    raw = {"stories": [{"title": "T", "spine": "", "hook_idea": "", "ending_idea": "", "beats": [
        beat("a", "10:00", "10:30", "x"), beat("b", "40:00", "40:30", "x"), beat("c", "70:00", "70:30", "x"),
        beat("finale", "95:00", "95:30", "x")]}], "broad_searches": []}
    stories = st.clean_stories(raw, runtime=100 * 60)
    assert [b["name"] for b in stories[0]["beats"]] == ["a", "b", "c"]           # 95 min of 100: the climax

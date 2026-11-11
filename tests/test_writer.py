from shorts_pipeline import writer as w
from shorts_pipeline.locate import MovieTranscript

SRT = "\n".join([
    "1\n00:10:00,000 --> 00:10:02,000\nWINSTON: You have one hour, Jonathan.",
    "2\n00:10:03,000 --> 00:10:05,000\nI still have time.",
    "3\n00:10:40,000 --> 00:10:42,000\n[GRUNTS] Who's gonna know the difference?",
    "4\n00:12:00,000 --> 00:12:02,000\nGood luck, Mr. Wick."]) + "\n"
RESEARCH = {"movie": {"title": "John Wick: Chapter 3", "year": 2019, "overview": "John Wick is on the run.",
                      "cast": [{"name": "Keanu Reeves", "character": "John Wick"},
                               {"name": "Ian McShane", "character": "Winston"}]}}
ARC = {"id": "arc1", "movie_start": 595.0, "movie_end": 730.0, "short_seconds": 60, "footage_seconds": 90, "dialogue_before": "",
       "scenes": [{"clip_title": "John Wick: Chapter 3 (2019) - Library Fight Scene (2/10) | Movieclips",
                   "clip_start": 5.0, "clip_end": 65.0, "movie_start": 595.0, "movie_end": 655.0},
                  {"clip_title": "Doctor scene", "clip_start": 0.0, "clip_end": 30.0,
                   "movie_start": 700.0, "movie_end": 730.0}]}


def brief():
    return w.build_brief(ARC, RESEARCH, MovieTranscript.from_subtitles(SRT), plot="John Wick is excommunicado.")


def test_brief_has_lines_in_clip_time_budgets_and_clean_titles():
    b = brief()
    assert b.data["scenes"][0]["clip_title"] == "Library Fight"
    texts = {v["text"]: v for v in b.lines.values()}
    assert texts["I still have time."]["clip_start"] == 13.0  # movie 603 s − offset 590 s
    assert "Who's gonna know the difference?" in texts and "winston" in b.allowed_names
    assert b.budgets[0] > b.budgets[1]
    assert abs(sum(b.budgets.values()) - int(60 * w.WORDS_PER_SECOND * 0.85)) <= 2


def test_check_flags_invented_names_filler_quotes_and_bad_line_ids():
    b = brief()
    bad = {"title": "t", "hook": "In this movie Marcus runs.", "ending": "reveal", "beats": [
        {"scene": 0, "kind": "narration", "text": "He says 'I still have time today' to Winston."},
        {"scene": 1, "kind": "dialogue", "line": "s0l1"}]}
    issues = " | ".join(w.check(bad, b)["issues"])
    assert "filler" in issues and "marcus" in issues and "quotes dialogue" in issues and "unknown dialogue line" in issues


class FakeLLM:
    """Draft A too short, draft B good; judge prefers B; fix pass returns B unchanged."""

    def __init__(self, b):
        good = " ".join(["word"] * (b.budgets[0] - 8))
        self.drafts = [
            {"title": "A", "hook": "He runs.", "ending": "reveal", "beats": [{"scene": 0, "kind": "narration", "text": "Short."}]},
            {"title": "He Broke the Rule. Now Everyone Hunts Him.", "hook": "A bleeding man sprints through the rain.",
             "ending": "renewed_threat", "beats": [
                 {"scene": 0, "kind": "narration", "text": good},
                 {"scene": 0, "kind": "dialogue", "line": "s0l1"},
                 {"scene": 1, "kind": "narration", "text": " ".join(["more"] * b.budgets[1])}]}]
        self.calls = []

    def chat(self, system, user, schema, **kw):
        self.calls.append(schema is w.JUDGE_SCHEMA)
        if schema is w.JUDGE_SCHEMA:
            return {"scores": [{"draft": "A", "hook": 3, "clarity": 4, "faithfulness": 8, "energy": 2, "ending": 2},
                               {"draft": "B", "hook": 9, "clarity": 8, "faithfulness": 9, "energy": 8, "ending": 8}]}
        if "DRAFT:" in user:
            return self.drafts[1]
        return self.drafts[min(len([c for c in self.calls if not c]) - 1, 1)]


def test_write_short_picks_the_best_draft_and_keeps_the_chosen_line():
    b = brief()
    result = w.write_short(ARC, RESEARCH, MovieTranscript.from_subtitles(SRT), FakeLLM(b), drafts=2)
    assert result["script"]["title"].startswith("He Broke")
    assert list(result["dialogue_lines"]) == ["s0l1"] and result["dialogue_lines"]["s0l1"]["text"] == "I still have time."
    assert len(result["drafts"]) == 2 and result["drafts"][1]["total"] > result["drafts"][0]["total"]


def test_write_command_end_to_end_with_fake_model(tmp_path, monkeypatch):
    import json
    from shorts_pipeline import cli
    source = tmp_path / "discover"
    source.mkdir()
    (source / "research.json").write_text(json.dumps(RESEARCH))
    (source / "arcs.json").write_text(json.dumps({"arcs": [ARC]}))
    (source / "movie.srt").write_text(SRT)
    (source / "plot.txt").write_text("John Wick is excommunicado.")
    b = brief()

    class Model(FakeLLM):
        def __init__(self, *_args, **_kw):
            super().__init__(b)

    monkeypatch.setattr(w, "Ollama", Model)
    summary = cli.run_write(source, tmp_path / "out", drafts=2)
    assert summary["scripts"][0]["title"].startswith("He Broke")
    text = (tmp_path / "out" / "scripts.md").read_text()
    assert "I still have time." in text and "**Hook:**" in text


def test_every_model_call_starts_with_the_same_prompt_so_ollama_can_reuse_its_cache():
    b = brief()
    seen = []

    class Recorder(FakeLLM):
        def chat(self, system, user, schema, **kw):
            seen.append((system, user, kw.get("max_tokens")))
            return super().chat(system, user, schema, **kw)

    w.write_short(ARC, RESEARCH, MovieTranscript.from_subtitles(SRT), Recorder(b), drafts=2)
    prefix = w._user(w.build_brief(ARC, RESEARCH, MovieTranscript.from_subtitles(SRT))).split("\n\n")[0]
    assert len(seen) >= 3 and all(s == w.SYSTEM and u.startswith(prefix) for s, u, _ in seen)
    assert all(t is not None and t <= 1800 for *_, t in seen)


def test_long_plot_is_cut_at_a_sentence():
    plot = "He runs. " * 1000
    cut = w._trim(plot, w.PLOT_CHARS)
    assert len(cut) <= w.PLOT_CHARS and cut.endswith(".")


def test_write_command_can_write_one_story_per_machine(tmp_path, monkeypatch):
    import json
    from shorts_pipeline import cli
    source = tmp_path / "discover"
    source.mkdir()
    second = {**ARC, "id": "arc-2"}
    (source / "research.json").write_text(json.dumps(RESEARCH))
    (source / "arcs.json").write_text(json.dumps({"arcs": [ARC, second]}))
    (source / "movie.srt").write_text(SRT)
    b = brief()

    class Model(FakeLLM):
        def __init__(self, *_args, **_kw):
            super().__init__(b)

    monkeypatch.setattr(w, "Ollama", Model)
    summary = cli.run_write(source, tmp_path / "out", arc_index=1)
    assert [s["arc"] for s in summary["scripts"]] == ["arc-2"]


def test_writer_only_sees_the_plot_up_to_the_chosen_scenes():
    plot = " ".join(f"Event {i} happens." for i in range(1, 21))  # 20 sentences over a 100-minute film
    so_far, this_part = w.plot_window(plot, 30 * 60, 40 * 60, 100 * 60)
    assert "Event 5 happens." in so_far and "Event 7 happens." in this_part
    assert "Event 12 happens." not in so_far + this_part  # later events (and the ending) are never shown


def test_only_complete_single_speaker_lines_are_playable():
    assert w.playable("Viggo is not gonna like this.")
    assert not w.playable("is John Wick.") and not w.playable("sheer will.")
    assert not w.playable("Are you guys excited? - Yes!")


def test_cleanup_enforces_movie_line_rules_and_removes_quotes_and_read_out_title():
    b = brief()
    for line in b.lines.values():
        line["playable"] = True
    script = {"title": "The Last Hour", "hook": 'He says "run".', "beats": [
        {"scene": 0, "kind": "narration", "text": 'He hears "I still have time".'},
        *[{"scene": 0, "kind": "dialogue", "line": "s0l1"} for _ in range(5)],
        {"scene": 1, "kind": "narration", "text": "The Last Hour."}]}
    clean = w.cleanup(script, b)
    assert sum(x["kind"] == "dialogue" for x in clean["beats"]) == w.MAX_DIALOGUE_BEATS
    assert '"' not in clean["hook"] + " ".join(x.get("text", "") for x in clean["beats"])
    assert all(x.get("text") != "The Last Hour." for x in clean["beats"])


def test_brief_fits_the_model_context():
    from shorts_pipeline.locate import MovieTranscript
    long_srt = "\n\n".join(f"{i}\n00:{i // 60:02d}:{i % 60:02d},000 --> 00:{i // 60:02d}:{i % 60:02d},900\n"
                           f"Line number {i} is a fairly long piece of dialogue." for i in range(1, 3000))
    arc = {**ARC, "scenes": [{**ARC["scenes"][0], "movie_start": 0, "movie_end": 2900, "clip_start": 0,
                              "clip_end": 2900}] * 6}
    b = w.build_brief(arc, RESEARCH, MovieTranscript.from_subtitles(long_srt), "A plot sentence. " * 400)
    assert w._estimate_tokens(b.data) <= w.BRIEF_TOKEN_BUDGET


def test_run15_script_problems_are_caught_and_cleaned():
    b = brief()
    b.lines["x1"] = {"text": "I once saw him kill three men in a bar with a pencil.", "scene": 0, "playable": True}
    looped = ("Aurelio says they agreed to his terms. John asks if he's seen Iosef. Aurelio says he hasn't. "
              "Aurelio says they agreed to his terms. John asks if he's seen Iosef. Aurelio says he hasn't.")
    script = {"title": "Baba Yaga's Return", "hook": "John Wick digs up his guns.", "beats": [
        {"scene": 0, "kind": "narration", "text": looped},
        {"scene": 1, "kind": "narration", "text": "I once saw him kill three men in a bar with a pencil. Frost's men run."}]}
    issues = w.check(script, b)["issues"]
    assert any("repeated" in i for i in issues) and any("dialogue instead" in i for i in issues)
    assert any("retells the dialogue" in i for i in issues)
    assert not any("names not in the brief" in i and "frost" in i for i in issues) or "frost" not in b.allowed_names
    clean = w.cleanup(script, b)
    text = " ".join(x.get("text", "") for x in clean["beats"])
    assert text.count("Aurelio says they agreed to his terms.") == 1 and "pencil" not in text


def test_possessives_and_apostrophes_are_not_false_alarms():
    b = brief()
    b.allowed_names |= {"frost", "alejandro"}
    script = {"title": "A Rogue Agent", "hook": "Frost runs.", "beats": [
        {"scene": 0, "kind": "narration", "text": "Frost's men can't stop. It's a trap, and he doesn't see it. Alejandro's gun is English."}]}
    issues = w.check(script, b)["issues"]
    assert not any("names not in the brief" in i for i in issues)
    assert not any("quotes dialogue" in i for i in issues)


def test_swearing_lines_cliches_and_camera_talk_are_handled():
    assert not w.playable("You wanna start a war? You're a fucking spook!")
    b = brief()
    script = {"title": "Kate's Raid", "hook": "Agents storm a house.", "beats": [
        {"scene": 0, "kind": "narration", "text": "Every second counts. The camera lingers on her face. Her jaw tightens."}]}
    assert any("cliches" in i for i in w.check(script, b)["issues"])
    assert "camera" not in " ".join(x.get("text", "") for x in w.cleanup(script, b)["beats"])


def test_a_clean_first_draft_needs_only_one_model_call():
    b = brief()

    class GoodFirst(FakeLLM):
        def chat(self, system, user, schema, **kw):
            self.calls.append(schema is w.JUDGE_SCHEMA)
            return self.drafts[1]  # the good draft straight away

    llm = GoodFirst(b)
    result = w.write_short(ARC, RESEARCH, MovieTranscript.from_subtitles(SRT), llm, drafts=2)
    assert len(llm.calls) == 1 and not result["rejected"]


def test_being_under_the_word_budget_alone_does_not_trigger_a_rewrite():
    report = {"issues": [], "total_words": 140, "target_words": 230, "off_budget": {0: (60, 120)}}
    assert not w.needs_fix(report)
    assert w.needs_fix({**report, "total_words": 90})               # under half: worth a rewrite
    assert not w.needs_fix({**report, "issues": ["filler: meanwhile"]}, serious_only=True)
    assert w.needs_fix({**report, "issues": ["2 repeated sentences"]}, serious_only=True)



def test_hook_repeated_as_first_narration_is_dropped_not_rejected():
    from shorts_pipeline import writer as w
    brief = w.Brief({}, set(), {}, {0: 20})
    script = {"title": "T", "hook": "SWAT officers break open a wall.", "beats": [
        {"scene": 0, "kind": "narration", "text": "SWAT officers break open a wall! Bodies are inside."}]}
    clean = w.cleanup(script, brief)
    assert clean["beats"][0]["text"] == "Bodies are inside."


def test_planned_script_is_the_first_draft_with_its_movie_lines():
    from shorts_pipeline import writer as w
    from shorts_pipeline.locate import MovieTranscript
    transcript = MovieTranscript.from_subtitles("1\n00:12:05,000 --> 00:12:07,000\nShe is not for sale my friend.\n")
    arc = {"id": "a", "movie_start": 720, "movie_end": 750, "short_seconds": 60,
           "story": {"title": "The Mustang", "hook": "A gangster wants his car.", "ending_mode": "renewed_threat"},
           "missing": [{"name": "basement", "narration": "He digs up his guns."}],
           "scenes": [{"clip_id": "G", "clip_title": "t", "clip_start": 0, "clip_end": 30, "movie_start": 720,
                       "movie_end": 750, "beat": {"name": "gas", "narration": "John pumps gas into his Mustang.",
                                                  "movie_lines": ["She's not for sale, my friend."]}}]}
    brief = w.build_brief(arc, {"movie": {"title": "John Wick", "year": 2014, "cast": []}}, transcript)
    draft = w.planned_draft(arc, brief)
    assert draft["hook"] == "A gangster wants his car." and draft["beats"][0]["text"].startswith("John pumps")
    assert draft["beats"][1]["kind"] == "dialogue"
    assert brief.data["events_without_footage"][0].startswith("basement")


def test_narration_too_long_for_its_footage_is_flagged():
    from shorts_pipeline import writer as w
    brief = w.Brief({}, set(), {}, {0: 20})
    script = {"title": "T", "hook": "h", "beats": [{"scene": 0, "kind": "narration", "text": "word " * 45}]}
    assert any("too long for its footage" in i for i in w.check(script, brief)["issues"])


def test_hook_about_a_later_scene_plays_over_that_scene():
    from shorts_pipeline.writer import hook_scene
    arc = {"scenes": [{"beat": {"name": "Autopsy", "what_we_see": "Robert reads the autopsy files with Dave",
                                "key_moment": "the wound under the rib"}},
                      {"beat": {"name": "Cab", "what_we_see": "a hitman attacks Robert in his car"}},
                      {"beat": {"name": "Redial", "what_we_see": "Robert redials the phone and Dave's phone rings",
                                "key_moment": "Dave's phone rings on the counter"}}]}
    assert hook_scene("He redials the dead assassin's phone and his best friend's phone rings.", arc) == 2
    assert hook_scene("Nobody expected what came next.", arc) == 0
    assert hook_scene("anything", {**arc, "story": {"hook_beat_name": "Cab"}}) == 1


def test_a_script_well_under_its_footage_length_is_flagged_and_extended():
    b = brief()
    short = {"title": "t", "hook": "He walks in.", "ending": "reveal",
             "beats": [{"scene": 0, "kind": "narration", "text": "John fights in the library."},
                       {"scene": 1, "kind": "narration", "text": "A doctor helps him."}]}
    report = w.check(short, b)
    assert any(i.startswith("script too short") for i in report["issues"]) and w.needs_fix(report)


def test_a_numbered_word_is_not_a_name_and_one_odd_word_never_rejects_a_script():
    b = brief()
    hurricane = {"title": "t", "hook": "He waits.", "ending": "reveal", "beats": [
        {"scene": 0, "kind": "narration", "text": "John waits out a Category 5 storm in the library."}]}
    assert not any("category" in i for i in w.check(hurricane, b)["issues"])
    odd = {"title": "t", "hook": "He waits.", "ending": "reveal", "beats": [
        {"scene": 0, "kind": "narration", "text": "John fights while Zorblax watches."}]}
    issues = w.check(odd, b)["issues"]
    assert any(i.startswith("one word not in the brief") for i in issues) and not any(w.is_serious(i) for i in issues)


def test_cleanup_drops_a_sentence_repeated_in_other_words():
    b = brief()
    script = {"title": "t", "hook": "h", "ending": "reveal", "beats": [
        {"scene": 0, "kind": "narration", "text": "John stands outside the library and waits for the killers."},
        {"scene": 1, "kind": "narration", "text": "John stands outside the library, waiting for the killers. The doctor runs."}]}
    texts = [x["text"] for x in w.cleanup(script, b)["beats"]]
    assert texts[1] == "The doctor runs."

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

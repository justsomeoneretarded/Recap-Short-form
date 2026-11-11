import json

import pytest

from shorts_pipeline import gemini as g


@pytest.fixture(autouse=True)
def _no_spacing(monkeypatch):
    monkeypatch.setattr(g, "MIN_GAP", 0.0)


class Reply:
    def __init__(self, status=200, data=None, text=None, headers=None):
        self.status_code = status
        self._data = data
        self.text = text if text is not None else json.dumps(data or {})
        self.headers = headers or {}

    def json(self):
        return self._data


MODELS = {"models": [
    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.8-flash-preview-tts", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-flash-image", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
]}


def answer(obj):
    return Reply(200, {"candidates": [{"content": {"parts": [{"text": obj if isinstance(obj, str) else json.dumps(obj)}]}}],
                       "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}})


class Session:
    """Answers the model list, then the queued replies per model name."""

    def __init__(self, replies: dict, models=MODELS):
        self.replies = {k: list(v) for k, v in replies.items()}
        self.models = models
        self.posts = []

    def request(self, method, url, headers=None, timeout=None, **kwargs):
        if url.endswith("/v1beta/models"):
            return Reply(200, self.models)
        model = url.rsplit("/", 1)[-1].split(":")[0]
        self.posts.append((model, kwargs.get("json")))
        queue = self.replies.get(model) or []
        return queue.pop(0) if queue else Reply(500, text="no reply queued")


def client(replies, **kwargs):
    return g.Client("test-key", session=Session(replies, **kwargs), sleep=lambda s: None)


def test_models_are_discovered_not_hardcoded():
    ranked = {role: g.rank_models(MODELS["models"], role) for role in g.ROLES}
    assert ranked["smart"][0] == "gemini-3.5-flash" and "gemini-2.5-flash" in ranked["smart"]
    assert ranked["light"] == ["gemini-3.5-flash-lite"]
    assert ranked["embed"] == ["gemini-embedding-001"]
    assert not any("tts" in m or "image" in m for m in ranked["smart"] + ranked["light"])
    latest = g.rank_models(MODELS["models"] + [{"name": "models/gemini-flash-latest",
                                                "supportedGenerationMethods": ["generateContent"]}], "smart")
    assert latest[0] == "gemini-flash-latest"


def test_json_answer_is_parsed_even_inside_a_code_fence():
    c = client({"gemini-3.5-flash": [answer("```json\n{\"a\": 1}\n```")]})
    assert c.generate("smart", [{"text": "hi"}], schema={"type": "object"}) == {"a": 1}
    assert c.usage()["requests"] == 1


def test_per_minute_limit_waits_and_retries():
    waits = []
    c = g.Client("k", session=Session({"gemini-3.5-flash": [
        Reply(429, text='{"error": {"details": [{"retryDelay": "7s"}]}}'), answer({"ok": True})]}), sleep=waits.append)
    assert c.generate("smart", [{"text": "x"}], schema={"type": "object"}) == {"ok": True}
    assert waits == [61.0]  # a full minute: the per-minute window is fresh again


def test_daily_quota_moves_to_the_next_model_then_gives_up():
    day = Reply(429, text='{"error": {"message": "GenerateRequestsPerDayPerProjectPerModel", "details": [{"retryDelay": "5s"}]}}')
    c = client({"gemini-3.5-flash": [day], "gemini-2.5-flash": [answer({"from": "older"})]})
    assert c.generate("smart", [{"text": "x"}], schema={"type": "object"}) == {"from": "older"}
    assert "gemini-3.5-flash" in c.exhausted
    c2 = client({})  # every model fails → the caller's fallback runs
    with pytest.raises(g.GeminiUnavailable):
        c2.generate("light", [{"text": "x"}])


def test_job_budget_protects_the_shared_daily_quota():
    c = g.Client("k", session=Session({"gemini-3.5-flash": [answer("a"), answer("b")]}), sleep=lambda s: None, max_calls=1)
    assert c.generate("smart", [{"text": "x"}]) == "a"
    with pytest.raises(g.GeminiUnavailable):
        c.generate("smart", [{"text": "x"}])


def test_safety_block_is_unavailable_not_a_crash():
    blocked = Reply(200, {"promptFeedback": {"blockReason": "SAFETY"}})
    c = client({m: [blocked] for m in ("gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite")})
    with pytest.raises(g.GeminiUnavailable):
        c.generate("smart", [{"text": "x"}], schema={"type": "object"})


def test_no_key_means_off(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(g, "_CLIENT", None)
    assert g.client() is None
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("SHORTS_GEMINI", "off")
    assert g.client() is None


def test_watch_uses_the_youtube_link_and_cleans_the_answer():
    reply = {"right_movie": True, "confidence": 0.9, "kind": "movie_scene", "narrator_over_picture": False,
             "overlays": [{"start": 50, "end": 58, "what": "channel logo"}],
             "moments": [{"start": 0, "end": 4, "what": "A man walks in", "intensity": 2, "story": 3},
                         {"start": 4, "end": 9, "what": "He shoots the guard", "intensity": 15, "story": 9},
                         {"start": 70, "end": 80, "what": "past the end", "intensity": 5, "story": 5}],
             "best_moment": {"start": 4, "end": 7, "why": "sudden violence"}}
    c = client({"gemini-3.5-flash-lite": [answer(reply)]})
    watch = g.watch_clip(c, "abc123", {"title": "Sicario", "year": 2015, "cast": []}, duration=60)
    sent = c.session.posts[-1][1]["contents"][0]["parts"][0]
    assert sent["fileData"]["fileUri"].endswith("v=abc123")
    assert [m["what"] for m in watch["moments"]] == ["A man walks in", "He shoots the guard"]  # past the end dropped
    assert all(m["end"] <= 60 for m in watch["moments"]) and watch["moments"][1]["intensity"] == 10
    assert watch["best_moment"]["start"] == 4


def test_apply_watch_rejects_what_local_checks_miss():
    base = {"accept": True, "reasons": [], "notes": [], "avoid": [[1, 2]]}
    seen = g.clean_watch({"right_movie": True, "confidence": 0.9, "kind": "reaction", "narrator_over_picture": False,
                          "overlays": [{"start": 10, "end": 12, "what": "logo"}], "moments": [], "best_moment": None}, 60)
    report = g.apply_watch(base, seen)
    assert not report["accept"] and "reaction" in report["reasons"][0]
    assert [9.5, 12.5] in report["avoid"] and [1, 2] in report["avoid"]
    wrong = g.clean_watch({"right_movie": False, "confidence": 0.9, "kind": "movie_scene", "moments": []}, 60)
    assert not g.apply_watch(base, wrong)["accept"]
    unsure = g.clean_watch({"right_movie": False, "confidence": 0.4, "kind": "movie_scene", "moments": []}, 60)
    assert g.apply_watch(base, unsure)["accept"]


class Local:
    model = "qwen3:14b"

    def __init__(self):
        self.stats = []

    def chat(self, system, user, schema, **kwargs):
        self.stats.append({"prompt_tokens": 1, "prompt_seconds": 1, "output_tokens": 1, "output_seconds": 1, "total_seconds": 2})
        return {"title": "local"}


def test_writer_falls_back_to_the_local_model_for_good_when_quota_ends():
    c = g.Client("k", session=Session({"gemini-3.5-flash": [answer({"title": "gemini"})]}), sleep=lambda s: None, max_calls=1)
    made = []
    writer = g.FallbackWriter(g.GeminiWriter(c), lambda: made.append(1) or Local())
    assert writer.extras and writer.context_tokens >= 100_000
    assert writer.chat("s", "u", {"type": "object"})["title"] == "gemini"
    assert writer.chat("s", "u", {"type": "object"})["title"] == "local"
    assert writer.chat("s", "u", {"type": "object"})["title"] == "local"
    assert made == [1] and len(writer.stats) == 3 and writer.notes


def test_scene_hints_from_search():
    c = client({"gemini-3.5-flash-lite": [answer('Sure! {"scenes": ["border crossing shootout", "dinner table", "x"]}')]})
    hints = g.scene_hints(c, {"title": "Sicario", "year": 2015})
    assert hints == ["border crossing shootout", "dinner table"]
    assert c.session.posts[-1][1]["tools"] == [{"google_search": {}}]


def test_cover_pick_keeps_indexes_valid():
    from PIL import Image
    images = [Image.new("RGB", (64, 64), (i * 40, 0, 0)) for i in range(3)]
    c = client({"gemini-3.5-flash-lite": [answer({"best": 7, "second": 7, "words": "He Knew Everything Already Now"})]})
    pick = g.pick_cover(c, images, "Title")
    assert pick["best"] == 0 and pick["second"] == 1 and pick["words"] == ["He", "Knew", "Everything", "Already"]


def test_critic_scores_are_clamped(tmp_path, monkeypatch):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"0" * 10)
    c = client({"gemini-3.5-flash": [answer({"scores": {"hook": 12, "story_clarity": 6, "picture_matches_words": 5,
                                                         "pace": 7, "framing": 8, "ending": 6, "overall": 6},
                                              "keep_watching": False, "problems": [{"second": 12.3, "what": "talking head"}],
                                              "age_restriction_risk": "medium", "age_reason": "blood"})]})
    monkeypatch.setattr(c, "upload", lambda path: {"name": "files/x", "uri": "u", "mimeType": "video/mp4"})
    monkeypatch.setattr(c, "delete", lambda record: None)
    review = g.critique(c, video, "T", "script")
    assert review["scores"]["hook"] == 10 and review["age_restriction_risk"] == "medium"
    from shorts_pipeline.publish import review as checks_for
    render = {"vertical": {"fps": 60, "duplicate_frames": 0, "integrated_lufs": -14, "true_peak_db": -1.0}}
    voice = {"beats": [{"kind": "dialogue"}], "words_per_minute": 200}
    result = {"check": {"issues": []}, "script": {"hook": "A man runs now"}}
    rows = checks_for(render, voice, result, {"duration": 100, "median_shot": 2}, 120, review)
    names = {r["check"]: r["status"] for r in rows}
    assert names["viewer review (Gemini watched it)"] == "warn" and names["age restriction risk"] == "warn"
    assert "talking head" in next(r["detail"] for r in rows if r["check"] == "viewer review: problems")


def test_story_intensity_comes_from_what_is_on_screen():
    from shorts_pipeline.arcs import seen_intensity
    calm = [{"start": 0, "end": 10, "intensity": 1, "story": 2}]
    action = [{"start": 0, "end": 10, "intensity": 10, "story": 9}]
    assert seen_intensity(action, 0.5) > 0.9 > 0.2 > seen_intensity(calm, 0.5)
    assert seen_intensity([], 0.42) == 0.42


def test_edit_puts_each_sentence_over_the_shot_that_shows_it():
    from shorts_pipeline.edit import choose
    pieces = [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10), (10, 12)]
    moments = [{"start": 0, "end": 6, "what": "two men talk at a table", "intensity": 3, "story": 4},
               {"start": 6, "end": 8, "what": "the car explodes in the street", "intensity": 9, "story": 8},
               {"start": 8, "end": 12, "what": "an empty hallway", "intensity": 1, "story": 1}]
    picked = choose(pieces, 4, [], moments=moments, text="Then the car explodes.")
    assert (6, 8) in picked
    assert (8, 10) not in picked and (10, 12) not in picked  # dead moments skipped


def test_writer_brief_shows_what_is_on_screen_and_asks_for_extras():
    from shorts_pipeline import writer as w
    scene = {"clip_start": 10.0, "clip_end": 30.0,
             "moments": [{"start": 8, "end": 14, "what": "Kate enters the house"}, {"start": 14, "end": 20, "what": "Bodies in the walls"}]}
    assert w.on_screen(scene) == ["0-4s: Kate enters the house", "4-10s: Bodies in the walls"]

    class Strong:
        extras = True
    assert "cover_words" in w.schema_for(Strong())["properties"] and "pinned_comment" in w.system_for(Strong())
    assert "cover_words" not in w.schema_for(object())["properties"]


def test_zero_or_daily_limits_are_never_retried_and_minute_limits_cool_down(monkeypatch):
    monkeypatch.setattr(g, "MINUTE_RETRIES", 0)
    zero = Reply(429, text='{"error": {"message": "Quota exceeded for metric: generate_content_free_tier_requests, limit: 0", '
                          '"details": [{"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]}, '
                          '{"retryDelay": "40s"}]}}')
    minute = Reply(429, text='{"error": {"details": [{"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier", '
                            '"quotaValue": "10"}]}, {"retryDelay": "40s"}]}}')
    waits = []
    c = g.Client("k", session=Session({"gemini-3.5-flash": [zero], "gemini-2.5-flash": [minute],
                                       "gemini-3.5-flash-lite": [answer({"ok": 1})]}), sleep=waits.append)
    assert c.generate("smart", [{"text": "x"}], schema={"type": "object"}) == {"ok": 1}
    assert "gemini-3.5-flash" in c.exhausted and "gemini-2.5-flash" not in c.exhausted
    assert c.cooldown["gemini-2.5-flash"] > 0 and waits == []  # no long waits: next model straight away
    assert c.chain("smart")[0] == "gemini-3.5-flash-lite"      # the model that answered is tried first
    assert "limit is 0" in c.usage()["errors"]["gemini-3.5-flash"]


def test_google_message_names_the_limit():
    text = json.dumps({"error": {"message": "You exceeded your current quota.", "details": [{"violations": [
        {"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "quotaValue": "10",
         "quotaDimensions": {"model": "gemini-3.6-flash"}}]}]}})
    said = g.google_message(text)
    assert "PerMinute" in said and "= 10" in said and "gemini-3.6-flash" in said
    assert g.quota_problem(text)[1] is False


DAILY = '{"error": {"code": 429, "message": "You exceeded your current quota.", "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"}]}, {"retryDelay": "30s"}]}}'
MINUTE = '{"error": {"code": 429, "message": "You exceeded your current quota.", "details": [{"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "quotaValue": "15"}]}, {"retryDelay": "20s"}]}}'


class Google:
    """Fake Google with today's real behaviour: Flash models out for the day, Flash-Lite busy now and then."""

    def __init__(self, busy_every=3, flash_daily=True, always_busy=False):
        self.calls, self.n = [], 0
        self.busy_every, self.flash_daily, self.always_busy = busy_every, flash_daily, always_busy

    def request(self, method, url, headers=None, timeout=None, **kwargs):
        if url.endswith("/v1beta/models"):
            return Reply(200, MODELS)
        model = url.rsplit("/", 1)[-1].split(":")[0]
        self.calls.append(model)
        if self.always_busy:
            return Reply(429, text=MINUTE)
        if "lite" not in model and self.flash_daily:
            return Reply(429, text=DAILY)
        self.n += 1
        if self.n % self.busy_every == 0:
            return Reply(429, text=MINUTE)
        return answer({"right_movie": True, "confidence": 1, "kind": "movie_scene", "narrator_over_picture": False,
                       "overlays": [], "moments": [{"start": 0, "end": 3, "what": "x", "intensity": 5, "story": 5}],
                       "best_moment": None})


def test_todays_quota_situation_finishes_fast_and_never_retries_used_up_models(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_GEMINI_STATE", str(tmp_path / "state.json"))
    google, waits = Google(), []
    c = g.Client("k", session=google, sleep=waits.append)
    movie = {"title": "Sicario", "year": 2015, "cast": []}
    for i in range(10):  # ten clips watched, then the script
        assert g.watch_clip(c, f"clip{i}", movie, duration=60)["moments"]
    # The writer asks for Flash; every Flash model is out for the day, so Flash-Lite answers instead.
    assert c.generate("smart", [{"text": "write"}], schema={"type": "object"})["right_movie"] is True
    assert c.generate("smart", [{"text": "write"}], schema={"type": "object"})  # and goes straight there next time
    flash_calls = [m for m in google.calls if "lite" not in m]
    assert len(flash_calls) == len(set(flash_calls)) <= 2  # each used-up Flash model asked once, never again
    assert all(w == 61.0 for w in waits) and sum(waits) <= g.JOB_WAIT  # only full-minute waits, bounded
    # A later job (another machine) starts from the saved state: no request wasted on used-up models.
    later = Google()
    c2 = g.Client("k", session=later, sleep=lambda s: None)
    g.watch_clip(c2, "clip", movie, duration=60)
    assert not [m for m in later.calls if "lite" not in m]


def test_worst_case_every_model_busy_stops_waiting_within_budget():
    google, waits = Google(always_busy=True), []
    c = g.Client("k", session=google, sleep=waits.append)
    with pytest.raises(g.GeminiUnavailable):
        c.generate("light", [{"text": "x"}], schema={"type": "object"})
    assert sum(waits) <= g.REQUEST_WAIT + g.MAX_WAIT  # minutes, not a quarter hour: then the local fallback runs


def test_corner_logo_through_the_whole_clip_never_blocks_its_footage():
    base = {"accept": True, "reasons": [], "notes": [], "avoid": [], "duration": 200}
    logo = [{"start": a, "end": a + 20, "what": 'Watermark "CLIP KINGS"', "type": "channel_logo", "size": "small_corner"}
            for a in range(0, 200, 20)]
    seen = g.clean_watch({"right_movie": True, "confidence": 1, "kind": "movie_scene", "overlays": logo, "moments": []}, 200)
    report = g.apply_watch(base, seen)
    assert report["avoid"] == [] and report["accept"]
    big = [{"start": 0, "end": 150, "what": "text", "type": "text_over_picture", "size": "large"}]
    seen = g.clean_watch({"right_movie": True, "confidence": 1, "kind": "movie_scene", "overlays": big, "moments": []}, 200)
    assert g.apply_watch(base, seen)["avoid"] == []  # most of the clip: not skipped
    card = [{"start": 190, "end": 199, "what": "Available now", "type": "title_card", "size": "large"}]
    seen = g.clean_watch({"right_movie": True, "confidence": 1, "kind": "movie_scene", "overlays": card, "moments": []}, 200)
    assert g.apply_watch(base, seen)["avoid"] == [[189.5, 199.5]]


def test_picture_check_names_sentences_that_are_not_on_screen():
    c = client({"gemini-3.5-flash-lite": [answer({"problems": [{"sentence": "Lorraine plunges through the floor.",
                                                                "why": "the footage shows a man at a closet"}]})]})
    brief = {"scenes": [{"scene": 0, "on_screen": ["0-4s: a man opens a closet"], "dialogue": []}]}
    script = {"beats": [{"kind": "narration", "scene": 0, "text": "Lorraine plunges through the floor."}]}
    notes = g.picture_check(c, brief, script)
    assert notes and notes[0].startswith('not on screen: "Lorraine plunges')
    assert g.picture_check(c, {"scenes": [{"scene": 0}]}, script) == []  # nothing watched: nothing to check


def test_shot_list_maps_sentences_to_their_own_scenes_moments():
    arc = {"scenes": [{"clip_start": 10, "clip_end": 40, "moments": [
        {"start": 12, "end": 16, "what": "a man walks"}, {"start": 30, "end": 35, "what": "he smashes the floor"}]},
        {"clip_start": 0, "clip_end": 20, "moments": [{"start": 2, "end": 6, "what": "a car"}]}]}
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0, "duration": 6, "text": "He smashes the floor."},
                       {"id": "b1", "kind": "narration", "scene": 1, "duration": 4, "text": "A car waits."}]}
    c = client({"gemini-3.5-flash-lite": [answer({"shots": [{"beat": "b0", "moments": [1, 2]},
                                                             {"beat": "b1", "moments": [2]}]})]})
    shots = g.shot_list(c, arc, voice)
    assert shots == {"b0": [(30, 35)], "b1": [(2, 6)]}  # a moment from another scene is never used for b0


def test_pre_render_critic_repicks_shots_for_sentences_that_do_not_match():
    arc = {"scenes": [{"clip_id": "c", "clip_start": 0, "clip_end": 40, "moments": [
        {"start": 0, "end": 5, "what": "a man drinks tea"}, {"start": 20, "end": 26, "what": "he smashes the floor"}]}]}
    edl = {"shots": [{"clip_id": "c", "start": 0, "end": 4, "beat": "b0", "audio": "duck"}]}
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0, "text": "He smashes the concrete floor."}]}
    c = client({"gemini-3.5-flash-lite": [answer({"beats": [{"beat": "b0", "match": 2, "better": [1]}]})]})
    assert g.critique_edit(c, arc, voice, edl) == {"b0": [(20, 26)]}
    good = client({"gemini-3.5-flash-lite": [answer({"beats": [{"beat": "b0", "match": 8, "better": [1]}]})]})
    assert g.critique_edit(good, arc, voice, edl) == {}


ZERO = '{"error": {"message": "Quota exceeded for metric: generate_content_free_tier_requests, limit: 0"}}'


def test_models_with_a_zero_free_limit_are_skipped_on_later_days_too(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    monkeypatch.setenv("SHORTS_GEMINI_STATE", str(state))
    c = client({"gemini-3.5-flash": [Reply(429, text=ZERO)], "gemini-2.5-flash": [answer("ok")]})
    assert c.smart_ready() == "gemini-2.5-flash"
    saved = json.loads(state.read_text())
    assert saved["never_free"] == ["gemini-3.5-flash"]
    saved["day"] = "2000-01-01"  # the next day: daily limits are forgotten, a zero limit is not
    state.write_text(json.dumps(saved))
    later = client({"gemini-2.5-flash": [answer("ok")]})
    assert later.smart_ready() == "gemini-2.5-flash"
    assert [m for m, _ in later.session.posts] == ["gemini-2.5-flash"]


def test_quota_gate_stops_the_run_when_only_the_light_model_is_left(monkeypatch):
    from shorts_pipeline import cli
    day = Reply(429, text=DAILY)
    c = client({"gemini-3.5-flash": [day], "gemini-2.5-flash": [day]})
    assert c.smart_ready() is None
    with pytest.raises(SystemExit, match="after 08:00 UTC"):
        cli.quota_gate(c)
    assert cli.quota_gate(client({"gemini-3.5-flash": [answer("ok")]})) == "gemini-3.5-flash"


def test_light_work_never_spends_the_smart_models_quota():
    busy = Reply(429, text=DAILY)
    c = client({"gemini-3.5-flash-lite": [busy]})
    assert all("lite" in m for m in c.chain("light"))
    with pytest.raises(g.GeminiUnavailable):
        c.generate("light", [{"text": "x"}])
    assert all("lite" in m for m, _ in c.session.posts)


class Picker:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def generate(self, role, parts, **kw):
        self.calls.append((role, [p.get("text", "")[:60] for p in parts if "text" in p]))
        return self.replies.pop(0)


def test_pick_frames_keeps_valid_stretches_as_long_as_their_clause():
    arc = {"scenes": [{"clip_id": "A", "clip_start": 10.0, "clip_end": 40.0}]}
    voice = {"beats": [{"id": "b0", "kind": "narration", "scene": 0}]}
    slots = {"b0": [{"start": 0.0, "end": 3.0, "text": "He opens the trunk,"},
                    {"start": 3.0, "end": 6.0, "text": "finds the guns."}]}
    from PIL import Image
    sheets = [{"scene": 0, "times": [10.5], "image": Image.new("RGB", (64, 36))}]
    picker = Picker([{"slots": [{"id": "b0#0", "start": 12, "end": 30, "match": 8, "shown": True},
                                {"id": "b0#1", "start": 39.8, "end": 50, "match": 7, "shown": True},   # runs off the scene
                                {"id": "zz#9", "start": 1, "end": 2, "match": 9, "shown": True}]}])
    picks = g.pick_frames(picker, arc, voice, slots, sheets)
    assert picks["b0#0"] == {"start": 12.0, "end": 15.0, "match": 8, "shown": True}   # trimmed to the clause
    assert "b0#1" not in picks and "zz#9" not in picks                                # under 0.5 s left / unknown
    assert g.picks_to_director(picks, slots) == {}                                     # all clauses or none
    picks["b0#1"] = {"start": 20.0, "end": 23.0, "match": 6, "shown": True}
    assert g.picks_to_director(picks, slots) == {"b0": [(12.0, 15.0), (20.0, 23.0)]}


def test_contact_sheet_labels_real_frames(tmp_path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24", "-t", "6",
                    str(video)], check=True)
    sheets = g.frame_sheets({"scenes": [{"clip_id": "A", "clip_start": 1.0, "clip_end": 5.0, "clip_title": "t"}]},
                            {"A": str(video)}, tmp_path / "w")
    assert len(sheets) == 1 and 3 <= len(sheets[0]["times"]) <= 5 and sheets[0]["image"].size[0] > 256


def test_writer_keeps_gemini_while_another_model_is_left():
    class Primary:
        role, stats = "smart", [{}]

        def __init__(self):
            self.gemini, self.calls = self, 0

        def chain(self, role):
            return ["gemini-3.6-flash"]                         # still one model with quota

        def chat(self, *a, **k):
            self.calls += 1
            if self.calls == 1:
                raise g.GeminiUnavailable("gemini-flash-latest: daily free limit used up")
            return {"ok": True}

    class Local:
        stats, model = [{}], "qwen"

        def chat(self, *a, **k):
            return {"local": True}
    primary = Primary()
    writer = g.FallbackWriter(primary, Local)
    assert writer.chat("s", "u", {}) == {"local": True}          # this one call falls back
    assert writer.chat("s", "u", {}) == {"ok": True}             # the next one is Gemini again


def test_viewer_review_uploads_a_small_copy(monkeypatch, tmp_path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    video = tmp_path / "final.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=60", "-f", "lavfi",
                    "-i", "sine=frequency=440", "-t", "2", "-shortest", str(video)], check=True)
    uploaded = {}

    class Fake:
        def upload(self, path):
            uploaded["height"] = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                                     "stream=height", "-of", "csv=p=0", str(path)],
                                                    capture_output=True, text=True).stdout.strip())
            return {"uri": "u", "name": "n"}

        def generate(self, *a, **k):
            return {"scores": {"overall": 7}, "problems": []}

        def delete(self, record):
            pass
    g.critique(Fake(), video, "t", "words")
    assert uploaded["height"] == 480 and not (tmp_path / "final-480p.mp4").exists()

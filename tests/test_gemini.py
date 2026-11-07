import json

import pytest

from shorts_pipeline import gemini as g


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
    assert waits == [8.0]


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
    c = client({"gemini-3.5-flash": [answer('Sure! {"scenes": ["border crossing shootout", "dinner table", "x"]}')]})
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

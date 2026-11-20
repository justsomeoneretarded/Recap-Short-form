import pytest

from shorts_pipeline import discovery as d

MOVIE = {"title": "Nobody", "year": 2021, "genres": ["Action", "Thriller"],
         "cast": [{"name": "Bob Odenkirk"}, {"name": "Connie Nielsen"}],
         "clips": [{"key": "official1", "name": "Bus Fight Scene | Nobody (2021)"}]}


def info(vid, title, views=1_000_000, subs=1_000_000, verified=True, height=1080, heat=True, **extra):
    return {"id": vid, "title": title, "description": extra.pop("description", "Bob Odenkirk in Nobody (2021)"),
            "duration": extra.pop("duration", 180), "view_count": views, "like_count": views // 50,
            "channel": "Clips", "channel_follower_count": subs, "channel_is_verified": verified,
            "heatmap": [{"start_time": 30, "end_time": 35, "value": 1.0}] if heat else None,
            "formats": [{"vcodec": "avc1", "height": height, "fps": 24}], **extra}


class FakeYouTube:
    def __init__(self, results, infos):
        self.results, self.infos, self.searched = results, infos, []

    def search(self, query, count=10):
        self.searched.append(query)
        return self.results.get(query, [])

    def info(self, vid):
        if vid not in self.infos:
            raise RuntimeError("Video unavailable")
        return self.infos[vid]


def test_queries_use_studio_clip_names_hints_and_genres():
    queries = d.build_queries(MOVIE, scene_hints=["bus fight"])
    assert queries[0] == "Nobody 2021 scene"
    assert "Nobody Bus Fight Scene Nobody" not in queries and any("Bus Fight Scene" in q for q in queries)
    assert "Nobody bus fight scene" in queries and "Nobody 2021 fight scene" in queries
    assert queries[-1].endswith("compilation") or len(queries) == 12


@pytest.mark.parametrize("title,reason", [
    ("Nobody (2021) - Official Trailer", "title marks non-scene content"),
    ("Nobody Ending Explained", "title marks non-scene content"),
    ("Nobody Movie Recap in 10 minutes", "title marks non-scene content"),
    ("Random action fight", "title names neither the film nor its cast"),
    ("Knife Expert Breaks Down Nobody Bus Fight Scene", "title marks non-scene content"),
])
def test_prefilter_rejects(title, reason):
    assert d.prefilter({"title": title, "duration": 120}, MOVIE) == reason


def test_prefilter_accepts_cast_named_scene():
    assert d.prefilter({"title": "Odenkirk bus fight scene", "duration": 120}, MOVIE) is None


def test_identity_rejects_other_year_namesake():
    other = info("x", "Nobody (2007) best scene", description="Nobody 2007 Japanese film")
    assert not d.identity(other, MOVIE)["ok"]
    assert d.identity(info("y", "Nobody bus fight scene"), MOVIE)["ok"]


def test_score_rewards_audience_and_penalises_low_resolution():
    big = d.score(info("a", "t", views=50_000_000, subs=5_000_000, verified=True))
    small = d.score(info("b", "t", views=2_000, subs=300, verified=False, heat=False))
    soft = d.score(info("c", "t", views=50_000_000, subs=5_000_000, height=480))
    assert big["total"] > small["total"] and big["total"] > soft["total"]
    assert big["parts"]["verified"] == 1 and small["parts"]["verified"] == 0


def test_comment_peaks_weight_by_likes():
    peaks = d.comment_peaks([{"text": "2:13 that look", "like_count": 900}, {"text": "0:45 lol", "like_count": 1},
                             {"text": "9:99 nonsense"}, {"text": "2:13!!", "like_count": 10}], duration=300)
    assert peaks[0]["second"] == 133 and peaks[1]["second"] == 45


def test_discover_ranks_and_records_rejections():
    results = {"Nobody 2021 scene": [
        {"id": "big", "title": "Nobody bus fight scene", "view_count": 9_000_000},
        {"id": "small", "title": "Nobody kitchen scene", "view_count": 5_000},
        {"id": "trailer", "title": "Nobody Official Trailer", "view_count": 50_000_000},
        {"id": "gone", "title": "Nobody house scene", "view_count": 10}]}
    infos = {"big": info("big", "Nobody bus fight scene", views=9_000_000),
             "small": info("small", "Nobody kitchen scene", views=5_000, subs=200, verified=False, heat=False),
             "official1": info("official1", "Bus Fight Scene | Nobody (2021)", views=3_000_000)}
    result = d.discover({"movie": MOVIE}, FakeYouTube(results, infos))
    ids = [c["id"] for c in result["candidates"]]
    assert ids[-1] == "small" and set(ids) == {"big", "small", "official1"}
    assert any(r["id"] == "trailer" for r in result["rejected"])
    assert any(e.get("video") == "gone" for e in result["errors"])
    top = result["candidates"][0]
    assert top["signals"]["verified"] and top["signals"]["heatmap_peaks"][0]["start"] == 30


def test_compilation_flag_from_title_or_chapters():
    movie_info = info("comp", "Nobody all fight scenes", chapters=[{"title": "a", "start_time": 0, "end_time": 60}])
    assert d.candidate(movie_info, MOVIE, "q", set()).compilation


def test_vertical_reuploads_are_rejected():
    results = {"Nobody 2021 scene": [{"id": "v", "title": "Nobody bus fight scene", "view_count": 9}]}
    vertical = info("v", "Nobody bus fight scene")
    vertical["formats"] = [{"vcodec": "avc1", "height": 1920, "width": 1080, "fps": 30}]
    result = d.discover({"movie": {**MOVIE, "clips": []}}, FakeYouTube(results, {"v": vertical}))
    assert not result["candidates"] and "vertical" in result["rejected"][0]["reason"]


def test_youtube_budget_stops_requests_and_node_runtime_is_enabled(monkeypatch):
    yt = d.YouTube(proxy="", cookies="", budget=0)
    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="time budget"):
        yt.extract("ytsearch1:anything")
    assert d.YouTube(proxy="", cookies="")._options(False, {})["js_runtimes"] == {"node": {}}
    monkeypatch.setenv("SHORTS_YTDLP_NODE", "0")
    assert "js_runtimes" not in d.YouTube(proxy="", cookies="")._options(False, {})


def test_parallel_lookups_give_the_same_result_as_one_at_a_time(monkeypatch):
    import threading
    import time as _time
    results = {f"q{i}": [{"id": f"v{i}{j}", "title": f"Nobody scene {i}{j}", "view_count": 1000 * (10 - j)}
                         for j in range(3)] for i in range(4)}
    infos = {v["id"]: info(v["id"], v["title"], views=v["view_count"]) for r in results.values() for v in r}

    class Slow(FakeYouTube):
        def __init__(self, *a):
            super().__init__(*a)
            self.active = self.peak = 0
            self.lock = threading.Lock()

        def info(self, vid):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            _time.sleep(0.02)
            with self.lock:
                self.active -= 1
            return super().info(vid)

    monkeypatch.setattr(d, "build_queries", lambda movie, hints=None, limit=12: list(results))
    monkeypatch.setenv("SHORTS_YOUTUBE_WORKERS", "1")
    serial = d.discover({"movie": MOVIE}, FakeYouTube(results, infos))
    monkeypatch.setenv("SHORTS_YOUTUBE_WORKERS", "3")
    slow = Slow(results, infos)
    parallel = d.discover({"movie": MOVIE}, slow)
    assert [c["id"] for c in parallel["candidates"]] == [c["id"] for c in serial["candidates"]]
    assert slow.peak > 1


def test_every_search_that_found_a_video_is_remembered(monkeypatch):
    from shorts_pipeline import discovery as d
    class YT:
        def search(self, query, count):
            return [{"id": "same", "title": "Havoc club fight scene", "view_count": 5}]
        def info(self, vid):
            return {"id": vid, "title": "Havoc (2025) | Club Fight Scene", "duration": 120, "view_count": 5,
                    "formats": [{"width": 1920, "height": 1080, "vcodec": "avc1"}], "channel": "c"}
    monkeypatch.setattr(d, "build_queries", lambda movie, hints=None, limit=12: ["Havoc scene", "Havoc club fight"])
    monkeypatch.setattr(d, "identity", lambda info, movie: {"ok": True})
    out = d.discover({"movie": {"title": "Havoc", "year": 2025, "clips": []}}, YT())
    assert out["candidates"][0]["queries"] == ["Havoc scene", "Havoc club fight"]


def test_good_channels_are_followed_and_playlists_searched(monkeypatch):
    from shorts_pipeline import discovery as d
    cands = [{"id": "a" * 11, "title": "Havoc (2025) | Club Fight Scene", "duration": 180, "channel_url": "https://yt/@Clips",
              "signals": {"height": 1080}, "score": {"total": 0.5}},
             {"id": "b" * 11, "title": "Havoc review", "duration": 900, "channel_url": "https://yt/@Critic",
              "signals": {"height": 1080}, "score": {"total": 0.9}}]
    assert d.good_channels(cands) == ["https://yt/@Clips"]

    class YT:
        def channel_search(self, url, query, count):
            return [{"id": "c" * 11, "title": "Havoc Cabin Shootout Scene", "duration": 200}, {"id": "a" * 11, "title": "dup"}]
        def search_playlists(self, query, count):
            return [{"url": "https://yt/playlist?list=PL1", "title": "Havoc (2025) all scenes"}]
        def playlist(self, url, count):
            return [{"id": "d" * 11, "title": "Havoc hospital shootout", "duration": 150}]
    monkeypatch.setattr(d, "candidate_from_id", lambda yt, vid, movie, query: {"id": vid, "queries": [query]})
    new = d.expand(YT(), {"title": "Havoc", "year": 2025, "cast": []}, cands)
    assert {c["id"] for c in new} == {"c" * 11, "d" * 11}
    assert any(c["queries"][0].startswith("playlist") for c in new)


def test_title_filter_spares_the_movies_own_name_and_ending_scenes():
    from shorts_pipeline import discovery as d
    game = {"title": "The Game", "year": 1997, "cast": []}
    assert d.prefilter({"title": "The Game (1997) - Final Scene", "duration": 120}, game) is None
    assert d.prefilter({"title": "The Game (1997) review", "duration": 120}, game)
    frac = {"title": "Fractured", "year": 2019, "cast": []}
    assert d.prefilter({"title": "Fractured (2019) ending scene", "duration": 120}, frac) is None
    assert d.prefilter({"title": "Fractured ending explained", "duration": 120}, frac)


def test_coverage_counts_clean_scene_uploads():
    from shorts_pipeline import discovery as d
    c = [{"title": "Havoc club fight scene", "duration": 180, "signals": {"height": 1080}},
         {"title": "Havoc club fight scene", "duration": 180, "signals": {"height": 360}},
         {"title": "Havoc review", "duration": 600, "signals": {"height": 1080}}]
    assert d.coverage(c) == 1


def test_the_youtube_budget_counts_only_time_spent_on_youtube(monkeypatch):
    import time as _time
    yt = d.YouTube(proxy="", cookies="", budget=5)
    calls = []

    def fake_extract(target, **extra):
        calls.append(target)
        yt_spent_before = yt.spent
        return {"id": target, "spent_before": yt_spent_before}
    monkeypatch.setattr(yt, "_extract", fake_extract)
    _time.sleep(0.05)                                  # time outside YouTube (a slow Gemini answer) is free
    assert yt.extract("https://www.youtube.com/watch?v=abc")["id"].endswith("abc") and yt.spent < 1
    yt.spent = 6.0                                     # the budget is used up ...
    with pytest.raises(RuntimeError, match="budget"):
        yt.extract("https://www.youtube.com/watch?v=other")
    yt.must = {"needed1"}                              # ... but a found story's clip still gets downloaded
    assert yt.extract("https://www.youtube.com/watch?v=needed1")
    yt.spent = 6.0 + yt.reserve
    with pytest.raises(RuntimeError, match="budget"):
        yt.extract("https://www.youtube.com/watch?v=needed1")


class _FakeYDL:
    """yt-dlp stand-in: answers per (proxy?, cookies?) route with a result or an error."""
    answers = {}
    seen = []

    def __init__(self, options):
        self.route = (bool(options.get("proxy")), bool(options.get("cookiefile")))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, target, download=False):
        _FakeYDL.seen.append((target[-11:], self.route))
        answer = _FakeYDL.answers.get(self.route, "ERROR: Video unavailable. This content isn’t available.")
        if isinstance(answer, str):
            raise Exception(answer)
        return answer


@pytest.fixture
def fake_ytdlp(monkeypatch, tmp_path):
    import sys
    import types
    module = types.SimpleNamespace(YoutubeDL=_FakeYDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", module)
    _FakeYDL.answers, _FakeYDL.seen = {}, []
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("x")
    yt = d.YouTube(proxy="socks5h://127.0.0.1:1", cookies=str(cookies), pause=0)
    yt.bot_backoff = 0
    return yt


def test_content_isnt_available_is_a_block_tried_through_the_proxy_then_without_cookies(fake_ytdlp):
    yt = fake_ytdlp
    _FakeYDL.answers = {(True, False): {"id": "aaaaaaaaaaa"}}            # only the proxy without cookies works
    assert yt.extract("https://www.youtube.com/watch?v=aaaaaaaaaaa") == {"id": "aaaaaaaaaaa"}
    routes = [r for _, r in _FakeYDL.seen]
    assert routes[0] == (False, True) and (True, True) in routes and routes[-1] == (True, False)
    assert yt.prefer_proxy and yt.served == 1


def test_a_runner_youtube_refuses_everywhere_stops_with_a_clear_message(fake_ytdlp):
    yt = fake_ytdlp
    for i in range(d.BLOCKED_STOP - 1):
        with pytest.raises(RuntimeError):
            yt.extract(f"https://www.youtube.com/watch?v=video{i:06d}")
    with pytest.raises(d.YouTubeBlocked):
        yt.extract("https://www.youtube.com/watch?v=videolast00")
    assert yt.blocked_runner
    _FakeYDL.seen.clear()
    with pytest.raises(d.YouTubeBlocked):                                    # no more time spent on YouTube
        yt.extract("https://www.youtube.com/watch?v=another0000")
    assert _FakeYDL.seen == []


def test_a_really_deleted_video_is_skipped_at_once(fake_ytdlp):
    yt = fake_ytdlp
    _FakeYDL.answers = {(False, True): "ERROR: Video unavailable. This video has been removed by the uploader"}
    with pytest.raises(RuntimeError, match="removed"):
        yt.extract("https://www.youtube.com/watch?v=gone0000000")
    assert len(_FakeYDL.seen) == 1 and not yt.blocked

"""The unified runner: script first, adaptive hunt, fallbacks (all with fakes, no network)."""
from shorts_pipeline import hunt as h
from shorts_pipeline import story as st
from shorts_pipeline.arcs import Unit


def script(title="T", beats=(("gas", 720), ("break-in", 1020), ("chop shop", 1320), ("basement", 1800))):
    return {"title": title, "spine": "", "hook_idea": "", "ending_idea": "", "ending_mode": "renewed_threat",
            "hook": "He would not sell the car.", "hooks": [], "cold_open": False,
            "beats": [{"name": n, "role": f"{n} role", "what_we_see": n, "search": f"John Wick {n}", "key_moment": "",
                       "narration": f"Narration for {n}.", "movie_lines": [], "movie_start": t, "movie_end": t + 30}
                      for n, t in beats]}


class FakeHunt(h.Hunt):
    """Placement 'proves' the beats listed in `placeable`; records what the hunt did."""

    def __init__(self, placeable, found_count=20, footage="auto"):
        self.placeable = placeable
        self.calls = []
        research = {"movie": {"title": "John Wick", "year": 2014, "runtime_minutes": 101}}
        clips = [{"id": f"v{i:010d}", "title": f"John Wick scene {i}", "duration": 120, "signals": {"height": 1080}}
                 for i in range(found_count)]
        super().__init__(None, research, None, "/tmp", footage=footage, log=lambda m: None,
                         discover=lambda *a, **k: {"candidates": clips, "queries": k.get("scene_hints") or ["q"],
                                                   "rejected": [], "errors": []},
                         place=self._fake_place, expand=lambda *a, **k: self.calls.append("expand") or [])

    def _fake_place(self, research, discovered, youtube, workdir, top, use_whisper):
        self.calls.append(("place", len(discovered["candidates"])))
        return {"clips": discovered["candidates"], "placed": 0, "considered": len(discovered["candidates"])}

    def units(self, screened=None):
        return [Unit(f"u{t}", "u", 0, 40, t - 5, t + 35, 0.5, 1080) for t in self.placeable]


def run(monkeypatch, fake, *, confirm=None, length=150):
    monkeypatch.setattr(h, "plan_scripts", lambda *a, **k: [script("A"), script("B", (("x", 3000), ("y", 3300), ("z", 3600)))])
    monkeypatch.setattr(st, "general_searches", lambda *a, **k: ["John Wick action"])
    monkeypatch.setattr(st, "likely_uploads", lambda g, story, c, m: {i: [c[i % len(c)]["id"]] for i in range(len(story["beats"]))})
    monkeypatch.setattr(st, "suggest_links", lambda *a, **k: {})
    monkeypatch.setattr(st, "missing_searches", lambda *a, **k: fake.calls.append("more searches") or ["John Wick new"])
    watched = []

    def fake_confirm(g, story, c, m, *, log=None, only=None, checked=None, **k):
        watched.append(sorted(only or []))
        return confirm(story, only) if confirm else {}
    monkeypatch.setattr(st, "confirm_beats", fake_confirm)
    out = h.run(None, fake.research, None, "", None, "/tmp", length=length, wanted=1, screen=lambda placed, first: {},
                hunt=fake)
    return out, watched


def test_well_covered_movie_takes_the_light_path(monkeypatch):
    fake = FakeHunt(placeable=[720, 1020, 1320, 1800])
    out, watched = run(monkeypatch, fake)
    assert out["report"]["path"] == "script" and len(out["arcs"]) == 1
    assert len(out["arcs"][0]["scenes"]) == 4 and watched == []          # subtitles proved every beat: no watching
    assert "expand" not in fake.calls and out["report"]["coverage"] >= h.COVERAGE_PLENTY
    assert set(out["arcs"][0]["found_by"].values()) == {"subtitles"}


def test_rare_movie_widens_and_watches_only_the_missing_beats(monkeypatch):
    fake = FakeHunt(placeable=[720], found_count=3)
    confirm = lambda story, only: {i: {"id": f"v{i:010d}", "ok": True, "confidence": 0.9, "start": 2.0, "end": 30.0}
                                   for i in only if i in (1, 2)}
    out, watched = run(monkeypatch, fake, confirm=confirm, length=120)   # 3 scenes of 30 s: enough for 120 s
    assert watched[0] == [1, 2, 3]                                       # beat 0 was proven by subtitles
    assert "expand" in fake.calls and "more searches" in fake.calls      # beat 3 still missing → wider hunt
    arc = out["arcs"][0]
    assert [s["beat"]["name"] for s in arc["scenes"]] == ["gas", "break-in", "chop shop"]
    assert [m["name"] for m in arc["missing"]] == ["basement"]
    assert arc["found_by"] == {"gas": "subtitles", "break-in": "watching", "chop shop": "watching"}


def test_no_script_with_footage_falls_back_to_a_footage_aware_replan(monkeypatch):
    fake = FakeHunt(placeable=[], found_count=3)
    plans = []
    monkeypatch.setattr(h, "plan_scripts", lambda *a, **k: plans.append(k.get("uploads") is not None) or [script()])
    monkeypatch.setattr(st, "general_searches", lambda *a, **k: [])
    monkeypatch.setattr(st, "likely_uploads", lambda *a, **k: {})
    monkeypatch.setattr(st, "suggest_links", lambda *a, **k: {})
    monkeypatch.setattr(st, "missing_searches", lambda *a, **k: [])
    monkeypatch.setattr(st, "confirm_beats", lambda *a, **k: {})
    out = h.run(None, fake.research, None, "", None, "/tmp", length=150, wanted=1, screen=None, hunt=fake)
    assert plans == [False, True] and out["arcs"] == []
    assert out["report"]["path"].startswith("scene-by-scene")


def test_plenty_never_widens(monkeypatch):
    fake = FakeHunt(placeable=[720], found_count=2, footage="plenty")
    run(monkeypatch, fake)
    assert "expand" not in fake.calls


def test_a_script_missing_its_attack_scene_loses_to_a_complete_one():
    from shorts_pipeline.hunt import rank_results, script_rank
    traitor = {"beats": [{"role": "the inciting crime", "what_we_see": "two men stab her"}] +
                        [{"role": "talk", "what_we_see": "they talk"}] * 4, "editor": {"score": 6}}
    miles = {"beats": [{"role": "deadline", "what_we_see": "a gun is handed over"}] * 5, "editor": {"score": 6}}
    a = {"n": 0, "ok": True, "rank": script_rank(traitor, {1, 2, 3, 4})}   # the hotel killing has no footage
    b = {"n": 1, "ok": True, "rank": script_rank(miles, {0, 1, 2, 3, 4})}
    ranked = rank_results([a, b], wanted=1)
    assert ranked[0]["n"] == 1 and ranked[0]["ok"] and not ranked[1]["ok"]


class ScreeningHunt(FakeHunt):
    """Before screening every listed beat has footage; screening then rejects the clips of `rejected`."""

    def __init__(self, placeable, rejected):
        super().__init__(placeable)
        self.rejected = rejected

    def units(self, screened=None):
        keep = [t for t in self.placeable if not (screened and t in self.rejected)]
        return [Unit(f"u{t}", "u", 0, 40, t - 5, t + 35, 0.5, 1080) for t in keep]


def test_a_script_that_loses_scenes_in_screening_gives_way_to_the_spare_without_a_replan(monkeypatch):
    fake = ScreeningHunt(placeable=[720, 1020, 1320, 1800, 3000, 3300, 3600], rejected={1320, 1800})
    plans = []
    monkeypatch.setattr(h, "plan_scripts", lambda *a, **k: plans.append(k.get("uploads") is not None) or
                        [script("A"), script("B", (("x", 3000), ("y", 3300), ("z", 3600)))])
    monkeypatch.setattr(st, "general_searches", lambda *a, **k: [])
    monkeypatch.setattr(st, "likely_uploads", lambda *a, **k: {})
    monkeypatch.setattr(st, "suggest_links", lambda *a, **k: {})
    monkeypatch.setattr(st, "missing_searches", lambda *a, **k: [])
    monkeypatch.setattr(st, "confirm_beats", lambda *a, **k: {})
    screen = lambda placed, first: {"bad": {"accept": False, "reasons": ["burned-in subtitles inside the picture"]}}
    out = h.run(None, fake.research, None, "", None, "/tmp", length=120, wanted=1, screen=screen, hunt=fake)
    assert plans == [False]                                   # no mash-up re-plan
    assert out["report"]["path"] == "script" and out["arcs"][0]["story"]["title"] == "B"


def test_mash_up_scripts_are_dropped_before_the_hunt(monkeypatch):
    stories = [dict(script("mash"), editor={"one_storyline": False}), script("one")]
    monkeypatch.setattr(st, "plan_stories", lambda *a, **k: stories)
    monkeypatch.setattr(st, "verify_times", lambda *a, **k: None)
    monkeypatch.setattr(st, "edit_script", lambda g, story, movie: story)
    kept = h.plan_scripts(None, {"movie": {"title": "John Wick", "runtime_minutes": 101}}, None, "", 150, 2,
                          log=lambda m: None)
    assert [s["title"] for s in kept] == ["one"]


def test_half_a_story_or_too_little_footage_is_never_made(monkeypatch):
    assert not h.usable({"beats": [{}] * 6}, {0, 1, 2})          # 3 of 6 scenes (run 38)
    assert h.usable({"beats": [{}] * 6}, {0, 1, 2, 3, 4})
    fake = FakeHunt(placeable=[720, 1020, 1320])                   # 3 of 4 scenes, about 90 s of footage
    out, _ = run(monkeypatch, fake, length=150)                    # a 150 s Short needs at least 105 s
    assert out["arcs"] == []

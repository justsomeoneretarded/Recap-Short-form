from shorts_pipeline import arcs as a


def clip(cid, movie_start, duration=120, score=0.8, height=1080, peaks=(), segments=None, title=None):
    placement = {"matched": True, "offset_seconds": movie_start, "movie_start": movie_start,
                 "movie_end": movie_start + duration}
    if segments:
        placement["segments"] = segments
    return {"id": cid, "title": title or cid, "duration": duration, "placement": placement, "score": {"total": score},
            "signals": {"height": height, "heatmap_peaks": [{"start": p} for p in peaks]}, "comment_peaks": []}


def test_duplicates_keep_the_best_upload_and_remember_alternates():
    units = a.merge_duplicates(a.units_from([clip("low", 1000, score=0.5), clip("high", 1010, score=0.9)], {}))
    assert len(units) == 1 and units[0].clip_id == "high" and units[0].alternates == ["low"]


def test_rejected_clips_and_end_cards_are_excluded():
    screening = {"bad": {"accept": False}, "ok": {"accept": True, "usable": [5.0, 100.0]}}
    units = a.units_from([clip("bad", 0), clip("ok", 500)], screening)
    assert [u.clip_id for u in units] == ["ok"] and (units[0].clip_start, units[0].clip_end) == (5.0, 100.0)
    assert units[0].movie_start == 505.0


def test_compilation_segments_become_separate_scenes():
    segments = [{"start": 0, "end": 60, "matched": True, "offset_seconds": 2000},
                {"start": 60, "end": 120, "matched": False},
                {"start": 120, "end": 180, "matched": True, "offset_seconds": 4000}]
    units = a.units_from([clip("comp", 0, duration=180, segments=segments)], {})
    assert [(u.clip_start, round(u.movie_start)) for u in units] == [(0, 2000), (120, 4000)]


def test_arcs_cover_nearby_scenes_never_share_footage_and_rank():
    clips = [clip("a", 600, peaks=[30]), clip("b", 760), clip("c", 900),          # one story around 10–17 min
             clip("d", 3600, score=0.95), clip("e", 3750, score=0.95),             # another around 60–64 min
             clip("f", 6000, duration=40, score=0.3)]                              # a lone short scene
    result = a.build_arcs(clips, {}, target_seconds=150)
    arcs = result["arcs"]
    used = [s["clip_id"] for arc in arcs for s in arc["scenes"]]
    assert len(used) == len(set(used))  # no footage reused across Shorts
    assert all(arc["footage_seconds"] >= 0.6 * 150 for arc in arcs)
    assert {s["clip_id"] for s in arcs[0]["scenes"]} <= {"a", "b", "c"}
    assert arcs == sorted(arcs, key=lambda x: x["movie_start"]) and len(arcs) <= 5


def test_thin_footage_still_makes_one_shorter_short():
    result = a.build_arcs([clip("only", 100, duration=50)], {}, target_seconds=150)
    assert len(result["arcs"]) == 1 and result["arcs"][0]["shorter_than_requested"]

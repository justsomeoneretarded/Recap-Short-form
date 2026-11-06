import shutil
import subprocess

import pytest

from shorts_pipeline import covers, publish

RESEARCH = {"movie": {"title": "Nobody", "year": 2021, "genres": ["Action", "Thriller"], "keywords": ["bus"],
                      "cast": [{"name": "Bob Odenkirk"}, {"name": "Connie Nielsen"}]}}
RESULT = {"script": {"title": "He Was a Nobody. Now Everyone Knows.", "hook": "A quiet dad steps onto the wrong bus.",
                     "beats": []},
          "check": {"issues": []},
          "drafts": [{"script": {"title": "He Was a Nobody. Now Everyone Knows."}},
                     {"script": {"title": "Never Wake the Quiet Dad"}}, {"script": None}]}
ARC = {"id": "arc1", "scenes": [{"clip_id": "abc12345678"}, {"clip_id": "abc12345678"}]}


def test_hook_words_take_the_punchy_last_clause():
    assert covers.hook_words("He Was Hired to Kill. Now He's the Prey.") == ["NOW", "HE'S", "THE", "PREY"]
    assert covers.hook_words("The Quiet Guy Was the Deadliest Man in the Whole City") == ["DEADLIEST", "MAN", "WHOLE", "CITY"]


def test_titles_description_tags():
    assert publish.title_options(RESULT) == ["He Was a Nobody. Now Everyone Knows.", "Never Wake the Quiet Dad"]
    text = publish.description(RESULT, RESEARCH, ARC, {"abc12345678": {"channel": "Movieclips"}})
    assert text.startswith("A quiet dad") and "#Nobody" in text and "#Shorts" in text
    assert text.count("watch?v=abc12345678") == 1  # duplicate sources listed once
    tags = publish.tags(RESEARCH)
    assert "Nobody recap" in tags and "Bob Odenkirk" in tags and sum(len(t) + 1 for t in tags) <= 480


def test_review_flags_fake_60fps_and_loudness():
    render = {"square": {"fps": 60.0, "duplicate_frames": 0.6, "integrated_lufs": -9.0, "true_peak_db": 0.5,
                         "modes": {"track": 8, "fit": 2}}}
    voice = {"words_per_minute": 200, "beats": [{"kind": "dialogue"}]}
    checks = {c["check"]: c["status"] for c in publish.review(render, voice, RESULT, {"duration": 120, "median_shot": 2.2}, 150)}
    assert checks["square: real motion (no copied frames)"] == "fail" and checks["square: loudness"] == "warn"
    assert checks["length"] == "pass" and checks["narration pace"] == "pass"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_covers_and_package(tmp_path):
    video = tmp_path / "final.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24", "-t", "6",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    edl = {"shots": [{"timeline_start": t, "duration": 1.0} for t in range(6)], "duration": 6.0, "median_shot": 1.0}
    made = covers.make_covers(video, edl, RESULT["script"]["title"], tmp_path / "pkg")
    assert len(made["covers"]) == 6 and made["hook"] == "NOW EVERYONE KNOWS"
    from PIL import Image
    assert Image.open(made["covers"]["vertical-hook"]).size == (1080, 1920)
    sheet = covers.contact_sheet(video, 6.0, tmp_path / "pkg" / "contact-sheet.jpg")
    render = {"square": {"fps": 60.0, "duplicate_frames": 0.01, "integrated_lufs": -14.1, "true_peak_db": -1.2,
                         "modes": {"track": 5, "fit": 1}}}
    pack = publish.write_package(tmp_path / "pkg", result=RESULT, research=RESEARCH, arc=ARC, clips={},
                                 voiceover={"words_per_minute": 205, "beats": [{"kind": "dialogue"}]}, edl=edl,
                                 render=render, covers=made, sheet=str(sheet), target_seconds=10)
    assert (tmp_path / "pkg" / "review.html").read_text().count("PASS") >= 5 and pack["verdict"] in ("pass", "warn")

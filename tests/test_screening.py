import shutil
import subprocess

import pytest

pytest.importorskip("rapidocr_onnxruntime")
from shorts_pipeline import screening as s  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
LINES = ["WHERE IS THE MONEY", "I STILL HAVE TIME", "WHO WILL KNOW", "GOOD LUCK MISTER",
         "THE CLOCK STRIKES SIX", "EVERYONE IS WATCHING"]


def subtitles(y: str, size: int = 34) -> str:
    return ",".join(f"drawtext=fontfile={FONT}:text='{t}':fontsize={size}:fontcolor=white:borderw=3:"
                    f"x=(w-text_w)/2:y={y}:enable='between(t,{2 * i},{2 * i + 1.9})'" for i, t in enumerate(LINES))


def make(path, vf, size="960x540", seconds=12):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"mandelbrot=size={size}:rate=24",
                    "-t", str(seconds), "-vf", vf, "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
                    str(path)], check=True)
    return path


@pytest.fixture(autouse=True)
def small_test_clips(monkeypatch):
    monkeypatch.setattr(s, "MIN_HEIGHT", 480)  # test clips are 540p to stay fast


@pytest.fixture(scope="module")
def videos(tmp_path_factory):
    d = tmp_path_factory.mktemp("screen")
    return {
        "clean": make(d / "clean.mp4", "null"),
        "subs": make(d / "subs.mp4", subtitles("h*0.80")),
        "bars": make(d / "bars.mp4", "scale=960:400,pad=960:540:0:70," + subtitles("h-52", 26)),
        "mark": make(d / "mark.mp4", f"drawtext=fontfile={FONT}:text='CLIPHUB':fontsize=30:fontcolor=white:x=w-tw-20:y=20"),
        "promo": make(d / "promo.mp4", f"drawtext=fontfile={FONT}:text='IN THEATERS JULY 4':fontsize=48:fontcolor=white:"
                                       "x=(w-tw)/2:y=(h-th)/2:enable='lt(mod(t,4),2)'"),
        "mirror": make(d / "mirror.mp4", subtitles("h*0.80") + ",hflip"),
        "endcard": make(d / "endcard.mp4", f"drawtext=fontfile={FONT}:text='AVAILABLE ON DIGITAL NOW':fontsize=44:"
                                           "fontcolor=white:x=(w-tw)/2:y=(h-th)/2:enable='gte(t,9)'", seconds=12),
    }


def test_clean_clip_is_accepted(videos):
    report = s.screen(videos["clean"])
    assert report["accept"], report["reasons"]


def test_burned_subtitles_in_picture_mark_the_clip_as_a_last_resort(videos):
    report = s.screen(videos["subs"])
    assert report["accept"] and report["subtitled"]                      # kept, only used when nothing else shows it
    assert report["active"]["subtitle_crop"] <= report["active"]["box"][3] - 0.1  # the picture ends above them


def test_subtitles_only_in_black_bars_are_allowed(videos):
    report = s.screen(videos["bars"])
    assert report["active"]["bars"] and report["accept"], report
    assert any("black bars" in n for n in report["notes"])


def test_corner_watermark_is_noted_not_rejected(videos):
    report = s.screen(videos["mark"])
    assert report["accept"] and report["text"]["watermarks"]


def test_end_card_is_trimmed_not_rejected(videos):
    report = s.screen(videos["endcard"])
    assert report["accept"], report["reasons"]
    assert report["usable"][1] <= 9.0 and any("trimmed" in n for n in report["notes"])


def test_promo_cards_are_rejected(videos):
    assert any("promo" in r for r in s.screen(videos["promo"])["reasons"])


def test_mirrored_upload_is_rejected(videos):
    assert any("mirrored" in r for r in s.screen(videos["mirror"])["reasons"])


def test_narration_heuristic():
    assert s.narration_suspected({"clip_words": 300, "share": 0.02, "matched": False}, 120)
    assert not s.narration_suspected({"clip_words": 300, "share": 0.6, "matched": True}, 120)
    assert not s.narration_suspected({"clip_words": 20, "share": 0.0, "matched": False}, 120)


def test_low_resolution_uploads_are_rejected(videos, monkeypatch):
    monkeypatch.setattr(s, "MIN_HEIGHT", 720)
    report = s.screen(videos["clean"])  # 540p test clip
    assert any("low resolution" in r for r in report["reasons"])


def test_channel_handle_inside_the_picture_is_rejected(tmp_path):
    clip = make(tmp_path / "handle.mp4", f"drawtext=fontfile={FONT}:text='@filmcharacter':fontsize=34:fontcolor=white:"
                                         "x=w*0.12:y=h*0.62")
    report = s.screen(clip)
    assert not report["accept"]


def _rows(text, y0=0.92, y1=0.97, x0=0.30, x1=0.70, w=1000, h=1000):
    return {"box": (x0 * w, y0 * h, x1 * w, y1 * h), "text": text}


def test_studio_copyright_line_is_neither_subtitle_nor_logo():
    import numpy as np
    from shorts_pipeline.screening import classify_text
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
    samples = [(t, [_rows(f"@ 2018 Columbia Pictures {t}")], frame) for t in range(6)]   # OCR reads (c) as @
    text = classify_text(samples, (0, 0, 1, 1))
    assert text["subtitle_frames"] == 0 and not text["inner_watermarks"] and text["copyright_rows"] == 6


def test_real_subtitles_still_count():
    import numpy as np
    from shorts_pipeline.screening import classify_text
    frame = np.zeros((1000, 1000, 3), dtype=np.uint8)
    lines = ["I will find you.", "Who are you?", "Get out of my car.", "Nobody.", "Run."]
    text = classify_text([(t, [_rows(line, 0.80, 0.86)], frame) for t, line in enumerate(lines)], (0, 0, 1, 1))
    assert text["subtitle_frames"] == 5 and text["distinct_subtitle_lines"] == 5

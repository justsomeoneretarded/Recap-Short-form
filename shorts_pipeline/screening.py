"""Reject footage that would look bad or wrong in a Short.

Checks on a downloaded clip (all CPU, sampled frames):
- active picture: letterbox/pillarbox bars and added borders (cropdetect);
- burned subtitles: changing text in the lower part of the picture. Text that sits only in the
  black bars is fine (the crop removes it); text inside the picture rejects the clip;
- watermarks/logos: the same text box repeated in a corner (kept out of the crop, rejected if large);
- trailer material: promo cards ("in theaters", ratings) and very fast cutting;
- mirrored uploads: on-screen text that reads better when flipped;
- existing narration: lots of speech that does not match the movie's own dialogue.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np

from .media import probe

SAMPLE_WIDTH = 640
PROMO = re.compile(r"\b(in theaters|in cinemas|coming soon|only in|now playing|this (?:summer|fall|winter|spring|"
                   r"christmas)|tickets|rated [rgp]|pg-?13|restricted|subscribe|official trailer|in theatres|"
                   r"streaming|now on|watch now|available on)\b", re.I)


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def read_text(frame: np.ndarray, minimum_score: float = 0.6) -> list[dict]:
    """OCR one RGB frame → [{'text', 'score', 'box': (x0, y0, x1, y1) in pixels}]."""
    result, _ = _ocr()(frame[:, :, ::-1])  # RapidOCR expects BGR like OpenCV
    rows = []
    for box, text, score in result or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        if float(score) >= minimum_score and len(text.strip()) >= 2:
            rows.append({"text": text.strip(), "score": float(score),
                         "box": (min(xs), min(ys), max(xs), max(ys))})
    return rows


def sample_frames(video: Path, *, every: float = 1.0, limit: int = 90, start: float = 0.0,
                  duration: float | None = None) -> list[tuple[float, np.ndarray]]:
    info = probe(video)
    width, height = info["width"], info["height"]
    out_w = SAMPLE_WIDTH if width > SAMPLE_WIDTH else width - width % 2
    out_h = int(round(height * out_w / width / 2) * 2)
    length = duration if duration is not None else max(0.0, info["duration"] - start)
    step = max(every, length / limit) if length > 0 else every
    command = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{length:.3f}",
               "-vf", f"fps=1/{step:.4f},scale={out_w}:{out_h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(command, capture_output=True, check=True).stdout
    size = out_w * out_h * 3
    frames = [np.frombuffer(raw[i:i + size], dtype=np.uint8).reshape(out_h, out_w, 3)
              for i in range(0, len(raw) - size + 1, size)]
    return [(start + i * step, f) for i, f in enumerate(frames)]


def active_box(frames: list[tuple[float, np.ndarray]], dark: int = 18, share: float = 0.9) -> dict:
    """The picture area without black bars, as fractions of the frame (x0, y0, x1, y1).

    A row (column) is a bar when its *median* brightness stays dark in most sampled frames.
    The median ignores subtitle text printed inside a bar, which fooled FFmpeg's cropdetect.
    """
    if not frames:
        return {"box": (0.0, 0.0, 1.0, 1.0), "bars": False}
    gray = np.stack([f.mean(axis=2) for _, f in frames])  # (n, h, w)
    rows_dark = (np.median(gray, axis=2) < dark).mean(axis=0) >= share
    cols_dark = (np.median(gray, axis=1) < dark).mean(axis=0) >= share
    def span(dark_mask: np.ndarray) -> tuple[int, int]:
        lit = np.flatnonzero(~dark_mask)
        return (int(lit[0]), int(lit[-1]) + 1) if lit.size else (0, dark_mask.size)
    (y0, y1), (x0, x1) = span(rows_dark), span(cols_dark)
    h, w = gray.shape[1:]
    box = (x0 / w, y0 / h, x1 / w, y1 / h)
    bars = box[1] > 0.03 or box[0] > 0.03 or box[2] < 0.97 or box[3] < 0.97
    return {"box": tuple(round(v, 4) for v in box), "bars": bars,
            "active_aspect": round(((x1 - x0) / max(1, y1 - y0)), 3)}


def _norm(box: tuple, frame: np.ndarray) -> tuple:
    h, w = frame.shape[:2]
    return (box[0] / w, box[1] / h, box[2] / w, box[3] / h)


def _inside(point: tuple, box: tuple, margin: float = 0.01) -> bool:
    return box[0] - margin <= point[0] <= box[2] + margin and box[1] - margin <= point[1] <= box[3] + margin


def classify_text(samples: list[tuple[float, list[dict], np.ndarray]], active: tuple) -> dict:
    """Group OCR boxes into subtitles, watermarks, promo cards and incidental scene text."""
    subtitle_frames, subtitle_texts, inside_picture = 0, set(), 0
    corner: Counter = Counter()
    promo_frames = 0
    ax0, ay0, ax1, ay1 = active
    for _, rows, frame in samples:
        has_sub = False
        for row in rows:
            x0, y0, x1, y1 = _norm(row["box"], frame)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            rel_y = (cy - ay0) / max(1e-6, ay1 - ay0)
            rel_x = (cx - ax0) / max(1e-6, ax1 - ax0)
            if PROMO.search(row["text"]):
                promo_frames += 1
            near_corner = (rel_x < 0.22 or rel_x > 0.78) and (rel_y < 0.2 or rel_y > 0.85)
            if near_corner and (x1 - x0) < 0.3:
                corner[(round(cx, 1), round(cy, 1), row["text"].lower()[:12])] += 1
                continue
            if cy > ay0 + 0.6 * (ay1 - ay0) and 0.15 < rel_x < 0.85 or cy > ay1:
                has_sub = True
                subtitle_texts.add(row["text"].lower())
                inside_picture += _inside((cx, cy), active)
        subtitle_frames += has_sub
    n = max(1, len(samples))
    watermarks = [{"x": k[0], "y": k[1], "text": k[2], "frames": v} for k, v in corner.items() if v / n >= 0.4]
    return {"frames": len(samples), "subtitle_frames": subtitle_frames, "subtitle_share": round(subtitle_frames / n, 3),
            "distinct_subtitle_lines": len(subtitle_texts), "subtitle_boxes_inside_picture": inside_picture,
            "watermarks": watermarks, "promo_frames": promo_frames}


def mirrored(samples: list[tuple[float, list[dict], np.ndarray]], checks: int = 4) -> dict:
    """Text reads more confidently when flipped → the upload was mirrored (a common re-upload trick).

    OCR still "reads" mirrored text, but with clearly lower confidence than the flipped frame.
    """
    with_text = [s for s in samples if s[1]][:checks]
    if not with_text:
        return {"checked": 0, "mirrored": False}
    better = 0
    for _, rows, frame in with_text:
        original = max(r["score"] for r in rows)
        flipped = max((r["score"] for r in read_text(np.ascontiguousarray(frame[:, ::-1]), 0.3)), default=0.0)
        better += flipped > original + 0.08
    return {"checked": len(with_text), "flipped_reads_better": better,
            "mirrored": better >= 2 and better * 2 > len(with_text)}


def shot_rate(video: Path, threshold: float = 10.0) -> dict:
    info = probe(video)
    log = subprocess.run(["ffmpeg", "-v", "info", "-i", str(video), "-vf",
                          f"scale=320:-2,scdet=threshold={threshold}", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    cuts = len(re.findall(r"lavfi\.scd\.time", log)) or len(re.findall(r"scd\.score", log))
    duration = info["duration"] or 1
    return {"cuts": cuts, "average_shot_seconds": round(duration / (cuts + 1), 2)}


def narration_suspected(placement: dict | None, duration: float | None) -> bool:
    """Plenty of speech that does not line up with the movie's dialogue = someone talking over it."""
    if not placement or not duration:
        return False
    words = placement.get("clip_words") or 0
    share = placement.get("share") or 0.0
    return words / duration >= 1.6 and share < 0.12 and not placement.get("matched")


def screen(video: Path, *, placement: dict | None = None, every: float = 1.0) -> dict:
    info = probe(video)
    frames = sample_frames(video, every=every, limit=90)
    active = active_box(frames)
    samples = [(t, read_text(f), f) for t, f in frames]
    text = classify_text(samples, active["box"])
    flip = mirrored(samples)
    cutting = shot_rate(video)
    reasons, notes = [], []
    if text["subtitle_share"] >= 0.2 and text["distinct_subtitle_lines"] >= 3:
        if text["subtitle_boxes_inside_picture"] > 0.3 * text["subtitle_frames"]:
            reasons.append("burned-in subtitles inside the picture")
        else:
            notes.append("subtitles only in the black bars (removed by the crop)")
    for mark in text["watermarks"]:
        notes.append(f"watermark near ({mark['x']}, {mark['y']}): '{mark['text']}' — keep out of the crop")
    if text["promo_frames"] >= 2 or (text["promo_frames"] and cutting["average_shot_seconds"] < 1.3):
        reasons.append("trailer or promo material (promo cards)")
    elif cutting["average_shot_seconds"] < 0.9 and info["duration"] > 20:
        reasons.append("trailer-like cutting (average shot under 0.9 s)")
    if flip["mirrored"]:
        reasons.append("mirrored upload (on-screen text reads backwards)")
    if narration_suspected(placement, info["duration"]):
        reasons.append("speech does not match the movie's dialogue (narration or commentary)")
    if active["bars"]:
        notes.append(f"black bars: active picture {active['box']}")
    if (info.get("height") or 0) < 720:
        notes.append(f"low resolution ({info.get('height')}p)")
    return {"accept": not reasons, "reasons": reasons, "notes": notes, "active": active, "text": text,
            "mirror_check": flip, "cutting": cutting, "width": info.get("width"), "height": info.get("height"),
            "fps": info.get("fps"), "duration": info.get("duration")}


def write_report(path: Path, report: dict) -> None:
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def screen_candidates(placed: dict, youtube, workdir: Path, *, top: int = 8) -> list[dict]:
    """Download the best-ranked clips and screen them; one failure never stops the batch."""
    folder = Path(workdir) / "footage"
    reports = []
    for clip in placed["clips"][:top]:
        row = {"id": clip["id"], "title": clip["title"]}
        cache = folder / f"{clip['id']}.screen.json"
        if cache.exists():
            reports.append({**row, **json.loads(cache.read_text())})
            continue
        try:
            video = youtube.download(clip["id"], folder)
            if not video:
                raise RuntimeError("download produced no file")
            report = screen(video, placement=clip.get("placement"))
            report["path"] = str(video)
            write_report(cache, report)
        except Exception as exc:  # noqa: BLE001
            report = {"accept": False, "reasons": [f"could not screen: {str(exc)[:160]}"], "notes": []}
        reports.append({**row, **report})
    return reports

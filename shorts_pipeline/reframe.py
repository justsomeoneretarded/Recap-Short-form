"""Smart reframing from 16:9 footage to 1:1 or 9:16, decided per shot.

For each shot a few frames are sampled. Faces (OpenCV's bundled Haar cascade, or YuNet when
its model file is configured) and a motion/edge "attention" map locate what matters.

Modes:
- track: the crop window follows the subject with a smooth linear pan (or holds still);
- fit:   when the important content is wider than the crop (two people far apart, wide
         action), the whole picture is shown over a blurred, zoomed copy of itself.

Nothing is ever cropped out silently: a shot whose subjects cannot fit in the window falls
back to fit.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

SAMPLE_WIDTH = 480


def sample(video: Path, start: float, end: float, count: int = 6) -> list[np.ndarray]:
    from .media import probe
    info = probe(video)
    width, height = info["width"], info["height"]
    out_w = SAMPLE_WIDTH
    out_h = int(round(height * out_w / width / 2) * 2)
    frames = []
    for i in range(count):
        t = start + (end - start) * (i + 0.5) / count
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                              "-vf", f"scale={out_w}:{out_h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        if len(raw) == out_w * out_h * 3:
            frames.append(np.frombuffer(raw, dtype=np.uint8).reshape(out_h, out_w, 3))
    return frames


@lru_cache(maxsize=1)
def _detector():
    import cv2
    model = os.environ.get("SHORTS_YUNET_MODEL", "")
    if model and Path(model).exists():
        return ("yunet", cv2.FaceDetectorYN.create(model, "", (SAMPLE_WIDTH, 270), 0.7))
    if hasattr(cv2, "CascadeClassifier"):  # OpenCV 4.x ships the Haar cascades; 5.x does not
        cascade = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        return ("haar", cv2.CascadeClassifier(str(cascade)))
    return ("none", None)


def faces(frame: np.ndarray) -> list[tuple[float, float, float, float]]:
    """Face boxes as fractions (x0, y0, x1, y1)."""
    import cv2
    kind, detector = _detector()
    if kind == "none":
        return []  # no detector available: framing falls back to motion/edge attention
    h, w = frame.shape[:2]
    if kind == "yunet":
        detector.setInputSize((w, h))
        _, found = detector.detect(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        boxes = [(x, y, x + bw, y + bh) for x, y, bw, bh, *_ in (found if found is not None else [])]
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        found = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(int(h * 0.08),) * 2)
        boxes = [(x, y, x + bw, y + bh) for x, y, bw, bh in found]
    return [(x0 / w, y0 / h, x1 / w, y1 / h) for x0, y0, x1, y1 in boxes]


def attention(frames: list[np.ndarray]) -> np.ndarray:
    """Column-wise attention (motion + edges), normalised to sum 1."""
    gray = [f.mean(axis=2) for f in frames]
    edges = np.mean([np.abs(np.diff(g, axis=1, prepend=g[:, :1])) for g in gray], axis=0)
    motion = np.mean([np.abs(a - b) for a, b in zip(gray, gray[1:])], axis=0) if len(gray) > 1 else 0 * edges
    columns = (edges + 2 * motion).sum(axis=0)
    columns = np.convolve(columns, np.ones(15) / 15, mode="same")
    total = columns.sum()
    return columns / total if total > 0 else np.full(columns.shape, 1 / columns.size)


def window_fraction(source_aspect: float, output_aspect: float) -> float:
    """Width of the crop window as a fraction of the source width (1.0 = no horizontal crop)."""
    return min(1.0, output_aspect / source_aspect)


def plan_shot(frames: list[np.ndarray], active: tuple, output_aspect: float) -> dict:
    """Decide mode and crop centre path (fractions of the active picture width)."""
    x0a, y0a, x1a, y1a = active
    if not frames:
        return {"mode": "track", "x_start": 0.5, "x_end": 0.5, "reason": "no frames"}
    h, w = frames[0].shape[:2]
    active_aspect = ((x1a - x0a) * w) / max(1.0, (y1a - y0a) * h)
    win = window_fraction(active_aspect, output_aspect)
    if win >= 0.98:
        return {"mode": "track", "x_start": 0.5, "x_end": 0.5, "window": win, "reason": "no crop needed"}
    centres, spreads, found_faces = [], [], 0
    for frame in frames:
        boxes = [b for b in faces(frame) if x0a <= (b[0] + b[2]) / 2 <= x1a]
        rel = [((b[0] + b[2]) / 2 - x0a) / (x1a - x0a) for b in boxes]
        sizes = [(b[2] - b[0]) * (b[3] - b[1]) for b in boxes]
        if boxes:
            found_faces += 1
            big = max(range(len(boxes)), key=lambda i: sizes[i])
            important = [r for r, s in zip(rel, sizes) if s >= 0.35 * sizes[big]]
            centres.append(float(np.average(important, weights=[s for s in sizes if s >= 0.35 * sizes[big]])))
            span = max(((b[2] - x0a) / (x1a - x0a)) for b, s in zip(boxes, sizes) if s >= 0.35 * sizes[big]) - \
                min(((b[0] - x0a) / (x1a - x0a)) for b, s in zip(boxes, sizes) if s >= 0.35 * sizes[big])
            spreads.append(span)
    if found_faces >= max(2, len(frames) // 2):
        if max(spreads) > win * 0.95:
            return {"mode": "fit", "window": win, "reason": "important faces wider than the crop"}
        reason = "faces"
    else:
        cols = attention(frames)
        a, b = int(x0a * cols.size), int(x1a * cols.size)
        cols = cols[a:b] / max(1e-9, cols[a:b].sum())
        positions = np.linspace(0, 1, cols.size)
        centre = float((cols * positions).sum())
        spread = float(np.sqrt((cols * (positions - centre) ** 2).sum()))
        if spread > 0.30 and win < 0.6:
            return {"mode": "fit", "window": win, "reason": "wide action"}
        half = len(frames) // 2 or 1
        centres = [centre] * len(frames)
        if len(frames) >= 4:  # pan only if attention clearly moves between halves
            first, second = attention(frames[:half])[a:b], attention(frames[half:])[a:b]
            c1 = float((first / max(1e-9, first.sum()) * positions).sum())
            c2 = float((second / max(1e-9, second.sum()) * positions).sum())
            centres = [c1] * half + [c2] * (len(frames) - half)
        reason = "attention"
    half = max(1, len(centres) // 2)
    start, end = float(np.median(centres[:half])), float(np.median(centres[half:] or centres))
    lo, hi = win / 2, 1 - win / 2
    start, end = min(hi, max(lo, start)), min(hi, max(lo, end))
    if abs(end - start) < 0.04:
        start = end = (start + end) / 2
    # Never pan faster than a quarter of the frame per shot: fast pans read as mistakes.
    if abs(end - start) > 0.25:
        end = start + 0.25 * (1 if end > start else -1)
    return {"mode": "track", "x_start": round(start, 4), "x_end": round(end, 4), "window": round(win, 4),
            "reason": reason}


def filter_graph(plan: dict, src_w: int, src_h: int, active: tuple, out_w: int, out_h: int, duration: float,
                 label_in: str = "0:v", label_out: str = "v") -> str:
    """FFmpeg filter for one shot: active-area crop, then track window or fit-over-blur, at out_w×out_h."""
    ax, ay = int(active[0] * src_w) // 2 * 2, int(active[1] * src_h) // 2 * 2
    aw = int((active[2] - active[0]) * src_w) // 2 * 2
    ah = int((active[3] - active[1]) * src_h) // 2 * 2
    base = f"[{label_in}]crop={aw}:{ah}:{ax}:{ay},setsar=1"
    if plan["mode"] == "fit":
        return (f"{base},split=2[fgsrc][bgsrc];"
                f"[bgsrc]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},"
                f"boxblur=24:2,eq=brightness=-0.10:saturation=0.85[bg];"
                f"[fgsrc]scale={out_w}:-2:flags=lanczos[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[{label_out}]")
    out_aspect = out_w / out_h
    cw = min(aw, int(round(ah * out_aspect / 2)) * 2)
    ch = min(ah, int(round(cw / out_aspect / 2)) * 2)
    x_start, x_end = plan.get("x_start", 0.5), plan.get("x_end", 0.5)
    left0, left1 = (x_start - cw / aw / 2) * aw, (x_end - cw / aw / 2) * aw
    d = max(0.04, duration)
    x = f"max(0\\,min({aw - cw}\\,{left0:.2f}+({left1 - left0:.2f})*min(1\\,t/{d:.3f})))"
    return (f"{base},crop={cw}:{ch}:x='{x}':y={(ah - ch) // 2},"
            f"scale={out_w}:{out_h}:flags=lanczos,setsar=1[{label_out}]")


def native_size(plan: dict, src_w: int, src_h: int, active: tuple, out_w: int, out_h: int) -> tuple[int, int]:
    """Pixels the shot really has before upscaling: the crop window at source resolution (track mode).

    Interpolating at this size and enlarging afterwards costs far less than interpolating the
    upscaled frame (vertical from 1080p: 608×1080 instead of 1080×1920) and looks the same.
    """
    if plan["mode"] != "track":
        return out_w, out_h
    aw = int((active[2] - active[0]) * src_w) // 2 * 2
    ah = int((active[3] - active[1]) * src_h) // 2 * 2
    cw = min(aw, int(round(ah * out_w / out_h / 2)) * 2)
    ch = min(ah, int(round(cw * out_h / out_w / 2)) * 2)
    return (cw, ch) if cw < out_w else (out_w, out_h)

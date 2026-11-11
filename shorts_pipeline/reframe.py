"""Smart reframing from 16:9 footage to 1:1 or 9:16, decided per shot.

For each shot a few frames are sampled. Faces (OpenCV's bundled Haar cascade, or YuNet when
its model file is configured) and a motion/edge "attention" map locate what matters.

Modes:
- track: the crop window follows the subject with a smooth linear pan (or holds still);
- stack: two people too far apart for one crop: each gets a proper crop of their own — one on
         top of the other in 9:16, side by side in 1:1. No Short ever shows blurred side bars.
- fit:   (kept only for older plans; the planner no longer chooses it) when the content is wider than the crop (two people far apart, wide
         action), a wider window that holds all of it (square for 9:16, 4:3 for 1:1, or the whole
         picture if needed) is shown across the full width over a blurred copy of itself. A thin
         16:9 strip in the middle of a 9:16 frame looked cheap; the wider window keeps it large.

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
FIT_ASPECT_VERTICAL = 1.0      # a 9:16 Short shows a square window when it cannot track one subject
FIT_ASPECT_SQUARE = 4 / 3      # a 1:1 Short shows a 4:3 window
STACK_TILE_ASPECT = 1080 / 960  # 9:16 two-person shots: two 1080x960 crops stacked
SIDE_TILE_ASPECT = 540 / 1080   # 1:1 two-person shots: two 540x1080 crops side by side
MIN_PEOPLE_GAP = 0.3   # two face centres at least this far apart (share of the width) to be two people


def sample(video: Path, start: float, end: float, count: int = 6) -> list[np.ndarray]:
    from .media import probe
    info = probe(video)
    width, height = info["width"], info["height"]
    out_w = SAMPLE_WIDTH
    out_h = int(round(height * out_w / width / 2) * 2)
    # One decode of the shot (instead of one seek per frame), keeping `count` evenly spaced frames.
    span = max(0.05, end - start)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{span:.3f}", "-i", str(video),
                          "-vf", f"fps={count / span:.6f},scale={out_w}:{out_h}", "-frames:v", str(count),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    size = out_w * out_h * 3
    return [np.frombuffer(raw[i * size:(i + 1) * size], dtype=np.uint8).reshape(out_h, out_w, 3)
            for i in range(len(raw) // size)]


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


DARK_LUMA = 70.0   # mean brightness (0-255) under which a shot is lifted


def lift_for(frames: list[np.ndarray]) -> float | None:
    """Gamma lift for dark shots (a 0-255 mean of 30 gets ~1.5), None for normal ones."""
    if not frames:
        return None
    luma = float(np.mean([f.mean() for f in frames]))
    return round(min(1.6, 1.0 + (DARK_LUMA - luma) / 80.0), 2) if luma < DARK_LUMA else None


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
    centres, spreads, found_faces, people = [], [], 0, []
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
            people.append(sorted((r, s) for r, s in zip(rel, sizes) if s >= 0.35 * sizes[big]))
    if found_faces >= max(2, len(frames) // 2):
        if max(spreads) > win * 0.95:
            # Never blurred side bars: follow the clearly bigger face, else show both people in two crops
            # (9:16: one above the other; 1:1: side by side).
            dominant = [len(p) == 1 or p[-1][1] >= 2 * sorted(x[1] for x in p)[-2] if len(p) > 1 else True
                        for p in people]
            biggest = [max(p, key=lambda x: x[1])[0] for p in people]
            if sum(dominant) >= 0.7 * len(people):
                centre = float(np.median(biggest))
                centre = min(1 - win / 2, max(win / 2, centre))
                return {"mode": "track", "x_start": round(centre, 4), "x_end": round(centre, 4), "window": round(win, 4),
                        "reason": "follows the main face"}
            rows = output_aspect < 0.8
            if rows:  # 9:16: a split-screen of two squashed tiles reads badly on a phone; follow the bigger face
                centre = min(1 - win / 2, max(win / 2, float(np.median(biggest))))
                return {"mode": "track", "x_start": round(centre, 4), "x_end": round(centre, 4), "window": round(win, 4),
                        "reason": "two people far apart: follows the bigger face (no split-screen in 9:16)"}
            frac = window_fraction(active_aspect, STACK_TILE_ASPECT if rows else SIDE_TILE_ASPECT)
            clamp = lambda c: round(min(1 - frac / 2, max(frac / 2, c)), 4)  # noqa: E731
            pairs = [p for p in people if len(p) >= 2]
            left = float(np.median([p[0][0] for p in pairs])) if pairs else 0.5
            right = float(np.median([p[-1][0] for p in pairs])) if pairs else 0.5
            # Two crops only for two different people: seen together in most frames, and far enough apart
            # that the crops do not show the same face twice. Otherwise follow the biggest face.
            if len(pairs) < 0.6 * len(people) or right - left < MIN_PEOPLE_GAP:
                centre = min(1 - win / 2, max(win / 2, float(np.median(biggest))))
                return {"mode": "track", "x_start": round(centre, 4), "x_end": round(centre, 4), "window": round(win, 4),
                        "reason": "follows the main face (one person, or two too close for separate crops)"}
            return {"mode": "stack", "layout": "rows" if rows else "columns", "x_top": clamp(left),
                    "x_bottom": clamp(right), "stack_window": round(frac, 4), "window": round(win, 4),
                    "reason": "two people far apart: " + ("stacked" if rows else "side by side")}
        reason = "faces"
    else:
        cols = attention(frames)
        a, b = int(x0a * cols.size), int(x1a * cols.size)
        cols = cols[a:b] / max(1e-9, cols[a:b].sum())
        positions = np.linspace(0, 1, cols.size)
        centre = float((cols * positions).sum())
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
    if plan.get("lift"):  # dark footage: lift the shadows so it reads on a phone
        base += f",eq=gamma={plan['lift']:.2f}:contrast=1.04:saturation=1.05"
    if plan.get("deflicker"):  # strobing light: smooth the brightness swings
        base += ",deflicker=mode=pm:size=7"
    if plan["mode"] == "stack" and plan.get("layout") == "columns":  # 1:1: two people side by side
        tile_w = out_w // 2 // 2 * 2
        fw = min(aw, int(round(ah * tile_w / out_h / 2)) * 2)
        def left_c(x: float) -> int:
            return int(min(max(0.0, x * aw - fw / 2), aw - fw)) // 2 * 2
        return (f"{base},split=2[sleft][sright];"
                f"[sleft]crop={fw}:{ah}:{left_c(plan.get('x_top', 0.3))}:0,scale={tile_w}:{out_h}:flags=lanczos[tileleft];"
                f"[sright]crop={fw}:{ah}:{left_c(plan.get('x_bottom', 0.7))}:0,scale={out_w - tile_w}:{out_h}:flags=lanczos[tileright];"
                f"[tileleft][tileright]hstack=inputs=2,setsar=1[{label_out}]")
    if plan["mode"] == "stack":  # 9:16: one person on top, the other below; no blur
        tile_h = out_h // 2 // 2 * 2
        fw = min(aw, int(round(ah * out_w / tile_h / 2)) * 2)
        def left(x: float) -> int:
            return int(min(max(0.0, x * aw - fw / 2), aw - fw)) // 2 * 2
        return (f"{base},split=2[stop][sbot];"
                f"[stop]crop={fw}:{ah}:{left(plan.get('x_top', 0.3))}:0,scale={out_w}:{tile_h}:flags=lanczos[tiletop];"
                f"[sbot]crop={fw}:{ah}:{left(plan.get('x_bottom', 0.7))}:0,scale={out_w}:{out_h - tile_h}:flags=lanczos[tilebot];"
                f"[tiletop][tilebot]vstack=inputs=2,setsar=1[{label_out}]")
    if plan["mode"] == "fit":
        trim = float(plan.get("trim") or 0.0)
        if trim:  # cut off the edges where a channel logo sits
            tw, th = int(aw * (1 - 2 * trim)) // 2 * 2, int(ah * (1 - 2 * trim)) // 2 * 2
            base += f",crop={tw}:{th}:{(aw - tw) // 2}:{(ah - th) // 2}"
            aw, ah = tw, th
        frac = float(plan.get("fit_window") or 1.0)
        if frac < 0.999:  # the wider window around the action, not the whole frame
            fw = max(2, int(aw * frac) // 2 * 2)
            left = int(min(max(0.0, plan.get("x_center", 0.5) * aw - fw / 2), aw - fw)) // 2 * 2
            base += f",crop={fw}:{ah}:{left}:0"
        return (f"{base},split=2[fgsrc][bgsrc];"
                f"[bgsrc]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},"
                f"boxblur=24:2,eq=brightness=-0.10:saturation=0.85[bg];"
                f"[fgsrc]scale={out_w}:-2:flags=lanczos[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2{punch_in(plan, out_w, out_h, duration)},setsar=1[{label_out}]")
    out_aspect = out_w / out_h
    cw = min(aw, int(round(ah * out_aspect / 2)) * 2)
    ch = min(ah, int(round(cw / out_aspect / 2)) * 2)
    x_start, x_end = plan.get("x_start", 0.5), plan.get("x_end", 0.5)
    left0, left1 = (x_start - cw / aw / 2) * aw, (x_end - cw / aw / 2) * aw
    d = max(0.04, duration)
    x = f"max(0\\,min({aw - cw}\\,{left0:.2f}+({left1 - left0:.2f})*min(1\\,t/{d:.3f})))"
    return (f"{base},crop={cw}:{ch}:x='{x}':y={(ah - ch) // 2},"
            f"scale={out_w}:{out_h}:flags=lanczos{punch_in(plan, out_w, out_h, duration)},setsar=1[{label_out}]")


def punch_in(plan: dict, out_w: int, out_h: int, duration: float) -> str:
    """A slow push-in (to 1 + punch over the shot, eased out) for key moments; '' for every other shot."""
    zoom = float(plan.get("punch") or 0.0)
    if zoom <= 0:
        return ""
    d = max(0.04, duration)
    grow = f"(1+{zoom:.3f}*(1-pow(1-min(1\\,t/{d:.3f})\\,2)))"  # ease-out: fast start, gentle landing
    return (f",scale=w='trunc({out_w}*{grow}/2)*2':h='trunc({out_h}*{grow}/2)*2':eval=frame:flags=bicubic,"
            f"crop={out_w}:{out_h}")


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

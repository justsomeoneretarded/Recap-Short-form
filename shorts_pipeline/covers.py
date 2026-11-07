"""Shorts covers: the best frame of the story, framed for 1:1 and 9:16, with a short hook.

Candidate frames come from the middle of every edited shot (and their peaks). Each frame is
scored for sharpness, faces (bigger is better), contrast/colour and the absence of on-screen
text (subtitles, logos), then the best distinct frames become three designs:

1. hook  — best face frame, graded, 2–4 word hook in big bold type;
2. punch — tighter crop on the face with the hook;
3. clean — best overall frame, graded, no text.

When the rendered shots are available (the finish machine has them), frames come from those
clean shots: no burned captions in the cover, and each shape uses its own framing (square
cover from the square shot, vertical from the vertical shot). Shots shown as fit-over-blur
are avoided. Frames are grabbed a few at a time.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

FONTS = Path(__file__).parent / "assets" / "fonts"
SIZES = {"square": (1080, 1080), "vertical": (1080, 1920)}
STOP = {"the", "a", "an", "and", "of", "to", "is", "was", "in", "on", "now", "he", "she", "they", "his", "her"}


def grab(video: Path, at: float) -> Image.Image | None:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, at):.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    if not raw:
        return None
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert("RGB")


def sharpness(gray: np.ndarray) -> float:
    lap = gray[1:-1, 1:-1] * 4 - gray[:-2, 1:-1] - gray[2:, 1:-1] - gray[1:-1, :-2] - gray[1:-1, 2:]
    return float(lap.var())


def score_frame(image: Image.Image, *, text_reader=None, face_finder=None) -> dict:
    small = image.resize((480, int(480 * image.height / image.width)))
    arr = np.asarray(small).astype(np.float32)
    gray = arr.mean(axis=2)
    sharp = min(1.0, sharpness(gray) / 400.0)
    contrast = min(1.0, gray.std() / 64.0)
    colour = min(1.0, float(np.abs(arr[:, :, 0] - arr[:, :, 1]).mean() + np.abs(arr[:, :, 1] - arr[:, :, 2]).mean()) / 60.0)
    exposure = 1.0 - min(1.0, abs(gray.mean() - 110) / 110)
    faces = face_finder(np.asarray(small)) if face_finder else []
    face_area = max(((b[2] - b[0]) * (b[3] - b[1]) for b in faces), default=0.0)
    texts = text_reader(np.asarray(small)) if text_reader else []
    total = 0.3 * sharp + 0.15 * contrast + 0.1 * colour + 0.15 * exposure + 0.3 * min(1.0, face_area / 0.06)
    total -= 0.25 * min(1.0, len(texts) / 2)
    return {"score": round(total, 4), "sharp": round(sharp, 3), "faces": faces, "face_area": round(face_area, 4),
            "text_boxes": len(texts)}


def _crop(image: Image.Image, size: tuple[int, int], centre_x: float = 0.5, centre_y: float = 0.45,
          zoom: float = 1.0) -> Image.Image:
    out_w, out_h = size
    aspect = out_w / out_h
    w, h = image.size
    crop_h = min(h, w / aspect) / zoom
    crop_w = crop_h * aspect
    left = min(max(0, centre_x * w - crop_w / 2), w - crop_w)
    top = min(max(0, centre_y * h - crop_h / 2), h - crop_h)
    return image.crop((int(left), int(top), int(left + crop_w), int(top + crop_h))).resize(size, Image.LANCZOS)


def _grade(image: Image.Image) -> Image.Image:
    image = ImageEnhance.Contrast(image).enhance(1.18)
    image = ImageEnhance.Color(image).enhance(1.15)
    image = ImageEnhance.Sharpness(image).enhance(1.4)
    w, h = image.size
    yy, xx = np.mgrid[0:h, 0:w]
    vignette = 1 - 0.45 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2
    arr = np.asarray(image).astype(np.float32) * np.clip(vignette, 0.55, 1)[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def hook_words(title: str, limit: int = 4) -> list[str]:
    """'He Was Hired to Kill. Now He's the Prey.' → strongest short phrase (last clause, ≤4 words)."""
    clauses = [c.strip(" .!?") for c in title.replace("—", ".").split(".") if c.strip(" .!?")]
    clause = clauses[-1] if clauses else title
    words = clause.split()
    if len(words) > limit:
        meaningful = [w for w in words if w.lower().strip("'’") not in STOP]
        words = (meaningful or words)[-limit:]
    return [w.upper() for w in words]


def _text(image: Image.Image, words: list[str], *, at: float = 0.12) -> Image.Image:
    draw = ImageDraw.Draw(image)
    w, h = image.size
    lines = [" ".join(words[:2]), " ".join(words[2:])] if len(" ".join(words)) > 14 else [" ".join(words)]
    lines = [line for line in lines if line]
    size = int(w * (0.16 if len(lines) > 1 else 0.14))
    font = ImageFont.truetype(str(FONTS / "Anton-Regular.ttf"), size)
    while max(draw.textlength(line, font=font) for line in lines) > w * 0.9 and size > 40:
        size -= 6
        font = ImageFont.truetype(str(FONTS / "Anton-Regular.ttf"), size)
    block = int(size * 1.08) * len(lines)
    # Keep the whole block inside the frame and clear of the platform's top/bottom UI (8 % / 14 %).
    y = int(min(max(h * at, h * 0.08), h * 0.86 - block))
    for i, line in enumerate(lines):
        width = draw.textlength(line, font=font)
        fill = (255, 214, 0) if i == len(lines) - 1 and len(lines) > 1 else (255, 255, 255)
        draw.text(((w - width) / 2, y), line, font=font, fill=fill, stroke_width=max(4, size // 14),
                  stroke_fill=(0, 0, 0))
        y += int(size * 1.08)
    return image


def _grab_all(jobs: list[tuple[Path, float]]) -> list[Image.Image | None]:
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:  # each grab is a separate FFmpeg process
        return list(pool.map(lambda job: grab(*job), jobs))


def _part(parts: Path | None, aspect: str, index: int) -> Path | None:
    path = Path(parts) / f"{aspect}-shot-{index:04d}.mkv" if parts else None
    return path if path and path.exists() else None


def make_covers(video: Path, edl: dict, title: str, outdir: Path, *, aspects=("square", "vertical"),
                text_reader=None, face_finder=None, max_candidates: int = 24, parts: Path | None = None,
                plans: dict | None = None, chooser=None, words: list[str] | None = None) -> dict:
    """Covers from real frames of the Short. `chooser(images, title)` (Gemini, optional) picks the
    strongest of the best-scoring frames and the cover words; otherwise the frame scores decide."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    main = "vertical" if "vertical" in aspects else aspects[0]
    shots = list(enumerate(edl["shots"]))
    step = max(1, len(shots) // max_candidates)
    picked = shots[::step][:max_candidates]

    def source(index: int, shot: dict, aspect: str) -> tuple[Path, float]:
        part = _part(parts, aspect, index)  # clean shot (no captions) in this shape's own framing
        return (part, shot["duration"] / 2) if part else (Path(video), shot["timeline_start"] + shot["duration"] / 2)

    frames = _grab_all([source(i, shot, main) for i, shot in picked])
    candidates = []
    for (index, shot), frame in zip(picked, frames):
        if frame is None:
            continue
        row = {"time": round(shot["timeline_start"] + shot["duration"] / 2, 2), "index": index, "image": frame,
               **score_frame(frame, text_reader=text_reader, face_finder=face_finder)}
        if ((plans or {}).get(str(index)) or {}).get(main, {}).get("mode") == "fit":
            row["score"] = round(row["score"] - 0.2, 4)  # blurred side bars look cheap on a cover
        candidates.append(row)
    if not candidates:
        raise RuntimeError("No frames could be read for covers")
    candidates.sort(key=lambda c: c["score"], reverse=True)
    best_face = next((c for c in candidates if c["faces"]), candidates[0])
    best_other = next((c for c in candidates if abs(c["time"] - best_face["time"]) > 3), candidates[0])
    words = [w for w in (words or []) if w][:4] or hook_words(title)
    picked_by = "frame scores"
    if chooser is not None and len(candidates) > 1:
        shortlist = candidates[:10]
        try:
            pick = chooser([c["image"] for c in shortlist], title)
            best_face, best_other = shortlist[pick["best"]], shortlist[pick["second"]]
            words = pick.get("words") or words
            picked_by = "Gemini"
        except Exception as exc:  # noqa: BLE001 - the frame scores still give a good cover
            picked_by = f"frame scores (Gemini: {str(exc)[:80]})"
    outputs = {}
    for aspect in aspects:
        size = SIZES[aspect]
        face_image, other_image = best_face["image"], best_other["image"]
        face_boxes = best_face["faces"]
        if aspect != main and parts:
            own = _grab_all([source(best_face["index"], edl["shots"][best_face["index"]], aspect),
                             source(best_other["index"], edl["shots"][best_other["index"]], aspect)])
            if own[0] is not None and _part(parts, aspect, best_face["index"]):
                face_image = own[0]
                small = np.asarray(face_image.resize((480, int(480 * face_image.height / face_image.width))))
                face_boxes = face_finder(small) if face_finder else []
            if own[1] is not None and _part(parts, aspect, best_other["index"]):
                other_image = own[1]
        face = max(face_boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])) if face_boxes else None
        cx = (face[0] + face[2]) / 2 if face else 0.5
        cy = (face[1] + face[3]) / 2 if face else 0.45
        designs = {
            "hook": _text(_grade(_crop(face_image, size, cx, cy)), words),
            "punch": _text(_grade(_crop(face_image, size, cx, cy, zoom=1.35 if face else 1.15)), words, at=0.70),
            "clean": _grade(_crop(other_image, size)),
        }
        for name, image in designs.items():
            path = outdir / f"cover-{aspect}-{name}.jpg"
            image.save(path, quality=92)
            outputs[f"{aspect}-{name}"] = str(path)
    return {"covers": outputs, "chosen_times": [best_face["time"], best_other["time"]], "hook": " ".join(words),
            "picked_by": picked_by,
            "from_clean_shots": bool(parts and _part(parts, main, best_face["index"])),
            "candidates": [{k: v for k, v in c.items() if k != "image"} for c in candidates[:8]]}


def contact_sheet(video: Path, duration: float, target: Path, columns: int = 6, rows: int = 2) -> Path:
    tiles = []
    count = columns * rows
    for i, frame in enumerate(_grab_all([(Path(video), duration * (i + 0.5) / count) for i in range(count)])):
        if frame is not None:
            frame.thumbnail((240, 240))
            tiles.append((i, frame))
    sheet = Image.new("RGB", (columns * 250, rows * 260), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for i, frame in tiles:
        x, y = (i % columns) * 250 + 5, (i // columns) * 260 + 5
        sheet.paste(frame, (x, y))
        draw.text((x, y + frame.height + 2), f"{duration * (i + 0.5) / (columns * rows):.1f}s", fill="white")
    sheet.save(target, quality=88)
    return target

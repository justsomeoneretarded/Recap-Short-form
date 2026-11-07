"""Render a Short from its edit decision list, in square and/or vertical, at true 60 fps.

Per shot: cut → smart reframe (reframe.py) → speed → 60 fps (RIFE when available, else
motion-blended frame interpolation; never frame duplication) → source sound (ducked under
narration, full for movie lines). Then: join shots, add the narrator, master to −14 LUFS /
−1 dBTP, burn the captions, encode H.264 60 fps.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .media import probe
from .reframe import filter_graph, native_size, plan_shot, sample

FPS = 60
SIZES = {"square": (1080, 1080), "vertical": (1080, 1920)}
DUCK_GAIN = 0.16


def _run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed: {' '.join(args[:6])}… {result.stderr[-600:]}")


def rife_available() -> bool:
    binary = os.environ.get("SHORTS_RIFE_BIN", "")
    return bool(binary and Path(binary).exists() and os.environ.get("SHORTS_RIFE_MODEL"))


def _gray(path: Path, width: int = 96):
    import numpy as np
    from PIL import Image
    with Image.open(path) as image:
        image = image.convert("L")
        image = image.resize((width, max(2, round(width * image.height / image.width))))
        return np.asarray(image, dtype=np.float32)


def rife_frames_ok(src: Path, dst: Path, samples: int = 16) -> tuple[bool, str]:
    """Do RIFE's new frames look like the real frames around them?

    A real in-between frame differs from its nearest source frames about as much as those differ
    from each other. A corrupted one (the horizontal streaks seen in run 15) differs from both by
    far more. Any such frame rejects the whole shot.
    """
    sources = sorted(src.glob("*.png"))
    outputs = sorted(dst.glob("*.png"))
    if len(sources) < 2 or len(outputs) < len(sources):
        return False, f"RIFE wrote {len(outputs)} frames for {len(sources)} inputs"
    step = max(1, len(outputs) // samples)
    for k in range(0, len(outputs), step):
        position = k * (len(sources) - 1) / max(1, len(outputs) - 1)
        a, b = sources[int(position)], sources[min(len(sources) - 1, int(position) + 1)]
        ga, gb, go = _gray(a), _gray(b), _gray(outputs[k])
        if go.shape != ga.shape:
            return False, f"frame {k} has the wrong size"
        between = float(abs(ga - gb).mean())
        nearest = min(float(abs(go - ga).mean()), float(abs(go - gb).mean()))
        if nearest > 2.5 * between + 12:
            return False, f"frame {k} does not match its neighbours ({nearest:.0f} vs {between:.0f})"
        # Structure, not brightness: in a dark scene garbage is close in brightness but not in shape.
        likeness = max(_correlation(go, ga), _correlation(go, gb))
        if likeness < min(_correlation(ga, gb), 0.9) - 0.25:
            return False, f"frame {k} has a different picture structure (likeness {likeness:.2f})"
        if _streakiness(go) > 2.0 * max(_streakiness(ga), _streakiness(gb), 1.0):
            return False, f"frame {k} is smeared into horizontal streaks"
    return True, "ok"


def _correlation(a, b) -> float:
    import numpy as np
    a, b = a - a.mean(), b - b.mean()
    scale = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / scale) if scale > 1e-6 else 1.0


def _streakiness(gray) -> float:
    """Vertical over horizontal detail: about 1 for real pictures, far higher for row-smeared frames."""
    import numpy as np
    horizontal = float(np.abs(np.diff(gray, axis=1)).mean())
    vertical = float(np.abs(np.diff(gray, axis=0)).mean())
    return vertical / max(0.5, horizontal)


def _rife(frames: Path, audio: Path, target: Path, frames_out: int, size: tuple[int, int],
          real_size: tuple[int, int] | None = None) -> None:
    """Interpolate one shot's frames with rife-ncnn-vulkan on the CPU, check them, then scale and encode.

    PNG in and out: the JPEG round trip used for speed produced streaked, corrupted frames.
    Every result is checked against the real frames; a bad result raises, and the caller
    renders the shot with motion blending instead.
    """
    # 2 processing threads, as in the Phase 0 test: more parallel CPU workers produced corrupted frames.
    threads = os.environ.get("SHORTS_RIFE_THREADS", "1:2:2")
    if real_size is None:
        from PIL import Image
        with Image.open(next(iter(sorted(frames.glob("*.png"))))) as first:
            real_size = first.size
    real_w, real_h = real_size  # frames arrive padded to a multiple of 32; the padding is cut off below
    dst = frames.parent / "out"
    dst.mkdir(exist_ok=True)
    _run([os.environ["SHORTS_RIFE_BIN"], "-i", str(frames), "-o", str(dst), "-m", os.environ["SHORTS_RIFE_MODEL"],
          "-n", str(frames_out), "-g", os.environ.get("SHORTS_RIFE_GPU", "-1"), "-j", threads, "-f", "png"])
    ok, why = rife_frames_ok(frames, dst)
    if not ok:
        raise RuntimeError(f"RIFE output rejected: {why}")
    _run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(dst / "%08d.png"), "-i", str(audio),
          "-map", "0:v", "-map", "1:a",
          "-vf", f"crop={real_w}:{real_h}:0:0,scale={size[0]}:{size[1]}:flags=lanczos,format=yuv420p",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-c:a", "pcm_s16le", "-shortest", str(target)])


def motion(source: Path, start: float, span: float) -> float:
    """Average frame-to-frame change (0–255) of a shot at low resolution. Under ~3: calm shot."""
    log = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{start:.3f}", "-t", f"{min(span, 4):.3f}", "-i", str(source),
                          "-vf", "scale=160:-2,format=gray,tblend=all_mode=difference,signalstats,"
                          "metadata=print:key=lavfi.signalstats.YAVG", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    values = [float(v) for v in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", log)]
    return round(sum(values) / len(values), 2) if values else 99.0


CALM_MOTION = float(os.environ.get("SHORTS_CALM_MOTION", "1.5"))  # below this a shot is near-still


def render_shot(shot: dict, plan: dict, active: tuple, size: tuple[int, int], target: Path, *,
                interpolation: str = "auto", use_rife: bool | None = None) -> dict:
    """One shot, with fallbacks: RIFE → motion blending → plain 60 fps (never a missing shot)."""
    tries = (["rife"] if (use_rife if use_rife is not None else
                          interpolation == "rife" or (interpolation == "auto" and rife_available())) else []) + \
        ["blend", "plain"]
    errors = []
    for how in tries:
        try:
            row = _render_shot(shot, plan, active, size, target, how)
            if errors:
                row["fallback"] = "; ".join(errors)[:300]
            return row
        except Exception as exc:  # noqa: BLE001 - try the next, simpler method
            errors.append(f"{how} failed: {str(exc)[:120]}")
            target.unlink(missing_ok=True)
    raise RuntimeError(f"Shot could not be rendered: {errors}")


def _render_shot(shot: dict, plan: dict, active: tuple, size: tuple[int, int], target: Path, how: str) -> dict:
    out_w, out_h = size
    info = probe(Path(shot["source"]))
    span = shot["end"] - shot["start"]
    use_rife = how == "rife"
    work_w, work_h = native_size(plan, info["width"], info["height"], active, out_w, out_h) if use_rife else size
    graph = filter_graph(plan, info["width"], info["height"], active, work_w, work_h, span, "0:v", "framed")
    timing = f"[framed]setpts=(PTS-STARTPTS)/{shot['speed']:.6f}"
    if use_rife:  # padded to a multiple of 32 (RIFE's working grid); cropped back after interpolation
        timing += f",fps={info.get('fps') or 24:.3f},pad=ceil(iw/32)*32:ceil(ih/32)*32:0:0,format=yuv420p[v]"
    elif how == "blend":
        # Motion-blended interpolation: every output frame is new (no duplicated frames).
        timing += f",framerate=fps={FPS}:interp_start=0:interp_end=255:scene=8,format=yuv420p[v]"
    else:  # last resort: plain conversion to 60 fps
        timing += f",fps={FPS},format=yuv420p[v]"
    gain = 1.0 if shot["audio"] == "full" else DUCK_GAIN
    audio = (f"[0:a]atrim=0:{span:.4f},asetpts=PTS-STARTPTS,atempo={shot['speed']:.4f},volume={gain},"
             f"aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{shot['duration']:.4f}[a]")
    if not info.get("has_audio"):
        audio = f"anullsrc=r=48000:cl=stereo,atrim=0:{shot['duration']:.4f}[a]"
    cut = ["ffmpeg", "-y", "-v", "error", "-ss", f"{shot['start']:.4f}", "-t", f"{span:.4f}", "-i", shot["source"],
           "-filter_complex", f"{graph};{timing};{audio}"]
    if use_rife:
        with tempfile.TemporaryDirectory(dir=target.parent) as temp:
            frames, sound = Path(temp) / "in", Path(temp) / "sound.wav"
            frames.mkdir()
            _run(cut + ["-map", "[v]", "-t", f"{shot['duration']:.4f}", str(frames / "%06d.png"),
                        "-map", "[a]", "-t", f"{shot['duration']:.4f}", "-c:a", "pcm_s16le", str(sound)])
            _rife(frames, sound, target, max(2, round(shot["duration"] * FPS)), size, real_size=(work_w, work_h))
    else:
        _run(cut + ["-map", "[v]", "-map", "[a]", "-t", f"{shot['duration']:.4f}", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "14", "-c:a", "pcm_s16le", str(target)])
    return {"interpolation": how, "mode": plan["mode"],
            "work_size": [work_w, work_h]}


def _concat(parts: list[Path], target: Path) -> None:
    manifest = target.with_suffix(".txt")
    manifest.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))  # parts may live in another folder
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(manifest),
          "-c:v", "copy", "-c:a", "pcm_s16le", str(target)])


def _narration_mix(edit_video: Path, voiceover: dict, target: Path) -> None:
    narration = [b for b in voiceover["beats"] if b["kind"] == "narration"]
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(edit_video)]
    chains = []
    for i, beat in enumerate(narration, 1):
        args += ["-i", beat["audio_path"]]
        delay = round(beat["timeline_start"] * 1000)
        chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay}|{delay}[n{i}]")
    inputs = "[0:a]" + "".join(f"[n{i}]" for i in range(1, len(narration) + 1))
    chains.append(f"{inputs}amix=inputs={len(narration) + 1}:duration=first:normalize=0[a]")
    _run(args + ["-filter_complex", ";".join(chains), "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                 "-c:a", "pcm_s16le", str(target)])


def _loudness(path: Path) -> dict:
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af",
                          "loudnorm=I=-14:TP=-1:LRA=9:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    blocks = re.findall(r'\{\s*"input_i".*?\}', log, re.S)
    if not blocks:
        raise RuntimeError("Could not measure loudness")
    return json.loads(blocks[-1])


def _escape(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def finish(mixed: Path, captions: Path | None, target: Path) -> dict:
    m = _loudness(mixed)
    af = (f"loudnorm=I=-14:TP=-1:LRA=9:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
          "linear=true,aresample=48000")
    vf = f"ass=filename='{_escape(captions)}'," if captions else ""
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(mixed), "-vf", f"{vf}fps={FPS},format=yuv420p", "-af", af,
          "-c:v", "libx264", "-preset", os.environ.get("SHORTS_X264_PRESET", "medium"), "-crf", "17",
          "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "256k", str(target)])
    final = _loudness(target)
    return {"integrated_lufs": float(final["input_i"]), "true_peak_db": float(final["input_tp"])}


def duplicate_frame_ratio(video: Path) -> float:
    """Share of near-identical adjacent frames (fake 60 fps shows ~0.6)."""
    # One decode (the frame count comes from the file header); small frames are enough to see copies.
    log = subprocess.run(["ffmpeg", "-i", str(video), "-an", "-vf", "scale=320:-2,mpdecimate", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    total = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=nb_frames", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True).stdout.strip().split(",")[0] or 0)
    kept = re.findall(r"frame=\s*(\d+)", log)
    return round(max(0.0, 1 - int(kept[-1]) / total), 3) if total and kept else 0.0


def plan_shots(edl: dict, screening: dict[str, dict], aspects=("square", "vertical")) -> dict:
    """Framing plan and motion per shot, computed once (also shipped to parallel render machines)."""
    plans = {}
    for i, shot in enumerate(edl["shots"]):
        active = tuple((screening.get(shot["clip_id"]) or {}).get("active", {}).get("box") or (0, 0, 1, 1))
        frames = sample(Path(shot["source"]), shot["start"], max(shot["start"] + 0.2, shot["end"]), 5)
        entry = {"active": active, "motion": motion(Path(shot["source"]), shot["start"], shot["end"] - shot["start"])}
        logo = bool(((screening.get(shot["clip_id"]) or {}).get("text") or {}).get("watermarks"))
        for aspect in aspects:
            size = SIZES[aspect]
            entry[aspect] = plan_shot(frames, active, size[0] / size[1])
            if logo and entry[aspect]["mode"] == "fit":
                entry[aspect]["trim"] = 0.08  # corner logo: fit shots lose 8 % at every edge
        plans[str(i)] = entry
    return plans


def render_parts(edl: dict, plans: dict, aspect: str, indexes: list[int], folder: Path, *,
                 interpolation: str = "auto", budget: float | None = None) -> list[dict]:
    """Render some shots of one aspect. RIFE only where it shows (moving shots) and while time allows."""
    import time
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    budget = budget if budget is not None else float(os.environ.get("SHORTS_RIFE_BUDGET", "7200"))
    started = time.monotonic()
    rife_ok = interpolation == "rife" or (interpolation == "auto" and rife_available())
    rows = []
    for i in indexes:
        shot, plan = edl["shots"][i], plans[str(i)]
        moving = plan.get("motion", 99.0) >= CALM_MOTION
        in_time = time.monotonic() - started < budget
        use_rife = rife_ok and moving and in_time
        part = folder / f"{aspect}-shot-{i:04d}.mkv"
        row = render_shot(shot, plan[aspect], tuple(plan["active"]), SIZES[aspect], part, use_rife=use_rife)
        row.update(index=i, motion=plan.get("motion"),
                   why="rife" if use_rife else "calm shot" if rife_ok and not moving else
                   "time budget" if rife_ok and not in_time else "rife unavailable")
        rows.append(row)
    return rows


def streaked_shots(video: Path, edl: dict) -> list[int]:
    """Shots whose middle frame in the finished video is smeared into horizontal streaks."""
    import numpy as np
    bad = []
    for i, shot in enumerate(edl["shots"]):
        t = shot["timeline_start"] + shot["duration"] / 2
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                              "-vf", "scale=160:-2,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        if not raw:
            continue
        info_w = 160
        frame = np.frombuffer(raw, np.uint8).astype(np.float32)
        frame = frame[: frame.size // info_w * info_w].reshape(-1, info_w)
        if _streakiness(frame) > 4.0:
            bad.append(i)
    return bad


def finish_aspect(edl: dict, voiceover: dict, aspect: str, parts_folder: Path, captions: Path | None,
                  outdir: Path, rows: list[dict]) -> dict:
    """Join every shot of one aspect, add the narrator, master, burn captions → final-<aspect>.mp4."""
    parts = [Path(parts_folder) / f"{aspect}-shot-{i:04d}.mkv" for i in range(len(edl["shots"]))]
    missing = [p.name for p in parts if not p.exists()]
    if missing:
        raise RuntimeError(f"Missing rendered shots for {aspect}: {missing[:5]}")
    work = Path(tempfile.mkdtemp(prefix=f"finish-{aspect}-", dir=outdir))
    joined, mixed = work / "joined.mkv", work / "mixed.mkv"
    _concat(parts, joined)
    _narration_mix(joined, voiceover, mixed)
    final = Path(outdir) / f"final-{aspect}.mp4"
    audio = finish(mixed, captions, final)
    info = probe(final)
    shutil.rmtree(work, ignore_errors=True)
    reasons = {}
    for row in rows:
        reasons[row["why"]] = reasons.get(row["why"], 0) + 1
    return {"path": str(final), "duration": info["duration"], "width": info["width"], "height": info["height"],
            "fps": info["fps"], **audio, "duplicate_frames": duplicate_frame_ratio(final),
            "streaked_shots": streaked_shots(final, edl),
            "modes": {m: sum(1 for x in rows if x["mode"] == m) for m in ("track", "fit")},
            "interpolation": sorted({x["interpolation"] for x in rows}), "interpolation_reasons": reasons,
            "shot_rows": [{"index": x.get("index"), "fallback": x["fallback"]} for x in rows if x.get("fallback")]}


def render_short(edl: dict, voiceover: dict, screening: dict[str, dict], captions: dict[str, Path], outdir: Path,
                 *, aspects: tuple[str, ...] = ("square", "vertical"), interpolation: str = "auto") -> dict:
    """Single-machine render (local use and small jobs); the workflow splits the same steps across machines."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plans = plan_shots(edl, screening, aspects)
    reports = {}
    parts = outdir / "parts"
    for aspect in aspects:
        rows = render_parts(edl, plans, aspect, list(range(len(edl["shots"]))), parts, interpolation=interpolation)
        reports[aspect] = finish_aspect(edl, voiceover, aspect, parts, captions.get(aspect), outdir, rows)
    shutil.rmtree(parts, ignore_errors=True)
    (outdir / "render.json").write_text(json.dumps({"edl": edl, "outputs": reports, "plans": plans},
                                                   indent=1, default=str))
    return reports

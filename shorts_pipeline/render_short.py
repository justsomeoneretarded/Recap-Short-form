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
from .reframe import filter_graph, plan_shot, sample

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


def _rife(video: Path, target: Path, frames_out: int) -> None:
    """Interpolate a short shot with rife-ncnn-vulkan (CPU), keeping its audio."""
    with tempfile.TemporaryDirectory(dir=target.parent) as temp:
        src, dst = Path(temp) / "in", Path(temp) / "out"
        src.mkdir()
        dst.mkdir()
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(video), str(src / "%06d.png")])
        _run([os.environ["SHORTS_RIFE_BIN"], "-i", str(src), "-o", str(dst), "-m", os.environ["SHORTS_RIFE_MODEL"],
              "-n", str(frames_out), "-g", os.environ.get("SHORTS_RIFE_GPU", "-1"), "-j", "1:2:2"])
        _run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(dst / "%08d.png"), "-i", str(video),
              "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
              "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", str(target)])


def render_shot(shot: dict, plan: dict, active: tuple, size: tuple[int, int], target: Path, *,
                interpolation: str = "auto") -> dict:
    out_w, out_h = size
    info = probe(Path(shot["source"]))
    span = shot["end"] - shot["start"]
    graph = filter_graph(plan, info["width"], info["height"], active, out_w, out_h, span, "0:v", "framed")
    use_rife = interpolation == "rife" or (interpolation == "auto" and rife_available())
    timing = f"[framed]setpts=(PTS-STARTPTS)/{shot['speed']:.6f}"
    if use_rife:
        timing += f",fps={info.get('fps') or 24:.3f},format=yuv420p[v]"
    else:
        # Motion-blended interpolation: every output frame is new (no duplicated frames).
        timing += f",framerate=fps={FPS}:interp_start=0:interp_end=255:scene=8,format=yuv420p[v]"
    gain = 1.0 if shot["audio"] == "full" else DUCK_GAIN
    audio = (f"[0:a]atrim=0:{span:.4f},asetpts=PTS-STARTPTS,atempo={shot['speed']:.4f},volume={gain},"
             f"aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{shot['duration']:.4f}[a]")
    if not info.get("has_audio"):
        audio = f"anullsrc=r=48000:cl=stereo,atrim=0:{shot['duration']:.4f}[a]"
    first = target.with_suffix(".base.mkv") if use_rife else target
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{shot['start']:.4f}", "-t", f"{span:.4f}", "-i", shot["source"],
          "-filter_complex", f"{graph};{timing};{audio}", "-map", "[v]", "-map", "[a]",
          "-t", f"{shot['duration']:.4f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
          "-c:a", "pcm_s16le", str(first)])
    if use_rife:
        _rife(first, target, max(2, round(shot["duration"] * FPS)))
        first.unlink(missing_ok=True)
    return {"interpolation": "rife" if use_rife else "blend", "mode": plan["mode"]}


def _concat(parts: list[Path], target: Path) -> None:
    manifest = target.with_suffix(".txt")
    manifest.write_text("".join(f"file '{p.name}'\n" for p in parts))
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
          "-c:v", "libx264", "-preset", os.environ.get("SHORTS_X264_PRESET", "slow"), "-crf", "17",
          "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "256k", str(target)])
    final = _loudness(target)
    return {"integrated_lufs": float(final["input_i"]), "true_peak_db": float(final["input_tp"])}


def duplicate_frame_ratio(video: Path) -> float:
    """Share of near-identical adjacent frames (fake 60 fps shows ~0.6)."""
    total = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                "stream=nb_read_frames", "-of", "csv=p=0", str(video)],
                               capture_output=True, text=True).stdout.strip() or 0)
    log = subprocess.run(["ffmpeg", "-i", str(video), "-vf", "mpdecimate", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    kept = re.findall(r"frame=\s*(\d+)", log)
    return round(1 - int(kept[-1]) / total, 3) if total and kept else 0.0


def render_short(edl: dict, voiceover: dict, screening: dict[str, dict], captions: dict[str, Path], outdir: Path,
                 *, aspects: tuple[str, ...] = ("square", "vertical"), interpolation: str = "auto") -> dict:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plans: dict[int, dict] = {}
    reports = {}
    for aspect in aspects:
        size = SIZES[aspect]
        work = Path(tempfile.mkdtemp(prefix=f"render-{aspect}-", dir=outdir))
        parts, modes = [], []
        for i, shot in enumerate(edl["shots"]):
            active = tuple((screening.get(shot["clip_id"]) or {}).get("active", {}).get("box") or (0, 0, 1, 1))
            key = (i, aspect)
            if key not in plans:
                frames = sample(Path(shot["source"]), shot["start"], max(shot["start"] + 0.2, shot["end"]), 5)
                plans[key] = plan_shot(frames, active, size[0] / size[1])
            part = work / f"shot-{i:04d}.mkv"
            modes.append(render_shot(shot, plans[key], active, size, part, interpolation=interpolation))
            parts.append(part)
        joined = work / "joined.mkv"
        _concat(parts, joined)
        mixed = work / "mixed.mkv"
        _narration_mix(joined, voiceover, mixed)
        final = outdir / f"final-{aspect}.mp4"
        audio = finish(mixed, captions.get(aspect), final)
        info = probe(final)
        reports[aspect] = {"path": str(final), "duration": info["duration"], "width": info["width"],
                           "height": info["height"], "fps": info["fps"], **audio,
                           "duplicate_frames": duplicate_frame_ratio(final),
                           "modes": {m: sum(1 for x in modes if x["mode"] == m) for m in ("track", "fit")},
                           "interpolation": sorted({x["interpolation"] for x in modes})}
        shutil.rmtree(work, ignore_errors=True)
    (outdir / "render.json").write_text(json.dumps({"edl": edl, "outputs": reports,
                                                    "plans": {f"{k[0]}-{k[1]}": v for k, v in plans.items()}},
                                                   indent=1, default=str))
    return reports

"""Phase 0: how fast and how real is 60 fps on a CPU runner?

Times four ways of turning 24 fps footage into 60 fps, at the two render sizes we need
(1080×1080 square, and the 608×1080 source crop that becomes 9:16), then counts how many
output frames are near-duplicates (fake 60 fps shows up as many duplicates).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import USER_AGENT, out_dir, write_report  # noqa: E402

SECONDS = 5
SIZES = {"square-1080x1080": (1080, 1080), "vertical-crop-608x1080": (608, 1080)}


def run(command: list[str], **kwargs) -> float:
    started = time.time()
    subprocess.run(command, check=True, capture_output=True, **kwargs)
    return time.time() - started


def source_clip(directory: Path) -> Path:
    clips = sorted(Path(os.environ.get("PROBE_CLIPS", "work/phase0/youtube/clips")).glob("*.mp4"))
    target = directory / "source-24fps.mp4"
    if clips:
        source = ["-i", str(clips[0])]
    else:
        source = ["-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=24"]
    run(["ffmpeg", "-y", *source, "-t", str(SECONDS), "-vf", "fps=24,scale=1920:1080", "-an",
         "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(target)])
    return target


def crop(source: Path, size: tuple[int, int], target: Path) -> Path:
    width, height = size
    run(["ffmpeg", "-y", "-i", str(source), "-vf",
         f"scale=-2:{height},crop={width}:{height}", "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(target)])
    return target


def duplicate_ratio(video: Path) -> float:
    """Fraction of frames mpdecimate would drop as near-identical to the previous one."""
    def frames(extra: list[str]) -> int:
        out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                              "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0",
                              *extra, str(video)], capture_output=True, text=True).stdout.strip()
        return int(out or 0)
    total = frames([])
    kept = subprocess.run(["ffmpeg", "-i", str(video), "-vf", "mpdecimate", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    match = re.findall(r"frame=\s*(\d+)", kept)
    unique = int(match[-1]) if match else total
    return round(1 - unique / total, 3) if total else 0.0


def ffmpeg_method(name: str, vf: str, source: Path, target: Path) -> dict:
    seconds = run(["ffmpeg", "-y", "-i", str(source), "-vf", vf, "-c:v", "libx264", "-crf", "16",
                   "-preset", "fast", str(target)])
    return {"method": name, "seconds": round(seconds, 1), "x_realtime": round(seconds / SECONDS, 2),
            "duplicate_ratio": duplicate_ratio(target)}


def rife_binary(directory: Path) -> tuple[Path, Path] | None:
    headers = {"User-Agent": USER_AGENT}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    release = requests.get("https://api.github.com/repos/nihui/rife-ncnn-vulkan/releases/latest",
                           headers=headers, timeout=30).json()
    asset = next((a for a in release.get("assets", []) if a["name"].endswith("ubuntu.zip")), None)
    if not asset:
        return None
    archive = directory / asset["name"]
    archive.write_bytes(requests.get(asset["browser_download_url"], timeout=300).content)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(directory)
    binary = next(directory.rglob("rife-ncnn-vulkan"))
    binary.chmod(0o755)
    models = sorted(p for p in binary.parent.iterdir() if p.is_dir() and p.name.startswith("rife-v4"))
    return binary, models[-1]


def rife_method(binary: Path, model: Path, gpu: str, source: Path, target: Path, work: Path) -> dict:
    frames_in, frames_out = work / "in", work / "out"
    for folder in (frames_in, frames_out):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
    run(["ffmpeg", "-y", "-i", str(source), str(frames_in / "%06d.png")])
    count = len(list(frames_in.glob("*.png")))
    started = time.time()
    run([str(binary), "-i", str(frames_in), "-o", str(frames_out), "-m", str(model),
         "-n", str(round(count * 60 / 24)), "-g", gpu, "-j", "1:2:2"], cwd=binary.parent)
    interpolate = time.time() - started
    run(["ffmpeg", "-y", "-framerate", "60", "-i", str(frames_out / "%08d.png"), "-c:v", "libx264",
         "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p", str(target)])
    return {"method": f"rife-ncnn {model.name} (gpu={gpu})", "seconds": round(interpolate, 1),
            "x_realtime": round(interpolate / SECONDS, 2), "duplicate_ratio": duplicate_ratio(target)}


def main() -> None:
    directory = out_dir("interpolation")
    source = source_clip(directory)
    report = {"source": source.name, "seconds": SECONDS, "results": [], "errors": []}
    rife = None
    try:
        rife = rife_binary(directory / "rife-bin")
        report["rife"] = str(rife[1].name) if rife else "no ubuntu release asset"
    except Exception as exc:  # noqa: BLE001
        report["errors"].append(f"rife download: {exc}"[:300])
    for label, size in SIZES.items():
        cropped = crop(source, size, directory / f"{label}-24fps.mp4")
        methods = [("duplicate (current)", "fps=60"), ("blend", "framerate=fps=60"),
                   ("minterpolate mci", "minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")]
        for name, vf in methods:
            try:
                row = ffmpeg_method(name, vf, cropped, directory / f"{label}-{name.split()[0]}.mp4")
                report["results"].append({"size": label, **row})
            except subprocess.CalledProcessError as exc:
                report["errors"].append(f"{label} {name}: {exc.stderr[-300:]!r}")
        if rife:
            for gpu in ("-1", "0"):
                try:
                    row = rife_method(*rife, gpu, cropped, directory / f"{label}-rife-g{gpu}.mp4",
                                      directory / "frames")
                    report["results"].append({"size": label, **row})
                except subprocess.CalledProcessError as exc:
                    report["errors"].append(f"{label} rife gpu={gpu}: {(exc.stderr or b'')[-300:]!r}")
        print(json.dumps(report["results"][-5:], indent=1), flush=True)
    shutil.rmtree(directory / "frames", ignore_errors=True)
    shutil.rmtree(directory / "rife-bin", ignore_errors=True)
    lines = ["## Phase 0 · 60 fps probe", "",
             f"Source: {source.name}, {SECONDS} s at 24 fps. `x realtime` = processing seconds per second of video "
             "(lower is faster). `duplicates` near 0.6 means fake 60 fps.", "",
             "| Size | Method | Seconds | x realtime | Duplicates |", "|---|---|---|---|---|"]
    lines += [f"| {r['size']} | {r['method']} | {r['seconds']} | {r['x_realtime']} | {r['duplicate_ratio']} |"
              for r in report["results"]]
    lines += [f"- error: {e}" for e in report["errors"]]
    write_report(directory, report, lines)


if __name__ == "__main__":
    main()

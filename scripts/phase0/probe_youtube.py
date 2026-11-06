"""Phase 0: can the runner search YouTube, read the ranking signals we plan to use, and download?

For each test film this records, without judging quality:
- which search results come back for the planned query families;
- per candidate: views, likes, subscribers, verified checkmark, Most Replayed heatmap,
  chapters, description timestamps, captions, best resolution/fps;
- top comments (and how many carry timestamps) for a few candidates;
- whether a short section actually downloads, and its real resolution/fps.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import films, out_dir, slug, write_report  # noqa: E402

import yt_dlp  # noqa: E402

QUERY_FAMILIES = ["{t} {y} scene", "{t} {y} fight scene", "{t} {y} best scenes",
                  "{t} {y} clip", "{t} all scenes compilation"]
SEARCH_DEPTH = 10
FULL_PER_FILM = 8
COMMENTS_PER_FILM = 2
REJECT = re.compile(r"\b(trailer|teaser|tv spot|review|reaction|explained|recap|ending explained|"
                    r"breakdown|edit|amv|slowed|reverb|full movie|behind the scenes|interview)\b", re.I)
TIMESTAMP = re.compile(r"\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b")
BOT = re.compile(r"sign in to confirm|not a bot|confirm you.?re not", re.I)


def cookie_file() -> str | None:
    contents = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if not contents:
        return None
    path = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "phase0-youtube-cookies.txt"
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(contents + "\n")
    return str(path)


COOKIES = cookie_file()
PROXY = os.environ.get("YTDLP_FALLBACK_PROXY", "")


def options(route: str, **extra) -> dict:
    result = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 30,
              "retries": 2, "extractor_retries": 2}
    if COOKIES:
        result["cookiefile"] = COOKIES
    if route == "warp" and PROXY:
        result["proxy"] = PROXY
    result.update(extra)
    return result


ROUTE_LOG: list[dict] = []


def call(target: str, **extra):
    """Try the direct route, then WARP after a bot check. Record which route worked."""
    routes = ["direct"] + (["warp"] if PROXY else [])
    last = None
    for route in routes:
        started = time.time()
        try:
            with yt_dlp.YoutubeDL(options(route, **extra)) as ydl:
                info = ydl.extract_info(target, download=not extra.get("skip_download", True))
            ROUTE_LOG.append({"target": target[:80], "route": route, "ok": True,
                              "seconds": round(time.time() - started, 1)})
            return info, route
        except Exception as exc:  # noqa: BLE001 - a probe records every failure kind
            message = str(exc)
            last = message
            ROUTE_LOG.append({"target": target[:80], "route": route, "ok": False,
                              "bot_check": bool(BOT.search(message)), "error": message[:300],
                              "seconds": round(time.time() - started, 1)})
            if not BOT.search(message) and route == "direct" and "proxy" not in message.lower():
                # A non-bot error (removed video, age gate…) will not be fixed by another route.
                break
    raise RuntimeError(last or "unknown failure")


def best_video(info: dict) -> dict:
    formats = [f for f in info.get("formats") or [] if f.get("vcodec") not in (None, "none") and f.get("height")]
    if not formats:
        return {}
    top = max(formats, key=lambda f: (f.get("height") or 0, f.get("fps") or 0, f.get("tbr") or 0))
    fps_values = sorted({round(f.get("fps") or 0) for f in formats})
    return {"max_height": top.get("height"), "max_width": top.get("width"), "fps_at_max": top.get("fps"),
            "fps_values": fps_values, "codec_at_max": top.get("vcodec")}


def heatmap_summary(info: dict) -> dict | None:
    heat = info.get("heatmap") or []
    if not heat:
        return None
    peak = max(heat, key=lambda h: h.get("value", 0))
    return {"points": len(heat), "peak_start": peak.get("start_time"), "peak_end": peak.get("end_time"),
            "peak_value": peak.get("value")}


def candidate_row(info: dict, route: str) -> dict:
    description = info.get("description") or ""
    return {
        "id": info.get("id"), "title": info.get("title"), "channel": info.get("channel"),
        "duration": info.get("duration"), "views": info.get("view_count"), "likes": info.get("like_count"),
        "subscribers": info.get("channel_follower_count"), "verified": info.get("channel_is_verified"),
        "upload_date": info.get("upload_date"), "heatmap": heatmap_summary(info),
        "chapters": [c.get("title") for c in info.get("chapters") or []],
        "description_timestamps": len(TIMESTAMP.findall(description)),
        "manual_subtitles": sorted((info.get("subtitles") or {}).keys())[:8],
        "auto_captions_en": "en" in (info.get("automatic_captions") or {}),
        "age_limit": info.get("age_limit"), "route": route, **best_video(info),
    }


def comments(video_id: str) -> dict:
    info, route = call(f"https://www.youtube.com/watch?v={video_id}", getcomments=True,
                       extractor_args={"youtube": {"max_comments": ["40", "all", "0", "0"],
                                                   "comment_sort": ["top"]}})
    rows = info.get("comments") or []
    stamped = [c for c in rows if TIMESTAMP.search(c.get("text") or "")]
    return {"id": video_id, "route": route, "fetched": len(rows), "with_timestamps": len(stamped),
            "examples": [{"text": (c.get("text") or "")[:160], "likes": c.get("like_count")}
                         for c in (stamped or rows)[:4]]}


def download_section(video_id: str, directory: Path) -> dict:
    """Download the whole clip with yt-dlp's own downloader, then cut 15 s locally.

    Section downloads hand the media URL to FFmpeg, which ignores the SOCKS (WARP) proxy
    and is refused by YouTube; the native downloader does use the proxy.
    """
    target = directory / f"{video_id}.full.%(ext)s"
    started = time.time()
    info, route = call(f"https://www.youtube.com/watch?v={video_id}", skip_download=False,
                       format="bv*[height<=1080]+ba/b[height<=1080]", outtmpl=str(target),
                       merge_output_format="mp4", max_filesize=400 * 1024 * 1024)
    full = sorted(directory.glob(f"{video_id}.full.*"))
    if full:
        subprocess.run(["ffmpeg", "-y", "-ss", "20", "-i", str(full[0]), "-t", "15", "-c", "copy",
                        str(directory / f"{video_id}.mp4")], capture_output=True)
        full_probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
                                     "-of", "json", str(full[0])], capture_output=True, text=True)
        full_info = json.loads(full_probe.stdout or "{}").get("format", {})
        full[0].unlink()
    files = sorted(directory.glob(f"{video_id}.mp4"))
    result = {"id": video_id, "route": route, "seconds": round(time.time() - started, 1),
              "files": [f.name for f in files], "full_clip": full_info if full else None}
    if files:
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height,avg_frame_rate", "-of", "json", str(files[0])],
                               capture_output=True, text=True)
        result["probe"] = json.loads(probe.stdout or "{}").get("streams", [{}])[0]
        result["bytes"] = files[0].stat().st_size
    return result


def main() -> None:
    directory = out_dir("youtube")
    clips = directory / "clips"
    clips.mkdir(exist_ok=True)
    report = {"cookies": bool(COOKIES), "warp_available": bool(PROXY), "yt_dlp": yt_dlp.version.__version__,
              "films": []}
    for film in films():
        entry = {"film": film["title"], "year": film["year"], "queries": [], "candidates": [],
                 "comments": [], "download": None, "errors": []}
        seen: dict[str, dict] = {}
        for family in QUERY_FAMILIES:
            query = family.format(t=film["short"], y=film["year"])
            try:
                info, route = call(f"ytsearch{SEARCH_DEPTH}:{query}", extract_flat="in_playlist")
            except RuntimeError as exc:
                entry["errors"].append({"query": query, "error": str(exc)[:300]})
                continue
            rows = info.get("entries") or []
            kept = 0
            for row in rows:
                title = row.get("title") or ""
                rejected = bool(REJECT.search(title))
                if not rejected and row.get("id"):
                    kept += 1
                    seen.setdefault(row["id"], {"id": row["id"], "title": title, "flat_views": row.get("view_count"),
                                                "flat_duration": row.get("duration"), "query": query})
            entry["queries"].append({"query": query, "route": route, "results": len(rows),
                                     "kept_after_title_filter": kept,
                                     "flat_fields": sorted(rows[0].keys()) if rows else []})
        ranked = sorted(seen.values(), key=lambda r: r.get("flat_views") or 0, reverse=True)
        for row in ranked[:FULL_PER_FILM]:
            try:
                info, route = call(f"https://www.youtube.com/watch?v={row['id']}")
                entry["candidates"].append({**candidate_row(info, route), "query": row["query"]})
            except RuntimeError as exc:
                entry["errors"].append({"video": row["id"], "error": str(exc)[:300]})
        for candidate in entry["candidates"][:COMMENTS_PER_FILM]:
            try:
                entry["comments"].append(comments(candidate["id"]))
            except RuntimeError as exc:
                entry["errors"].append({"comments": candidate["id"], "error": str(exc)[:300]})
        for candidate in entry["candidates"][:2]:
            try:
                entry["download"] = download_section(candidate["id"], clips)
                break
            except RuntimeError as exc:
                entry["errors"].append({"download": candidate["id"], "error": str(exc)[:300]})
        report["films"].append(entry)
        (directory / f"{slug(film['title'])}.json").write_text(json.dumps(entry, indent=2, ensure_ascii=False))
    report["routes"] = ROUTE_LOG
    write_report(directory, report, summarise(report))


def summarise(report: dict) -> list[str]:
    lines = ["## Phase 0 · YouTube probe", "",
             f"yt-dlp {report['yt_dlp']} · cookies: {report['cookies']} · WARP fallback: {report['warp_available']}", "",
             "| Film | Searches ok | Candidates | Verified | Subs known | Heatmap | Chapters | ≥1080p | 60fps | Comments (stamped) | Download |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for film in report["films"]:
        c = film["candidates"]
        ok = sum(1 for q in film["queries"] if q["results"])
        com = "; ".join(f"{x['fetched']} ({x['with_timestamps']})" for x in film["comments"]) or "–"
        dl = film["download"]
        dl_text = (f"{dl['probe'].get('width')}×{dl['probe'].get('height')} @ {dl['probe'].get('avg_frame_rate')} via {dl['route']}"
                   if dl and dl.get("probe") else "failed")
        lines.append(f"| {film['film']} | {ok}/{len(QUERY_FAMILIES)} | {len(c)} | "
                     f"{sum(1 for x in c if x.get('verified'))} | {sum(1 for x in c if x.get('subscribers'))} | "
                     f"{sum(1 for x in c if x.get('heatmap'))} | {sum(1 for x in c if x.get('chapters'))} | "
                     f"{sum(1 for x in c if (x.get('max_height') or 0) >= 1080)} | "
                     f"{sum(1 for x in c if 60 in (x.get('fps_values') or []))} | {com} | {dl_text} |")
    routes = report["routes"]
    bot = sum(1 for r in routes if r.get("bot_check"))
    lines += ["", f"Requests: {len(routes)}, failed: {sum(1 for r in routes if not r['ok'])}, bot checks: {bot}, "
              f"succeeded via WARP: {sum(1 for r in routes if r['ok'] and r['route'] == 'warp')}"]
    return lines


if __name__ == "__main__":
    main()

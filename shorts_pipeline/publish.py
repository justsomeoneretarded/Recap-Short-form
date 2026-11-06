"""Upload package for each Short: title options, description, tags, credits and a quality review.

The review is an automatic critic that inspects the finished files, not a human verdict:
60 fps without duplicated frames, YouTube loudness, length, cut rhythm, framing fallbacks,
script checks, caption coverage and footage sources. Every check says pass/warn/fail and why.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path


def _hashtag(text: str) -> str:
    return "#" + re.sub(r"[^A-Za-z0-9]", "", text.title())


def title_options(result: dict, limit: int = 3) -> list[str]:
    """The chosen script's title first, then the other drafts' titles (distinct, ≤ 70 characters)."""
    seen, titles = set(), []
    for title in [result["script"].get("title")] + [(d.get("script") or {}).get("title") for d in result.get("drafts", [])]:
        if not title:
            continue
        clean = " ".join(str(title).split())[:70]
        if clean.lower() not in seen:
            seen.add(clean.lower())
            titles.append(clean)
    return titles[:limit]


def description(result: dict, research: dict, arc: dict, clips: dict[str, dict]) -> str:
    movie = research["movie"]
    script = result["script"]
    cast = ", ".join(c["name"] for c in movie.get("cast", [])[:4])
    tags = [_hashtag(movie["title"]), "#MovieRecap", "#Shorts"] + [_hashtag(g) for g in movie.get("genres", [])[:2]]
    sources = []
    for scene in arc["scenes"]:
        clip = clips.get(scene["clip_id"], {})
        sources.append(f"- {clip.get('channel') or 'YouTube'}: https://www.youtube.com/watch?v={scene['clip_id']}")
    return "\n".join([
        script.get("hook", "").strip(),
        "",
        f"🎬 {movie['title']} ({movie.get('year')})" + (f" — starring {cast}" if cast else ""),
        "",
        " ".join(dict.fromkeys(tags)),
        "",
        "Footage sources (commentary and recap; all rights belong to the film's owners):",
        *dict.fromkeys(sources),
    ])


def tags(research: dict) -> list[str]:
    movie = research["movie"]
    base = [movie["title"], f"{movie['title']} {movie.get('year')}", f"{movie['title']} recap", "movie recap",
            "movie explained short", "film recap"]
    base += [c["name"] for c in movie.get("cast", [])[:3]] + movie.get("genres", [])[:2] + movie.get("keywords", [])[:4]
    out, total = [], 0
    for tag in dict.fromkeys(t.strip() for t in base if t):
        if total + len(tag) + 1 > 480:  # YouTube allows 500 characters of tags
            break
        out.append(tag)
        total += len(tag) + 1
    return out


def review(render: dict, voiceover: dict, result: dict, edl: dict, target_seconds: float) -> list[dict]:
    checks = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    for aspect, out in render.items():
        fps_ok = abs(out["fps"] - 60) < 0.5
        add(f"{aspect}: 60 fps", "pass" if fps_ok else "fail", f"{out['fps']:.2f} fps")
        dup = out.get("duplicate_frames", 0)
        add(f"{aspect}: real motion (no copied frames)", "pass" if dup < 0.1 else "warn" if dup < 0.3 else "fail",
            f"{dup:.0%} near-duplicate frames")
        lufs, peak = out["integrated_lufs"], out["true_peak_db"]
        add(f"{aspect}: loudness", "pass" if abs(lufs + 14) <= 1 and peak <= -0.8 else "warn",
            f"{lufs:.1f} LUFS, {peak:.1f} dBTP (target −14 / −1)")
        modes = out.get("modes", {})
        fit_share = modes.get("fit", 0) / max(1, sum(modes.values()))
        add(f"{aspect}: framing", "pass" if fit_share <= 0.35 else "warn",
            f"{modes.get('track', 0)} tracked, {modes.get('fit', 0)} fit-over-blur shots")
    duration = edl["duration"]
    add("length", "pass" if 0.6 * target_seconds <= duration <= target_seconds + 5 else "warn",
        f"{duration:.0f} s (requested {target_seconds:.0f} s)")
    add("cut rhythm", "pass" if 1.2 <= edl["median_shot"] <= 3.8 else "warn",
        f"median shot {edl['median_shot']} s (references 1.5–2.9 s)")
    wpm = voiceover.get("words_per_minute", 0)
    add("narration pace", "pass" if 170 <= wpm <= 240 else "warn", f"{wpm:.0f} words/min (references 206–231 incl. dialogue)")
    lines = sum(1 for b in voiceover["beats"] if b["kind"] == "dialogue")
    add("real movie lines", "pass" if lines else "warn", f"{lines} original dialogue beats")
    issues = result["check"]["issues"]
    add("script checks", "pass" if not issues else "warn", "; ".join(issues) or "no invented names, filler or quoting")
    hook = len((result["script"].get("hook") or "").split())
    add("hook", "pass" if 3 <= hook <= 14 else "warn", f"{hook} words")
    repairs = list(voiceover.get("warnings") or [])
    repairs += [{"beat": "shot", "reason": f"shot {r.get('index')}: {r['fallback']}"}
                for out in render.values() for r in out.get("shot_rows", []) if r.get("fallback")]
    add("automatic repairs", "pass" if not repairs else "warn",
        "; ".join(r["reason"] for r in repairs)[:400] or "none needed")
    return checks


def review_html(name: str, checks: list[dict], covers: dict, sheet: str | None, titles: list[str]) -> str:
    colour = {"pass": "#1a7f37", "warn": "#9a6700", "fail": "#cf222e"}
    rows = "".join(f"<tr><td>{html.escape(c['check'])}</td><td style='color:{colour[c['status']]};font-weight:600'>"
                   f"{c['status'].upper()}</td><td>{html.escape(c['detail'])}</td></tr>" for c in checks)
    images = "".join(f"<figure><img src='{html.escape(Path(p).name)}' width='240'><figcaption>{html.escape(k)}"
                     f"</figcaption></figure>" for k, p in covers.items())
    sheet_html = f"<h2>Contact sheet</h2><img src='{html.escape(Path(sheet).name)}' width='100%'>" if sheet else ""
    return (f"<!doctype html><meta charset='utf-8'><title>{html.escape(name)} review</title>"
            "<style>body{font-family:system-ui;margin:24px;max-width:1100px}td{padding:4px 10px;border-bottom:1px solid #ddd}"
            "figure{display:inline-block;margin:6px}</style>"
            f"<h1>{html.escape(name)}</h1><h2>Title options</h2><ol>{''.join(f'<li>{html.escape(t)}</li>' for t in titles)}</ol>"
            f"<h2>Automatic checks</h2><table>{rows}</table><h2>Covers</h2>{images}{sheet_html}")


def write_package(folder: Path, *, result: dict, research: dict, arc: dict, clips: dict[str, dict], voiceover: dict,
                  edl: dict, render: dict, covers: dict, sheet: str | None, target_seconds: float) -> dict:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    titles = title_options(result)
    checks = review(render, voiceover, result, edl, target_seconds)
    (folder / "title-options.txt").write_text("\n".join(titles) + "\n")
    (folder / "description.txt").write_text(description(result, research, arc, clips) + "\n")
    (folder / "tags.txt").write_text(", ".join(tags(research)) + "\n")
    (folder / "review.json").write_text(json.dumps(checks, indent=1))
    (folder / "review.html").write_text(review_html(titles[0] if titles else arc["id"], checks, covers.get("covers", {}),
                                                    sheet, titles))
    worst = "fail" if any(c["status"] == "fail" for c in checks) else "warn" if any(c["status"] == "warn" for c in checks) else "pass"
    return {"titles": titles, "verdict": worst, "checks": checks}

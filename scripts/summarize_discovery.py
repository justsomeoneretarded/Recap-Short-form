"""Print one compact Markdown summary of research and discovery artifacts (also to the job summary)."""
import glob
import json
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "all"
rows = ["| Movie | Cast photos | Studio clips | Plot words | Subtitles | Warnings |", "|---|---|---|---|---|---|"]
for path in sorted(glob.glob(f"{root}/research-*/research.json")):
    r = json.load(open(path))
    m, s = r["movie"], r["subtitles"]
    rows.append(f"| {m['title']} ({m['year']}) | {sum(1 for c in m['cast'] if c['photo'])} | {len(m['clips'])} | "
                f"{r['wikipedia'].get('words')} | {'yes' if s.get('path') else s.get('skipped')} | "
                f"{' / '.join(w[:120] for w in r['warnings']) or '–'} |")
for path in sorted(glob.glob(f"{root}/discover-*/summary.json")):
    s = json.load(open(path))
    rows += ["", f"**{s['movie']} ({s['year']})**: {s['candidates']} candidates, {s['rejected']} rejected, "
                 f"{s['placed']}/{s['considered']} placed in the movie, {s['search_errors']} search errors", "",
             "| # | Clip | Channel | Views | ✔ | Height | Score | Comp. | Placed by | Movie time | Screening |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in s["clips"]:
        t = c["movie_time"]
        when = f"{int(t[0] // 60)}:{int(t[0] % 60):02d}–{int(t[1] // 60)}:{int(t[1] % 60):02d}" if t else "–"
        rows.append(f"| {c['rank']} | {c['title'][:45]} | {(c['channel'] or '')[:20]} | {c['views'] or 0:,} | "
                    f"{'✔' if c['verified'] else ''} | {c['height']} | {c['score']} | {'yes' if c['compilation'] else ''} | "
                    f"{c['method'] or '–'}{' (' + str(c.get('segments_placed')) + ' segs)' if c.get('segments_placed') else ''} | "
                    f"{when} | {(c.get('screen') or '–')[:60]} |")
    if s.get("arcs") is not None:
        rows += ["", f"Stories (one Short each): {len(s['arcs'])}"]
        for arc in s["arcs"]:
            m = arc["movie"]
            rows.append(f"- {arc['id']}: {int(m[0] // 60)}:{int(m[0] % 60):02d}–{int(m[1] // 60)}:{int(m[1] % 60):02d}, "
                        f"{arc['footage']:.0f} s footage, score {arc['score']}{' (shorter)' if arc['shorter'] else ''}: "
                        + " → ".join(arc["scenes"]))
    notes = sorted({(c.get("caption_note") or "")[:90] for c in s["clips"] if c.get("caption_note")})
    if notes:
        rows += ["", "Caption notes: " + " · ".join(notes[:3])]
text = "\n".join(rows)
print("SUMMARY\n" + text)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
        stream.write(text + "\n")

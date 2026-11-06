# Phase 0 probes

These scripts measure the risky parts of the v2 redesign before any production code changes.
The **Phase 0 probes** workflow runs them on GitHub-hosted runners whenever this folder changes
on a `claude/**` branch, or on demand from Actions. Results appear in each job's summary and
in the `phase0-*` artifacts (7-day retention).

| Probe | Question it answers |
|---|---|
| `probe_youtube.py` | Can the runner search YouTube and download? Which ranking signals come back: views, likes, subscribers, verified checkmark, Most Replayed heatmap, chapters, captions, top comments, best resolution and fps? |
| `probe_research.py` | How much story detail is available: Wikipedia plot length, TMDB clips and cast photos, OpenSubtitles full subtitles, IMSDb screenplays? |
| `probe_writers.py` | The same scene brief written by GitHub Models candidates and by Top10's local Gemma 4 12B, so they can be read side by side. |
| `probe_interpolation.py` | How long true 60 fps takes on CPU (frame blending, FFmpeg motion interpolation, RIFE via ncnn on CPU or lavapipe Vulkan), and whether the output has duplicate frames. |

Optional repository secrets used when present: `YOUTUBE_COOKIES`, `TMDB_READ_TOKEN`,
`OPENSUBTITLES_API_KEY`. Without them those parts report "skipped" instead of failing.

The test films are in `films.json`. The writer brief in `writer_brief.json` paraphrases story
events and stands in for the scene dossiers the new pipeline will build.

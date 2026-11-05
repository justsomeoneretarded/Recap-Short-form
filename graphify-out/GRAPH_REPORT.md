# Graph Report - Recap-Short-form  (2026-11-05)

## Corpus Check
- 34 files · ~41,769 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 328 nodes · 699 edges · 14 communities (10 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `04e31c87`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_sources_planner.py
- default / description
- difflib / re
- array / copy
- generate-shorts.yml / concurrency
- argparse / pathlib
- Evidence-linked story beats and timed edit decisions / Source-grounded
- Concrete action or contradiction before a dossier / Automatic speech a
- ci.yml / jobs
- sources.py
- recap-shorts
- test_workflows.py

## God Nodes (most connected - your core abstractions)
1. `render_plan()` - 28 edges
2. `generate()` - 21 edges
3. `Eight reference Shorts: evidence and production guide` - 21 edges
4. `make_plan()` - 18 edges
5. `resolve_source()` - 18 edges
6. `synthesize_plan()` - 17 edges
7. `index_source()` - 15 edges
8. `Upstream technology comparison for Recap Shorts` - 14 edges
9. `write_captions()` - 12 edges
10. `inputs` - 11 edges

## Surprising Connections (you probably didn't know these)
- `test_ffmpeg_detector_debounces_adjacent_frame_triggers()` --calls--> `_ffmpeg_boundaries()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/sources.py
- `test_segments_cover_full_source_without_gaps()` --calls--> `_segments()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/sources.py
- `test_remote_sources_require_https_without_embedded_credentials()` --calls--> `resolve_source()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/sources.py
- `test_failed_download_is_not_cached()` --calls--> `resolve_source()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/sources.py
- `test_unknown_scene_id_is_never_substituted()` --calls--> `_normalize_model_plan()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/planner.py

## Import Cycles
- None detected.

## Communities (14 total, 4 thin omitted)

### Community 0 - "test_sources_planner.py"
Cohesion: 0.10
Nodes (26): _describe(), _key(), make_plan(), _normalize_model_plan(), _request_json(), _require_models(), validate_storyboard(), _segments() (+18 more)

### Community 1 - "default / description"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "difflib / re"
Cohesion: 0.12
Nodes (19): _align_script(), _chunks(), _duration(), _integer_words(), _lexical(), _normal(), _run(), synthesize_plan() (+11 more)

### Community 3 - "array / copy"
Cohesion: 0.14
Nodes (21): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+13 more)

### Community 4 - "generate-shorts.yml / concurrency"
Cohesion: 0.06
Nodes (35): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+27 more)

### Community 5 - "argparse / pathlib"
Cohesion: 0.12
Nodes (18): _ass_time(), _groups(), _srt_time(), _wrap(), write_captions(), generate(), stage(), main() (+10 more)

### Community 6 - "Evidence-linked story beats and timed edit decisions / Source-grounded"
Cohesion: 0.10
Nodes (18): faster-whisper small.en, resemble-ai/chatterbox, Chatterbox Nano, Original and multilingual Chatterbox variants, Chatterbox Turbo, SYSTRAN/faster-whisper, Female reference sample, FFmpeg/FFmpeg (+10 more)

### Community 7 - "Concrete action or contradiction before a dossier / Automatic speech a"
Cohesion: 0.20
Nodes (9): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+1 more)

### Community 8 - "ci.yml / jobs"
Cohesion: 0.15
Nodes (12): jobs, test, name, on, permissions, contents, run, uses (+4 more)

### Community 9 - "sources.py"
Cohesion: 0.15
Nodes (12): _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url(), index_source(), resolve_source(), _run(), _video_info() (+4 more)

## Knowledge Gaps
- **76 isolated node(s):** `name`, `description`, `required`, `type`, `description` (+71 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 123 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate()` connect `argparse / pathlib` to `test_sources_planner.py`, `sources.py`, `difflib / re`, `array / copy`?**
  _High betweenness centrality (0.003) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _76 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_sources_planner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09581646423751687 - nodes in this community are weakly interconnected._
- **Why does `render_plan()` connect `array / copy` to `sources.py`, `argparse / pathlib`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `default / description` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `synthesize_plan()` connect `difflib / re` to `sources.py`, `array / copy`, `argparse / pathlib`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `difflib / re` be split into smaller, more focused modules?**
  _Cohesion score 0.12436974789915967 - nodes in this community are weakly interconnected._
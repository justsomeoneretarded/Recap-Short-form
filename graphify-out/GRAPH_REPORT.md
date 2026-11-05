# Graph Report - Recap-Short-form  (2026-11-05)

## Corpus Check
- 34 files · ~43,356 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 341 nodes · 724 edges · 14 communities (10 shown, 4 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c2d7fe40`
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
2. `make_plan()` - 21 edges
3. `generate()` - 21 edges
4. `Eight reference Shorts: evidence and production guide` - 21 edges
5. `resolve_source()` - 18 edges
6. `synthesize_plan()` - 17 edges
7. `index_source()` - 15 edges
8. `Upstream technology comparison for Recap Shorts` - 14 edges
9. `_describe()` - 12 edges
10. `write_captions()` - 12 edges

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
Cohesion: 0.08
Nodes (31): _describe(), _key(), make_plan(), _normalize_model_plan(), _request_json(), _require_models(), validate_storyboard(), _segments() (+23 more)

### Community 1 - "default / description"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "difflib / re"
Cohesion: 0.10
Nodes (25): _ass_time(), _groups(), _srt_time(), _wrap(), write_captions(), _align_script(), _chunks(), _duration() (+17 more)

### Community 3 - "array / copy"
Cohesion: 0.15
Nodes (21): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+13 more)

### Community 4 - "generate-shorts.yml / concurrency"
Cohesion: 0.05
Nodes (38): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+30 more)

### Community 5 - "argparse / pathlib"
Cohesion: 0.15
Nodes (12): generate(), stage(), main(), assign_timeline(), request_config(), excerpt(), probe(), run() (+4 more)

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
Nodes (11): _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url(), index_source(), resolve_source(), _run(), _video_info() (+3 more)

## Knowledge Gaps
- **79 isolated node(s):** `name`, `description`, `required`, `type`, `description` (+74 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 131 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate()` connect `argparse / pathlib` to `test_sources_planner.py`, `sources.py`, `difflib / re`, `array / copy`?**
  _High betweenness centrality (0.003) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _79 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_sources_planner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0792156862745098 - nodes in this community are weakly interconnected._
- **Why does `render_plan()` connect `array / copy` to `test_sources_planner.py`, `sources.py`, `argparse / pathlib`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `default / description` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `make_plan()` connect `test_sources_planner.py` to `sources.py`, `argparse / pathlib`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `difflib / re` be split into smaller, more focused modules?**
  _Cohesion score 0.09725158562367865 - nodes in this community are weakly interconnected._
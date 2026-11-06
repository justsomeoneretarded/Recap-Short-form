# Graph Report - Recap-Short-form  (2026-11-06)

## Corpus Check
- 43 files · ~57,486 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 499 nodes · 1113 edges · 23 communities (12 shown, 11 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3f58d5e8`
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
- analyze_source_speech
- ci.yml / jobs
- make_plan
- recap-shorts
- write_captions
- with
- test_workflows.py

## God Nodes (most connected - your core abstractions)
1. `make_plan()` - 31 edges
2. `render_plan()` - 30 edges
3. `generate()` - 23 edges
4. `write_captions()` - 22 edges
5. `analyze_source_speech()` - 21 edges
6. `Eight reference Shorts: evidence and production guide` - 21 edges
7. `_compress_narration()` - 18 edges
8. `resolve_source()` - 18 edges
9. `synthesize_plan()` - 18 edges
10. `_normalize_model_plan()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_ffmpeg_detector_debounces_adjacent_frame_triggers()` --calls--> `_ffmpeg_boundaries()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/sources.py
- `test_unknown_scene_id_is_never_substituted()` --calls--> `_normalize_model_plan()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/planner.py
- `test_reverse_chronology_within_a_beat_is_rejected()` --calls--> `_normalize_model_plan()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/planner.py
- `test_caption_offsets_and_script_punctuation()` --calls--> `write_captions()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/captions.py
- `test_segments_cover_full_source_without_gaps()` --calls--> `_segments()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/sources.py

## Import Cycles
- None detected.

## Communities (23 total, 11 thin omitted)

### Community 0 - "test_sources_planner.py"
Cohesion: 0.06
Nodes (53): validate_storyboard(), _segments(), _is_compression(), _normalize_speech(), _plan(), _production_six_candidate(), _production_three_candidates(), _speech_candidate() (+45 more)

### Community 1 - "default / description"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "difflib / re"
Cohesion: 0.09
Nodes (26): _align_script(), _chunks(), _contextual_units(), _duration(), _integer_words(), _lexical(), _normal(), _run() (+18 more)

### Community 3 - "array / copy"
Cohesion: 0.15
Nodes (26): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+18 more)

### Community 4 - "generate-shorts.yml / concurrency"
Cohesion: 0.05
Nodes (39): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+31 more)

### Community 5 - "argparse / pathlib"
Cohesion: 0.10
Nodes (19): compress(), main(), prepare_model(), run_probe(), write_json(), generate(), stage(), main() (+11 more)

### Community 6 - "Evidence-linked story beats and timed edit decisions / Source-grounded"
Cohesion: 0.07
Nodes (27): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+19 more)

### Community 7 - "analyze_source_speech"
Cohesion: 0.12
Nodes (17): analyze_source_speech(), _candidate(), _number(), _transcribe(), fixture(), segment(), test_bad_word_bounds_and_confidence(), test_cache_and_content_invalidation() (+9 more)

### Community 8 - "ci.yml / jobs"
Cohesion: 0.12
Nodes (15): jobs, test, name, on, permissions, contents, name, run (+7 more)

### Community 9 - "make_plan"
Cohesion: 0.09
Nodes (24): _compress_narration(), _compression_schema(), _describe(), _key(), make_plan(), _NarrationTimingExcess, _normalize_model_plan(), _request_json() (+16 more)

### Community 11 - "write_captions"
Cohesion: 0.21
Nodes (16): _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions(), _events() (+8 more)

### Community 12 - "with"
Cohesion: 0.06
Nodes (33): OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL, WRITER_MODEL, writer_model, jobs, probe (+25 more)

## Knowledge Gaps
- **106 isolated node(s):** `default`, `description`, `options`, `type`, `description` (+101 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 188 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `make_plan()` connect `make_plan` to `test_sources_planner.py`, `array / copy`, `argparse / pathlib`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **What connects `default`, `description`, `options` to the rest of the system?**
  _106 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_sources_planner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06060606060606061 - nodes in this community are weakly interconnected._
- **Why does `generate()` connect `argparse / pathlib` to `test_sources_planner.py`, `difflib / re`, `array / copy`, `analyze_source_speech`, `make_plan`, `write_captions`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `default / description` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `render_plan()` connect `array / copy` to `make_plan`, `argparse / pathlib`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Should `difflib / re` be split into smaller, more focused modules?**
  _Cohesion score 0.09080841638981174 - nodes in this community are weakly interconnected._
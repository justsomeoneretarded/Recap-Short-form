# Graph Report - Recap-Short-form  (2026-11-05)

## Corpus Check
- 38 files · ~51,657 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 428 nodes · 972 edges · 18 communities (11 shown, 7 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `430f949f`
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
- sources.py
- recap-shorts
- json
- test_workflows.py

## God Nodes (most connected - your core abstractions)
1. `render_plan()` - 30 edges
2. `make_plan()` - 30 edges
3. `generate()` - 23 edges
4. `write_captions()` - 22 edges
5. `analyze_source_speech()` - 21 edges
6. `Eight reference Shorts: evidence and production guide` - 21 edges
7. `resolve_source()` - 18 edges
8. `synthesize_plan()` - 17 edges
9. `_normalize_model_plan()` - 15 edges
10. `index_source()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `test_reverse_chronology_within_a_beat_is_rejected()` --calls--> `_normalize_model_plan()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/planner.py
- `test_unknown_scene_id_is_never_substituted()` --calls--> `_normalize_model_plan()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/planner.py
- `_normalize_speech()` --calls--> `_normalize_model_plan()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/planner.py
- `test_bad_segment_limits_rejected()` --calls--> `_segments()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/sources.py
- `test_compression_preserves_selected_native_quote_and_uses_remaining_narration_budget()` --calls--> `make_plan()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/planner.py

## Import Cycles
- None detected.

## Communities (18 total, 7 thin omitted)

### Community 0 - "test_sources_planner.py"
Cohesion: 0.08
Nodes (34): _normalize_speech(), _production_three_candidates(), _speech_candidate(), _speech_plan(), test_bad_segment_limits_rejected(), test_compression_preserves_selected_native_quote_and_uses_remaining_narration_budget(), test_compression_undershoot_uses_full_storyboard_retry(), test_dialogue_words_do_not_expand_the_narration_budget() (+26 more)

### Community 1 - "default / description"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "difflib / re"
Cohesion: 0.08
Nodes (32): _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions(), _align_script() (+24 more)

### Community 3 - "array / copy"
Cohesion: 0.12
Nodes (30): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+22 more)

### Community 4 - "generate-shorts.yml / concurrency"
Cohesion: 0.05
Nodes (38): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+30 more)

### Community 5 - "argparse / pathlib"
Cohesion: 0.12
Nodes (13): generate(), stage(), main(), assign_timeline(), request_config(), excerpt(), probe(), run() (+5 more)

### Community 6 - "Evidence-linked story beats and timed edit decisions / Source-grounded"
Cohesion: 0.07
Nodes (27): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+19 more)

### Community 7 - "analyze_source_speech"
Cohesion: 0.11
Nodes (17): analyze_source_speech(), _candidate(), _number(), _transcribe(), fixture(), segment(), test_bad_word_bounds_and_confidence(), test_cache_and_content_invalidation() (+9 more)

### Community 8 - "ci.yml / jobs"
Cohesion: 0.14
Nodes (13): jobs, test, name, on, permissions, contents, run, uses (+5 more)

### Community 9 - "sources.py"
Cohesion: 0.13
Nodes (14): _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url(), index_source(), resolve_source(), _run(), _segments() (+6 more)

### Community 11 - "json"
Cohesion: 0.17
Nodes (15): _compress_narration(), _describe(), _key(), make_plan(), _NarrationTimingExcess, _normalize_model_plan(), _request_json(), _require_models() (+7 more)

## Knowledge Gaps
- **80 isolated node(s):** `name`, `description`, `required`, `type`, `description` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 158 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `make_plan()` connect `json` to `sources.py`, `array / copy`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _80 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_sources_planner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08244680851063829 - nodes in this community are weakly interconnected._
- **Why does `generate()` connect `argparse / pathlib` to `difflib / re`, `array / copy`, `analyze_source_speech`, `sources.py`, `json`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `default / description` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `render_plan()` connect `array / copy` to `sources.py`, `json`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `difflib / re` be split into smaller, more focused modules?**
  _Cohesion score 0.08385744234800839 - nodes in this community are weakly interconnected._
# Graph Report - Recap-Short-form  (2026-11-05)

## Corpus Check
- 38 files · ~53,530 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 449 nodes · 1015 edges · 21 communities (12 shown, 9 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d90cc0fe`
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
- write_captions
- json

## God Nodes (most connected - your core abstractions)
1. `make_plan()` - 31 edges
2. `render_plan()` - 30 edges
3. `generate()` - 23 edges
4. `write_captions()` - 22 edges
5. `analyze_source_speech()` - 21 edges
6. `Eight reference Shorts: evidence and production guide` - 21 edges
7. `synthesize_plan()` - 18 edges
8. `resolve_source()` - 18 edges
9. `_normalize_model_plan()` - 15 edges
10. `index_source()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `test_imported_audio_preserves_every_word_without_models()` --calls--> `synthesize_plan()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/voice.py
- `test_caption_offsets_and_script_punctuation()` --calls--> `write_captions()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/captions.py
- `test_asr_cannot_silently_drop_script_words()` --calls--> `_align_script()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/voice.py
- `test_chunking_preserves_long_script()` --calls--> `_chunks()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/voice.py
- `test_dialogue_with_reviewed_timings_preserves_source_span()` --calls--> `synthesize_plan()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/voice.py

## Import Cycles
- None detected.

## Communities (21 total, 9 thin omitted)

### Community 0 - "test_sources_planner.py"
Cohesion: 0.08
Nodes (44): validate_storyboard(), _is_compression(), _normalize_speech(), _plan(), _production_three_candidates(), _speech_candidate(), _speech_plan(), test_bad_segment_limits_rejected() (+36 more)

### Community 1 - "default / description"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "difflib / re"
Cohesion: 0.09
Nodes (25): _align_script(), _chunks(), _contextual_units(), _duration(), _integer_words(), _lexical(), _normal(), _run() (+17 more)

### Community 3 - "array / copy"
Cohesion: 0.15
Nodes (26): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+18 more)

### Community 4 - "generate-shorts.yml / concurrency"
Cohesion: 0.05
Nodes (39): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+31 more)

### Community 5 - "argparse / pathlib"
Cohesion: 0.11
Nodes (14): generate(), stage(), main(), assign_timeline(), request_config(), excerpt(), probe(), run() (+6 more)

### Community 6 - "Evidence-linked story beats and timed edit decisions / Source-grounded"
Cohesion: 0.07
Nodes (27): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+19 more)

### Community 7 - "analyze_source_speech"
Cohesion: 0.11
Nodes (17): analyze_source_speech(), _candidate(), _number(), _transcribe(), fixture(), segment(), test_bad_word_bounds_and_confidence(), test_cache_and_content_invalidation() (+9 more)

### Community 8 - "ci.yml / jobs"
Cohesion: 0.12
Nodes (15): jobs, test, name, on, permissions, contents, name, run (+7 more)

### Community 9 - "sources.py"
Cohesion: 0.13
Nodes (14): _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url(), index_source(), resolve_source(), _run(), _segments() (+6 more)

### Community 11 - "write_captions"
Cohesion: 0.19
Nodes (17): _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions(), _events() (+9 more)

### Community 17 - "json"
Cohesion: 0.16
Nodes (14): _compress_narration(), _compression_schema(), _describe(), _key(), make_plan(), _NarrationTimingExcess, _normalize_model_plan(), _request_json() (+6 more)

## Knowledge Gaps
- **83 isolated node(s):** `name`, `description`, `required`, `type`, `description` (+78 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 164 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `make_plan()` connect `json` to `test_sources_planner.py`, `sources.py`, `array / copy`, `argparse / pathlib`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _83 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_sources_planner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07581453634085213 - nodes in this community are weakly interconnected._
- **Why does `generate()` connect `argparse / pathlib` to `test_sources_planner.py`, `difflib / re`, `array / copy`, `analyze_source_speech`, `sources.py`, `write_captions`, `json`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `default / description` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `render_plan()` connect `array / copy` to `json`, `sources.py`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Should `difflib / re` be split into smaller, more focused modules?**
  _Cohesion score 0.09407665505226481 - nodes in this community are weakly interconnected._
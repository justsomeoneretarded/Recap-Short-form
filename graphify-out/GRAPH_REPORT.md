# Graph Report - Recap-Short-form  (2026-11-05)

## Corpus Check
- 35 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 324 nodes · 690 edges · 12 communities (9 shown, 3 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- base64 / hashlib
- default / description
- difflib / re
- array / copy
- generate-shorts.yml / concurrency
- argparse / pathlib
- Evidence-linked story beats and timed edit decisions / Source-grounded
- Concrete action or contradiction before a dossier / Automatic speech a
- ci.yml / jobs
- recap-shorts

## God Nodes (most connected - your core abstractions)
1. `render_plan()` - 28 edges
2. `generate()` - 21 edges
3. `Eight reference Shorts: evidence and production guide` - 21 edges
4. `resolve_source()` - 18 edges
5. `make_plan()` - 18 edges
6. `synthesize_plan()` - 17 edges
7. `index_source()` - 15 edges
8. `Upstream technology comparison for Recap Shorts` - 14 edges
9. `write_captions()` - 12 edges
10. `_run()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `test_chunking_preserves_long_script()` --calls--> `_chunks()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/voice.py
- `test_dialogue_with_reviewed_timings_preserves_source_span()` --calls--> `synthesize_plan()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/voice.py
- `test_imported_audio_preserves_every_word_without_models()` --calls--> `synthesize_plan()`  [EXTRACTED]
  tests/test_voice_captions.py → shorts_pipeline/voice.py
- `test_ffmpeg_detector_debounces_adjacent_frame_triggers()` --calls--> `_ffmpeg_boundaries()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/sources.py
- `test_reverse_chronology_within_a_beat_is_rejected()` --calls--> `_normalize_model_plan()`  [EXTRACTED]
  tests/test_sources_planner.py → shorts_pipeline/planner.py

## Import Cycles
- None detected.

## Communities (12 total, 3 thin omitted)

### Community 0 - "base64 / hashlib"
Cohesion: 0.08
Nodes (35): _describe(), _key(), make_plan(), _normalize_model_plan(), _request_json(), _require_models(), validate_storyboard(), _adaptive_boundaries() (+27 more)

### Community 1 - "default / description"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "difflib / re"
Cohesion: 0.10
Nodes (24): _ass_time(), _groups(), _srt_time(), _wrap(), write_captions(), _align_script(), _chunks(), _duration() (+16 more)

### Community 3 - "array / copy"
Cohesion: 0.14
Nodes (22): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+14 more)

### Community 4 - "generate-shorts.yml / concurrency"
Cohesion: 0.06
Nodes (35): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+27 more)

### Community 5 - "argparse / pathlib"
Cohesion: 0.12
Nodes (13): generate(), stage(), main(), assign_timeline(), request_config(), excerpt(), probe(), run() (+5 more)

### Community 6 - "Evidence-linked story beats and timed edit decisions / Source-grounded"
Cohesion: 0.10
Nodes (18): faster-whisper small.en, resemble-ai/chatterbox, Chatterbox Nano, Original and multilingual Chatterbox variants, Chatterbox Turbo, SYSTRAN/faster-whisper, Female reference sample, FFmpeg/FFmpeg (+10 more)

### Community 7 - "Concrete action or contradiction before a dossier / Automatic speech a"
Cohesion: 0.20
Nodes (9): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+1 more)

### Community 8 - "ci.yml / jobs"
Cohesion: 0.15
Nodes (12): jobs, test, name, on, permissions, contents, run, uses (+4 more)

## Knowledge Gaps
- **76 isolated node(s):** `default`, `description`, `options`, `type`, `description` (+71 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 122 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate()` connect `argparse / pathlib` to `base64 / hashlib`, `difflib / re`, `array / copy`?**
  _High betweenness centrality (0.003) - this node is a cross-community bridge._
- **What connects `default`, `description`, `options` to the rest of the system?**
  _76 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `base64 / hashlib` be split into smaller, more focused modules?**
  _Cohesion score 0.07539682539682539 - nodes in this community are weakly interconnected._
- **Why does `render_plan()` connect `array / copy` to `base64 / hashlib`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `default / description` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `synthesize_plan()` connect `difflib / re` to `base64 / hashlib`, `array / copy`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **Should `difflib / re` be split into smaller, more focused modules?**
  _Cohesion score 0.0975609756097561 - nodes in this community are weakly interconnected._

Semantic extraction used the host agent. Token usage was not exposed by the agent tool and is not accounted in the zero-valued CLI cost counters.

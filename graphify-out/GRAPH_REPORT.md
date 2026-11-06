# Graph Report - recap-short-form  (2026-11-06)

## Corpus Check
- 93 files · ~76,803 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 1019 nodes · 2212 edges · 58 communities (42 shown, 16 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7079bee4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- api
- inputs
- test_voice_captions.py
- render_plan
- env
- Upstream technology comparison for Recap Shorts
- Eight reference Shorts: evidence and production guide
- analyze_source_speech
- steps
- re
- recap-shorts
- screening.py
- with
- Runtime setup verification
- steps
- phase0-probes.yml
- writers-local
- cli.py
- env
- interpolation
- locate
- on
- youtube
- Reference video measurements
- warp_proxy.sh
- AGENTS.md
- voices/README.md
- V1.md
- V2.md
- V3.md
- V4.md
- V5.md
- V6.md
- V7.md
- V8.md
- research.py
- steps
- placement.py
- discovery.py
- shorts-research.yml
- make_plan
- _speech_plan
- write_captions
- parametrize
- Runtime setup verification
- Top10-Movies model and implementation review
- resemble-ai/chatterbox
- json
- test_scene_limit_fails_before_any_model_calls
- arcs.py
- research
- jobs
- with
- shorts-research.yml
- discover
- test_index_fallback_explains_method_and_preserves_every_time_span

## God Nodes (most connected - your core abstractions)
1. `make_plan()` - 34 edges
2. `render_plan()` - 30 edges
3. `generate()` - 23 edges
4. `MovieTranscript` - 23 edges
5. `write_captions()` - 23 edges
6. `Eight reference Shorts: evidence and production guide` - 23 edges
7. `analyze_source_speech()` - 21 edges
8. `_compress_narration()` - 20 edges
9. `resolve_source()` - 18 edges
10. `screen()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Local setup` --references--> `words()`  [INFERRED]
  README.md → scripts/phase0/probe_locate.py
- `3. Captions match the broad look but omit observed opacity changes` --references--> `write_captions()`  [INFERRED]
  docs/fidelity-review.md → shorts_pipeline/captions.py
- `1. Automatic stories exclude original-dialogue passages` --references--> `_normalize_model_plan()`  [INFERRED]
  docs/fidelity-review.md → shorts_pipeline/planner.py
- `2. Important actions and their framing are not verified through time` --references--> `_describe()`  [INFERRED]
  docs/fidelity-review.md → shorts_pipeline/planner.py
- `2. Important actions and their framing are not verified through time` --references--> `_normalize_model_plan()`  [INFERRED]
  docs/fidelity-review.md → shorts_pipeline/planner.py

## Import Cycles
- None detected.

## Communities (58 total, 16 thin omitted)

### Community 0 - "api"
Cohesion: 0.10
Nodes (22): _sentence_pattern(), _is_compression(), _production_six_candidate(), _production_three_candidates(), test_compression_undershoot_exhausts_text_attempts_before_full_storyboard_retry(), api(), test_invalid_compression_is_bounded_diagnosed_and_never_cached(), api() (+14 more)

### Community 1 - "inputs"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "test_voice_captions.py"
Cohesion: 0.09
Nodes (26): _align_script(), _chunks(), _contextual_units(), _duration(), _integer_words(), _lexical(), _normal(), _run() (+18 more)

### Community 3 - "render_plan"
Cohesion: 0.14
Nodes (26): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+18 more)

### Community 4 - "env"
Cohesion: 0.05
Nodes (39): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+31 more)

### Community 5 - "Upstream technology comparison for Recap Shorts"
Cohesion: 0.14
Nodes (11): faster-whisper small.en, SYSTRAN/faster-whisper, FFmpeg/FFmpeg, Zulko/moviepy, ollama/ollama, mlfoundations/open_clip, Breakthrough/PySceneDetect, remotion-dev/remotion (+3 more)

### Community 6 - "Eight reference Shorts: evidence and production guide"
Cohesion: 0.20
Nodes (9): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+1 more)

### Community 7 - "analyze_source_speech"
Cohesion: 0.13
Nodes (16): analyze_source_speech(), _candidate(), _transcribe(), fixture(), segment(), test_bad_word_bounds_and_confidence(), test_cache_and_content_invalidation(), test_english_candidate_relative_words_and_complete_evidence() (+8 more)

### Community 8 - "steps"
Cohesion: 0.12
Nodes (15): jobs, test, name, on, permissions, contents, name, run (+7 more)

### Community 9 - "re"
Cohesion: 0.05
Nodes (50): films(), out_dir(), slug(), write_report(), crop(), duplicate_ratio(), ffmpeg_method(), main() (+42 more)

### Community 11 - "screening.py"
Cohesion: 0.07
Nodes (28): excerpt(), probe(), run(), active_box(), classify_text(), _inside(), mirrored(), narration_suspected() (+20 more)

### Community 12 - "with"
Cohesion: 0.06
Nodes (33): OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL, WRITER_MODEL, writer_model, jobs, probe (+25 more)

### Community 13 - "Runtime setup verification"
Cohesion: 0.15
Nodes (10): Complete automatic workflow, Completed component checks, Model and repair findings, Scope and remaining review, Validation record, Generate a Short on GitHub, Local setup, Models and timing (+2 more)

### Community 14 - "steps"
Cohesion: 0.29
Nodes (16): steps, steps, steps, continue-on-error, if, name, run, timeout-minutes (+8 more)

### Community 15 - "phase0-probes.yml"
Cohesion: 0.14
Nodes (13): concurrency, cancel-in-progress, group, env, PROBE_OUT, jobs, research, name (+5 more)

### Community 16 - "writers-local"
Cohesion: 0.18
Nodes (11): OLLAMA_MODELS, SCRIPT_MODEL, writers-local, model, fail-fast, matrix, env, if (+3 more)

### Community 17 - "cli.py"
Cohesion: 0.17
Nodes (12): generate(), stage(), main(), run_discover(), run_research(), assign_timeline(), request_config(), write_json() (+4 more)

### Community 18 - "env"
Cohesion: 0.40
Nodes (5): GITHUB_TOKEN, OPENSUBTITLES_API_KEY, TMDB_READ_TOKEN, YOUTUBE_COOKIES, env

### Community 19 - "interpolation"
Cohesion: 0.40
Nodes (5): if, needs, runs-on, timeout-minutes, interpolation

### Community 20 - "locate"
Cohesion: 0.40
Nodes (5): locate, if, needs, runs-on, timeout-minutes

### Community 21 - "on"
Cohesion: 0.40
Nodes (5): on, push, workflow_dispatch, branches, paths

### Community 22 - "youtube"
Cohesion: 0.50
Nodes (4): youtube, if, runs-on, timeout-minutes

### Community 35 - "research.py"
Cohesion: 0.07
Nodes (31): choose_subtitle(), choose_tmdb_result(), title_ok(), _fold(), Http, MovieQuery, opensubtitles_file(), parse_movie() (+23 more)

### Community 36 - "steps"
Cohesion: 0.19
Nodes (16): steps, GITHUB_TOKEN, MOVIE, OPENSUBTITLES_API_KEY, TMDB_READ_TOKEN, steps, steps, continue-on-error (+8 more)

### Community 37 - "placement.py"
Cohesion: 0.06
Nodes (36): description_chapters(), place_segments(), _seconds(), segments_from_chapters(), segments_from_dialogue_gaps(), split(), Cue, locate_captions() (+28 more)

### Community 38 - "discovery.py"
Cohesion: 0.08
Nodes (23): best_format(), build_queries(), candidate(), Candidate, comment_peaks(), discover(), fold(), heatmap_peaks() (+15 more)

### Community 39 - "shorts-research.yml"
Cohesion: 0.20
Nodes (10): movie, description, required, type, on, push, workflow_dispatch, branches (+2 more)

### Community 40 - "make_plan"
Cohesion: 0.17
Nodes (13): 1. Automatic stories exclude original-dialogue passages, 2. Important actions and their framing are not verified through time, _compress_narration(), _compression_schema(), _describe(), _key(), make_plan(), _NarrationTimingExcess (+5 more)

### Community 41 - "_speech_plan"
Cohesion: 0.24
Nodes (14): _normalize_speech(), _speech_candidate(), _speech_plan(), test_compression_preserves_selected_native_quote_and_uses_remaining_narration_budget(), api(), test_dialogue_words_do_not_expand_the_narration_budget(), test_source_speech_cache_binds_exact_candidates_and_writer_request(), api() (+6 more)

### Community 42 - "write_captions"
Cohesion: 0.16
Nodes (19): 3. Captions match the broad look but omit observed opacity changes, Standalone Shorts fidelity review, Voice pace and sound: what can and cannot be concluded, _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text() (+11 more)

### Community 43 - "parametrize"
Cohesion: 0.12
Nodes (18): validate_storyboard(), _segments(), _plan(), test_bad_segment_limits_rejected(), test_dialogue_requires_one_contiguous_source_span(), test_duplicate_beat_ids_rejected(), test_ffmpeg_detector_debounces_adjacent_frame_triggers(), test_narration_only_remains_available_with_or_without_source_speech() (+10 more)

### Community 44 - "Runtime setup verification"
Cohesion: 0.25
Nodes (7): Actual model files and download footprint, Feasible validation recommendation, Nano, Ollama availability and capacity, Original, Pinned Chatterbox package, Runtime setup verification

### Community 45 - "Top10-Movies model and implementation review"
Cohesion: 0.25
Nodes (7): Dependency/runtime pins worth retaining, Licenses actually evidenced in this checkout, Model choices actually configured, Recommendation, Reusable code ideas and changes needed for Shorts, Source acquisition and workflow, Top10-Movies model and implementation review

### Community 46 - "resemble-ai/chatterbox"
Cohesion: 0.29
Nodes (7): resemble-ai/chatterbox, Chatterbox Nano, Original and multilingual Chatterbox variants, Chatterbox Turbo, Female reference sample, Kit Laser reference sample, Warguy reference sample

### Community 47 - "json"
Cohesion: 0.18
Nodes (12): _number(), _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url(), index_source(), resolve_source(), _run() (+4 more)

### Community 48 - "test_scene_limit_fails_before_any_model_calls"
Cohesion: 0.50
Nodes (3): test_failed_download_is_not_cached(), fail(), test_scene_limit_fails_before_any_model_calls()

### Community 49 - "arcs.py"
Cohesion: 0.17
Nodes (15): _arc_score(), attach_dialogue(), build_arcs(), candidate_arcs(), choose_arcs(), describe(), merge_duplicates(), Unit (+7 more)

### Community 50 - "research"
Cohesion: 0.22
Nodes (10): strategy, research, movie, needs, runs-on, strategy, timeout-minutes, fail-fast (+2 more)

### Community 52 - "jobs"
Cohesion: 0.22
Nodes (9): jobs, movies, summary, outputs, runs-on, list, if, needs (+1 more)

### Community 53 - "with"
Cohesion: 0.22
Nodes (9): with, cache, key, name, path, pattern, python-version, restore-keys (+1 more)

### Community 54 - "shorts-research.yml"
Cohesion: 0.29
Nodes (6): concurrency, cancel-in-progress, group, name, permissions, contents

### Community 55 - "discover"
Cohesion: 0.29
Nodes (7): env, needs, runs-on, timeout-minutes, HF_HOME, SHORTS_CPU_THREADS, discover

## Knowledge Gaps
- **212 isolated node(s):** `name`, `description`, `required`, `type`, `branches` (+207 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 397 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_discover()` connect `cli.py` to `arcs.py`, `screening.py`, `placement.py`, `discovery.py`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _212 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `api` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._
- **Why does `research()` connect `research.py` to `json`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Should `inputs` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `run_research()` connect `cli.py` to `research.py`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Should `test_voice_captions.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09191919191919191 - nodes in this community are weakly interconnected._
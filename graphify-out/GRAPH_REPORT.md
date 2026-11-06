# Graph Report - recap-short-form  (2026-11-06)

## Corpus Check
- 82 files · ~68,978 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 844 nodes · 1793 edges · 44 communities (30 shown, 14 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 48 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d0879b36`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_sources_planner.py
- inputs
- test_voice_captions.py
- render_plan
- env
- test_workflows.py
- Eight reference Shorts: evidence and production guide
- analyze_source_speech
- steps
- re
- recap-shorts
- write_captions
- with
- Runtime setup verification
- steps
- phase0-probes.yml
- writers-local
- make_plan
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
- with
- test_locate.py
- cli.py
- sources.py
- api
- _production_three_candidates
- parametrize
- test_scene_limit_fails_before_any_model_calls

## God Nodes (most connected - your core abstractions)
1. `make_plan()` - 34 edges
2. `render_plan()` - 30 edges
3. `generate()` - 23 edges
4. `write_captions()` - 23 edges
5. `Eight reference Shorts: evidence and production guide` - 23 edges
6. `analyze_source_speech()` - 21 edges
7. `_compress_narration()` - 20 edges
8. `resolve_source()` - 18 edges
9. `_normalize_model_plan()` - 18 edges
10. `synthesize_plan()` - 18 edges

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

## Communities (44 total, 14 thin omitted)

### Community 0 - "test_sources_planner.py"
Cohesion: 0.23
Nodes (17): _normalize_speech(), _plan(), _speech_candidate(), _speech_plan(), test_compression_preserves_selected_native_quote_and_uses_remaining_narration_budget(), test_dialogue_requires_one_contiguous_source_span(), test_dialogue_words_do_not_expand_the_narration_budget(), test_duplicate_beat_ids_rejected() (+9 more)

### Community 1 - "inputs"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "test_voice_captions.py"
Cohesion: 0.09
Nodes (25): _align_script(), _chunks(), _contextual_units(), _duration(), _integer_words(), _lexical(), _normal(), _run() (+17 more)

### Community 3 - "render_plan"
Cohesion: 0.12
Nodes (26): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+18 more)

### Community 4 - "env"
Cohesion: 0.05
Nodes (39): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+31 more)

### Community 6 - "Eight reference Shorts: evidence and production guide"
Cohesion: 0.06
Nodes (34): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+26 more)

### Community 7 - "analyze_source_speech"
Cohesion: 0.10
Nodes (17): analyze_source_speech(), _candidate(), _number(), _transcribe(), fixture(), segment(), test_bad_word_bounds_and_confidence(), test_cache_and_content_invalidation() (+9 more)

### Community 8 - "steps"
Cohesion: 0.12
Nodes (15): jobs, test, name, on, permissions, contents, name, run (+7 more)

### Community 9 - "re"
Cohesion: 0.06
Nodes (49): films(), out_dir(), slug(), write_report(), crop(), duplicate_ratio(), ffmpeg_method(), main() (+41 more)

### Community 11 - "write_captions"
Cohesion: 0.18
Nodes (18): 3. Captions match the broad look but omit observed opacity changes, _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions() (+10 more)

### Community 12 - "with"
Cohesion: 0.06
Nodes (33): OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL, WRITER_MODEL, writer_model, jobs, probe (+25 more)

### Community 13 - "Runtime setup verification"
Cohesion: 0.10
Nodes (17): Actual model files and download footprint, Feasible validation recommendation, Nano, Ollama availability and capacity, Original, Pinned Chatterbox package, Runtime setup verification, Complete automatic workflow (+9 more)

### Community 14 - "steps"
Cohesion: 0.29
Nodes (16): steps, steps, steps, continue-on-error, if, name, run, timeout-minutes (+8 more)

### Community 15 - "phase0-probes.yml"
Cohesion: 0.14
Nodes (13): concurrency, cancel-in-progress, group, env, PROBE_OUT, jobs, research, name (+5 more)

### Community 16 - "writers-local"
Cohesion: 0.18
Nodes (11): OLLAMA_MODELS, SCRIPT_MODEL, writers-local, model, fail-fast, matrix, env, if (+3 more)

### Community 17 - "make_plan"
Cohesion: 0.12
Nodes (19): 1. Automatic stories exclude original-dialogue passages, 2. Important actions and their framing are not verified through time, Standalone Shorts fidelity review, Voice pace and sound: what can and cannot be concluded, _compress_narration(), _compression_schema(), _describe(), _key() (+11 more)

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
Nodes (30): choose_subtitle(), choose_tmdb_result(), title_ok(), _fold(), Http, MovieQuery, opensubtitles_file(), parse_movie() (+22 more)

### Community 36 - "with"
Cohesion: 0.04
Nodes (48): concurrency, cancel-in-progress, group, MOVIE, OPENSUBTITLES_API_KEY, TMDB_READ_TOKEN, movie, jobs (+40 more)

### Community 37 - "test_locate.py"
Cohesion: 0.13
Nodes (15): Cue, locate_captions(), MovieTranscript, parse_cues(), _seconds(), timed_words(), tokens(), _movie() (+7 more)

### Community 38 - "cli.py"
Cohesion: 0.15
Nodes (15): generate(), stage(), main(), run_research(), assign_timeline(), request_config(), excerpt(), probe() (+7 more)

### Community 39 - "sources.py"
Cohesion: 0.15
Nodes (14): _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url(), index_source(), resolve_source(), _run(), _segments() (+6 more)

### Community 40 - "api"
Cohesion: 0.12
Nodes (12): _sentence_pattern(), _production_six_candidate(), test_narration_only_remains_available_with_or_without_source_speech(), test_plan_cache_binds_source_and_models_and_preserves_review_status(), api(), test_production_seven_short_payoff_uses_the_existing_hard_admission_limit(), test_production_six_repair_uses_bounded_natural_sentences_and_preserves_all_anchors(), api() (+4 more)

### Community 41 - "_production_three_candidates"
Cohesion: 0.21
Nodes (12): _is_compression(), _production_three_candidates(), api(), test_compression_undershoot_exhausts_text_attempts_before_full_storyboard_retry(), api(), test_invalid_compression_is_bounded_diagnosed_and_never_cached(), api(), test_production_four_two_word_anchor_requires_joint_storyboard_retry() (+4 more)

### Community 42 - "parametrize"
Cohesion: 0.20
Nodes (7): test_bad_segment_limits_rejected(), test_plan_cache_changes_when_an_omitted_model_default_changes(), test_remote_sources_require_https_without_embedded_credentials(), test_vision_empty_length_response_retries_without_using_thinking(), generate(), test_vision_two_failed_responses_leave_no_description_cache(), test_writer_context_budget_rejects_large_notes_or_descriptions_before_writer_call()

### Community 43 - "test_scene_limit_fails_before_any_model_calls"
Cohesion: 0.50
Nodes (3): test_failed_download_is_not_cached(), fail(), test_scene_limit_fails_before_any_model_calls()

## Knowledge Gaps
- **202 isolated node(s):** `name`, `description`, `required`, `type`, `branches` (+197 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 339 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `make_plan()` connect `make_plan` to `re`, `sources.py`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _202 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `inputs` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `generate()` connect `cli.py` to `test_voice_captions.py`, `render_plan`, `analyze_source_speech`, `sources.py`, `re`, `write_captions`, `make_plan`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Should `test_voice_captions.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09302325581395349 - nodes in this community are weakly interconnected._
- **Why does `render_plan()` connect `render_plan` to `make_plan`, `re`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Should `render_plan` be split into smaller, more focused modules?**
  _Cohesion score 0.12210915818686402 - nodes in this community are weakly interconnected._
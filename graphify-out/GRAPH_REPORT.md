# Graph Report - recap-short-form  (2026-11-06)

## Corpus Check
- 97 files · ~81,369 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 1101 nodes · 2429 edges · 63 communities (47 shown, 16 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 69 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `82847623`
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
- pathlib
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
- test_sources_planner.py
- writer.py
- __init__.py
- Runtime setup verification
- Top10-Movies model and implementation review
- resemble-ai/chatterbox
- parametrize
- test_scene_limit_fails_before_any_model_calls
- arcs.py
- research
- jobs
- with
- voice
- discover
- __init__.py
- compilations.py
- _production_three_candidates
- test_locate.py
- write

## God Nodes (most connected - your core abstractions)
1. `make_plan()` - 34 edges
2. `MovieTranscript` - 30 edges
3. `render_plan()` - 30 edges
4. `write_captions()` - 26 edges
5. `generate()` - 23 edges
6. `Eight reference Shorts: evidence and production guide` - 23 edges
7. `analyze_source_speech()` - 21 edges
8. `_compress_narration()` - 20 edges
9. `synthesize_plan()` - 18 edges
10. `YouTube` - 18 edges

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

## Communities (63 total, 16 thin omitted)

### Community 0 - "api"
Cohesion: 0.13
Nodes (11): _production_six_candidate(), test_plan_cache_binds_source_and_models_and_preserves_review_status(), api(), test_production_seven_short_payoff_uses_the_existing_hard_admission_limit(), test_production_six_repair_uses_bounded_natural_sentences_and_preserves_all_anchors(), api(), test_real_gemma_seven_word_bounty_fits_existing_three_point_four_second_admission(), test_real_gemma_underfill_uses_second_text_attempt_to_restore_supported_fact() (+3 more)

### Community 1 - "inputs"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "test_voice_captions.py"
Cohesion: 0.06
Nodes (43): 3. Captions match the broad look but omit observed opacity changes, _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions() (+35 more)

### Community 3 - "render_plan"
Cohesion: 0.08
Nodes (39): apply_tempo(), _duration(), forced_align(), synthesize_voiceover(), tempo_for(), voice_beats(), write_short_captions(), allocate_shots() (+31 more)

### Community 4 - "env"
Cohesion: 0.05
Nodes (39): concurrency, cancel-in-progress, group, HF_HOME, OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL (+31 more)

### Community 5 - "Upstream technology comparison for Recap Shorts"
Cohesion: 0.14
Nodes (11): faster-whisper small.en, SYSTRAN/faster-whisper, FFmpeg/FFmpeg, Zulko/moviepy, ollama/ollama, mlfoundations/open_clip, Breakthrough/PySceneDetect, remotion-dev/remotion (+3 more)

### Community 6 - "Eight reference Shorts: evidence and production guide"
Cohesion: 0.20
Nodes (9): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+1 more)

### Community 7 - "pathlib"
Cohesion: 0.06
Nodes (33): analyze_source_speech(), _candidate(), _number(), _transcribe(), _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url() (+25 more)

### Community 8 - "steps"
Cohesion: 0.12
Nodes (15): jobs, test, name, on, permissions, contents, name, run (+7 more)

### Community 9 - "re"
Cohesion: 0.06
Nodes (49): films(), out_dir(), slug(), write_report(), crop(), duplicate_ratio(), ffmpeg_method(), main() (+41 more)

### Community 11 - "screening.py"
Cohesion: 0.10
Nodes (24): active_box(), classify_text(), _inside(), mirrored(), narration_suspected(), _norm(), _ocr(), read_text() (+16 more)

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
Cohesion: 0.10
Nodes (20): generate(), stage(), main(), _preview(), run_discover(), run_research(), run_voice(), run_write() (+12 more)

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
Cohesion: 0.22
Nodes (18): steps, GITHUB_TOKEN, MOVIE, OPENSUBTITLES_API_KEY, TMDB_READ_TOKEN, steps, steps, continue-on-error (+10 more)

### Community 37 - "placement.py"
Cohesion: 0.17
Nodes (11): Cue, parse_cues(), flush(), _seconds(), timed_words(), tokens(), _audio(), place_candidates() (+3 more)

### Community 38 - "discovery.py"
Cohesion: 0.07
Nodes (25): description_chapters(), _seconds(), best_format(), build_queries(), candidate(), Candidate, comment_peaks(), discover() (+17 more)

### Community 39 - "shorts-research.yml"
Cohesion: 0.12
Nodes (16): concurrency, cancel-in-progress, group, movie, description, required, type, name (+8 more)

### Community 40 - "make_plan"
Cohesion: 0.12
Nodes (19): 1. Automatic stories exclude original-dialogue passages, 2. Important actions and their framing are not verified through time, Standalone Shorts fidelity review, Voice pace and sound: what can and cannot be concluded, _compress_narration(), _compression_schema(), _describe(), _key() (+11 more)

### Community 41 - "test_sources_planner.py"
Cohesion: 0.23
Nodes (17): _normalize_speech(), _plan(), _speech_candidate(), _speech_plan(), test_compression_preserves_selected_native_quote_and_uses_remaining_narration_budget(), test_dialogue_requires_one_contiguous_source_span(), test_dialogue_words_do_not_expand_the_narration_budget(), test_duplicate_beat_ids_rejected() (+9 more)

### Community 42 - "writer.py"
Cohesion: 0.29
Nodes (10): Brief, build_brief(), check(), _clean_title(), draft(), fix(), judge(), _names() (+2 more)

### Community 43 - "__init__.py"
Cohesion: 0.23
Nodes (7): brief(), FakeLLM, test_brief_has_lines_in_clip_time_budgets_and_clean_titles(), test_check_flags_invented_names_filler_quotes_and_bad_line_ids(), test_write_command_end_to_end_with_fake_model(), __init__(), test_write_short_picks_the_best_draft_and_keeps_the_chosen_line()

### Community 44 - "Runtime setup verification"
Cohesion: 0.25
Nodes (7): Actual model files and download footprint, Feasible validation recommendation, Nano, Ollama availability and capacity, Original, Pinned Chatterbox package, Runtime setup verification

### Community 45 - "Top10-Movies model and implementation review"
Cohesion: 0.25
Nodes (7): Dependency/runtime pins worth retaining, Licenses actually evidenced in this checkout, Model choices actually configured, Recommendation, Reusable code ideas and changes needed for Shorts, Source acquisition and workflow, Top10-Movies model and implementation review

### Community 46 - "resemble-ai/chatterbox"
Cohesion: 0.29
Nodes (7): resemble-ai/chatterbox, Chatterbox Nano, Original and multilingual Chatterbox variants, Chatterbox Turbo, Female reference sample, Kit Laser reference sample, Warguy reference sample

### Community 47 - "parametrize"
Cohesion: 0.20
Nodes (7): test_bad_segment_limits_rejected(), test_narration_only_remains_available_with_or_without_source_speech(), test_plan_cache_changes_when_an_omitted_model_default_changes(), test_remote_sources_require_https_without_embedded_credentials(), test_vision_empty_length_response_retries_without_using_thinking(), generate(), test_vision_two_failed_responses_leave_no_description_cache()

### Community 48 - "test_scene_limit_fails_before_any_model_calls"
Cohesion: 0.50
Nodes (3): test_failed_download_is_not_cached(), fail(), test_scene_limit_fails_before_any_model_calls()

### Community 49 - "arcs.py"
Cohesion: 0.18
Nodes (14): _arc_score(), build_arcs(), candidate_arcs(), choose_arcs(), describe(), merge_duplicates(), Unit, units_from() (+6 more)

### Community 50 - "research"
Cohesion: 0.43
Nodes (8): strategy, movie, strategy, fail-fast, matrix, max-parallel, strategy, strategy

### Community 52 - "jobs"
Cohesion: 0.15
Nodes (13): jobs, movies, research, summary, outputs, runs-on, list, needs (+5 more)

### Community 53 - "with"
Cohesion: 0.22
Nodes (9): with, cache, key, name, path, pattern, python-version, restore-keys (+1 more)

### Community 54 - "voice"
Cohesion: 0.40
Nodes (5): voice, if, needs, runs-on, timeout-minutes

### Community 55 - "discover"
Cohesion: 0.25
Nodes (9): env, needs, runs-on, timeout-minutes, HF_HOME, SHORTS_CPU_THREADS, TORCH_HOME, discover (+1 more)

### Community 56 - "__init__.py"
Cohesion: 0.23
Nodes (7): FakeYouTube, srt(), test_captions_place_clip_then_whisper_fallback_then_cache(), transcribe(), test_compilation_segments_are_placed(), test_without_subtitles_nothing_is_guessed(), vtt()

### Community 58 - "compilations.py"
Cohesion: 0.15
Nodes (10): attach_dialogue(), place_segments(), segments_from_chapters(), segments_from_dialogue_gaps(), split(), MovieTranscript, movie(), test_compilation_segments_are_placed_separately_and_strangers_dropped() (+2 more)

### Community 59 - "_production_three_candidates"
Cohesion: 0.21
Nodes (12): _is_compression(), _production_three_candidates(), api(), test_compression_undershoot_exhausts_text_attempts_before_full_storyboard_retry(), api(), test_invalid_compression_is_bounded_diagnosed_and_never_cached(), api(), test_production_four_two_word_anchor_requires_joint_storyboard_retry() (+4 more)

### Community 60 - "test_locate.py"
Cohesion: 0.35
Nodes (8): locate_captions(), _movie(), _rolling_vtt(), _stamp(), test_clip_is_placed_at_its_movie_time_with_context(), test_rolling_captions_are_not_double_counted(), test_too_little_dialogue_is_reported_not_guessed(), test_unrelated_dialogue_does_not_match()

### Community 62 - "write"
Cohesion: 0.22
Nodes (9): OLLAMA_MODELS, SCRIPT_MODEL, SHORTS_WRITER_MODEL, write, env, if, needs, runs-on (+1 more)

## Knowledge Gaps
- **219 isolated node(s):** `name`, `description`, `required`, `type`, `branches` (+214 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 422 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `make_plan()` connect `make_plan` to `cli.py`, `pathlib`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _219 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `api` be split into smaller, more focused modules?**
  _Cohesion score 0.1323529411764706 - nodes in this community are weakly interconnected._
- **Why does `research()` connect `research.py` to `cli.py`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Should `inputs` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Why does `analyze_source_speech()` connect `pathlib` to `cli.py`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Should `test_voice_captions.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06233538191395961 - nodes in this community are weakly interconnected._
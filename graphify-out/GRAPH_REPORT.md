# Graph Report - recap-short-form  (2026-11-07)

## Corpus Check
- 111 files · ~103,116 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .ttf 2, (none) 1)

## Summary
- 1424 nodes · 3228 edges · 88 communities (65 shown, 23 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 79 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `50fdc1f0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pytest
- voice.py
- write_captions
- subprocess
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
- YouTube
- discovery.py
- shorts-research.yml
- make_plan
- test_sources_planner.py
- test_good_audio_is_heard_again_before_a_new_take_is_made
- covers.py
- Runtime setup verification
- Top10-Movies model and implementation review
- resemble-ai/chatterbox
- placement.py
- parametrize
- api
- research
- jobs
- with
- synthesize_plan
- discover
- narration.py
- arcs.py
- place_candidates
- MovieTranscript
- jobs
- write
- MovieTranscript
- jobs
- compilations.py
- writer.py
- render
- generate-shorts.yml
- env
- with
- write
- finish
- write-story
- render
- install_rife.sh
- discover
- test_sources_planner.py
- test_voice_captions.py
- test_workflows.py
- test_scene_limit_fails_before_any_model_calls
- validate_words
- voice

## God Nodes (most connected - your core abstractions)
1. `make_plan()` - 34 edges
2. `render_plan()` - 30 edges
3. `MovieTranscript` - 28 edges
4. `write_captions()` - 28 edges
5. `YouTube` - 23 edges
6. `Eight reference Shorts: evidence and production guide` - 23 edges
7. `synthesize_plan()` - 22 edges
8. `generate()` - 21 edges
9. `analyze_source_speech()` - 21 edges
10. `screen()` - 20 edges

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

## Communities (88 total, 23 thin omitted)

### Community 0 - "pytest"
Cohesion: 0.08
Nodes (36): build_edl(), choose(), _extra_footage(), _free(), _pieces(), allocate_shots(), _ass_escape(), _attach_narration() (+28 more)

### Community 1 - "voice.py"
Cohesion: 0.24
Nodes (5): _chunks(), _contextual_units(), _lexical(), _normal(), test_chunking_preserves_long_script()

### Community 2 - "write_captions"
Cohesion: 0.18
Nodes (17): 3. Captions match the broad look but omit observed opacity changes, _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions() (+9 more)

### Community 3 - "subprocess"
Cohesion: 0.05
Nodes (44): attention(), _detector(), faces(), filter_graph(), native_size(), plan_shot(), sample(), window_fraction() (+36 more)

### Community 4 - "env"
Cohesion: 0.21
Nodes (12): env, ARC, HF_HOME, LENGTH, MOVIE, NARRATOR, SHORTS_CPU_THREADS, SHORTS_YUNET_MODEL (+4 more)

### Community 5 - "Upstream technology comparison for Recap Shorts"
Cohesion: 0.14
Nodes (11): faster-whisper small.en, SYSTRAN/faster-whisper, FFmpeg/FFmpeg, Zulko/moviepy, ollama/ollama, mlfoundations/open_clip, Breakthrough/PySceneDetect, remotion-dev/remotion (+3 more)

### Community 6 - "Eight reference Shorts: evidence and production guide"
Cohesion: 0.20
Nodes (9): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+1 more)

### Community 7 - "pathlib"
Cohesion: 0.06
Nodes (31): analyze_source_speech(), _candidate(), _number(), _transcribe(), _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url() (+23 more)

### Community 8 - "steps"
Cohesion: 0.12
Nodes (15): jobs, test, name, on, permissions, contents, name, run (+7 more)

### Community 9 - "re"
Cohesion: 0.06
Nodes (49): films(), out_dir(), slug(), write_report(), crop(), duplicate_ratio(), ffmpeg_method(), main() (+41 more)

### Community 11 - "screening.py"
Cohesion: 0.10
Nodes (28): active_box(), classify_text(), _inside(), mirrored(), narration_suspected(), _norm(), _ocr(), read_text() (+20 more)

### Community 12 - "with"
Cohesion: 0.06
Nodes (33): OLLAMA_MAX_LOADED_MODELS, OLLAMA_MODELS, OLLAMA_NUM_PARALLEL, SCRIPT_MODEL, WRITER_MODEL, writer_model, jobs, probe (+25 more)

### Community 13 - "Runtime setup verification"
Cohesion: 0.15
Nodes (10): Complete automatic workflow, Completed component checks, Model and repair findings, Scope and remaining review, Validation record, Generate Shorts on GitHub (one button), Local setup, Models and timing (+2 more)

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
Cohesion: 0.07
Nodes (35): chunk_indexes(), _footage(), generate(), stage(), main(), _package_story(), _preview(), run_discover() (+27 more)

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
Cohesion: 0.08
Nodes (31): choose_subtitle(), choose_tmdb_result(), title_ok(), _fold(), Http, MovieQuery, opensubtitles_file(), parse_movie() (+23 more)

### Community 36 - "steps"
Cohesion: 0.23
Nodes (20): steps, GITHUB_TOKEN, MOVIE, OPENSUBTITLES_API_KEY, TMDB_READ_TOKEN, YOUTUBE_COOKIES, steps, steps (+12 more)

### Community 38 - "discovery.py"
Cohesion: 0.09
Nodes (26): best_format(), build_queries(), candidate(), Candidate, discover(), fold(), heatmap_peaks(), identity() (+18 more)

### Community 39 - "shorts-research.yml"
Cohesion: 0.12
Nodes (16): concurrency, cancel-in-progress, group, movie, description, required, type, name (+8 more)

### Community 40 - "make_plan"
Cohesion: 0.14
Nodes (16): 1. Automatic stories exclude original-dialogue passages, 2. Important actions and their framing are not verified through time, Standalone Shorts fidelity review, Voice pace and sound: what can and cannot be concluded, _compress_narration(), _compression_schema(), _describe(), _key() (+8 more)

### Community 41 - "test_sources_planner.py"
Cohesion: 0.24
Nodes (14): _normalize_speech(), _speech_candidate(), _speech_plan(), test_compression_preserves_selected_native_quote_and_uses_remaining_narration_budget(), api(), test_dialogue_words_do_not_expand_the_narration_budget(), test_source_speech_cache_binds_exact_candidates_and_writer_request(), api() (+6 more)

### Community 43 - "covers.py"
Cohesion: 0.10
Nodes (25): contact_sheet(), _crop(), grab(), _grab_all(), _grade(), hook_words(), make_covers(), source() (+17 more)

### Community 44 - "Runtime setup verification"
Cohesion: 0.25
Nodes (7): Actual model files and download footprint, Feasible validation recommendation, Nano, Ollama availability and capacity, Original, Pinned Chatterbox package, Runtime setup verification

### Community 45 - "Top10-Movies model and implementation review"
Cohesion: 0.25
Nodes (7): Dependency/runtime pins worth retaining, Licenses actually evidenced in this checkout, Model choices actually configured, Recommendation, Reusable code ideas and changes needed for Shorts, Source acquisition and workflow, Top10-Movies model and implementation review

### Community 46 - "resemble-ai/chatterbox"
Cohesion: 0.29
Nodes (7): resemble-ai/chatterbox, Chatterbox Nano, Original and multilingual Chatterbox variants, Chatterbox Turbo, Female reference sample, Kit Laser reference sample, Warguy reference sample

### Community 47 - "placement.py"
Cohesion: 0.30
Nodes (6): comment_peaks(), _media(), place_candidates(), place_clip(), _prefetch(), whisper_words()

### Community 48 - "parametrize"
Cohesion: 0.17
Nodes (8): test_bad_segment_limits_rejected(), test_narration_only_remains_available_with_or_without_source_speech(), test_plan_cache_changes_when_an_omitted_model_default_changes(), test_remote_sources_require_https_without_embedded_credentials(), test_vision_empty_length_response_retries_without_using_thinking(), generate(), test_vision_two_failed_responses_leave_no_description_cache(), test_writer_context_budget_rejects_large_notes_or_descriptions_before_writer_call()

### Community 49 - "api"
Cohesion: 0.15
Nodes (10): _sentence_pattern(), _production_six_candidate(), test_plan_cache_binds_source_and_models_and_preserves_review_status(), api(), test_production_six_repair_uses_bounded_natural_sentences_and_preserves_all_anchors(), api(), test_real_gemma_seven_word_bounty_fits_existing_three_point_four_second_admission(), test_real_gemma_underfill_uses_second_text_attempt_to_restore_supported_fact() (+2 more)

### Community 50 - "research"
Cohesion: 0.29
Nodes (10): strategy, index, movie, slot, strategy, strategy, fail-fast, matrix (+2 more)

### Community 52 - "jobs"
Cohesion: 0.14
Nodes (14): jobs, movies, research, summary, outputs, runs-on, indexes, list (+6 more)

### Community 53 - "with"
Cohesion: 0.20
Nodes (10): with, cache, key, name, node-version, path, pattern, python-version (+2 more)

### Community 54 - "synthesize_plan"
Cohesion: 0.13
Nodes (10): _duration(), _run(), synthesize_plan(), _Synthesizer, _Verifier, voice_reference(), test_dialogue_with_reviewed_timings_preserves_source_span(), test_explicit_reference_directory_has_no_silent_fallback() (+2 more)

### Community 55 - "discover"
Cohesion: 0.25
Nodes (9): env, needs, runs-on, timeout-minutes, HF_HOME, SHORTS_CPU_THREADS, TORCH_HOME, discover (+1 more)

### Community 56 - "narration.py"
Cohesion: 0.08
Nodes (29): apply_tempo(), _duration(), forced_align(), _forced_align(), _mask(), _mms(), _number(), _number_words() (+21 more)

### Community 57 - "arcs.py"
Cohesion: 0.19
Nodes (16): _arc_score(), build_arcs(), candidate_arcs(), choose_arcs(), describe(), merge_duplicates(), Unit, units_from() (+8 more)

### Community 58 - "place_candidates"
Cohesion: 0.20
Nodes (10): FakeYouTube, srt(), test_captions_place_clip_then_whisper_fallback_then_cache(), transcribe(), test_captions_skipped_without_cookies(), test_clips_are_downloaded_ahead_once_each(), download(), test_compilation_segments_are_placed() (+2 more)

### Community 59 - "MovieTranscript"
Cohesion: 0.25
Nodes (3): attach_dialogue(), place_segments(), MovieTranscript

### Community 60 - "jobs"
Cohesion: 0.12
Nodes (16): if, needs, runs-on, concurrency, cancel-in-progress, group, if, needs (+8 more)

### Community 62 - "write"
Cohesion: 0.20
Nodes (10): OLLAMA_MODELS, SCRIPT_MODEL, SHORTS_WRITER_MODEL, write, env, if, name, needs (+2 more)

### Community 63 - "MovieTranscript"
Cohesion: 0.17
Nodes (15): Cue, locate_captions(), parse_cues(), flush(), _seconds(), timed_words(), tokens(), _movie() (+7 more)

### Community 64 - "jobs"
Cohesion: 0.25
Nodes (8): validate, length, movie, narrator, speech_model, outputs, runs-on, timeout-minutes

### Community 65 - "compilations.py"
Cohesion: 0.21
Nodes (9): description_chapters(), _seconds(), segments_from_chapters(), segments_from_dialogue_gaps(), split(), movie(), test_compilation_segments_are_placed_separately_and_strangers_dropped(), test_description_chapters_need_ordered_stamps_from_the_start() (+1 more)

### Community 66 - "writer.py"
Cohesion: 0.08
Nodes (39): Brief, build_brief(), check(), _clean_title(), cleanup(), copies_dialogue(), draft(), _estimate_tokens() (+31 more)

### Community 68 - "render"
Cohesion: 0.25
Nodes (8): SHORTS_RIFE_BUDGET, SHORTS_YUNET_MODEL, render, env, if, needs, runs-on, timeout-minutes

### Community 70 - "generate-shorts.yml"
Cohesion: 0.09
Nodes (22): length, movie, narrator, speech_model, default, description, options, type (+14 more)

### Community 71 - "env"
Cohesion: 0.22
Nodes (21): steps, steps, GITHUB_TOKEN, OPENSUBTITLES_API_KEY, SHORTS_INPUTS, TMDB_READ_TOKEN, YOUTUBE_COOKIES, steps (+13 more)

### Community 72 - "with"
Cohesion: 0.17
Nodes (12): with, cache, compression-level, key, merge-multiple, name, node-version, path (+4 more)

### Community 73 - "write"
Cohesion: 0.33
Nodes (6): write, arcs, if, needs, outputs, runs-on

### Community 74 - "finish"
Cohesion: 0.16
Nodes (15): strategy, voice, arc, aspect, chunk, slot, strategy, fail-fast (+7 more)

### Community 76 - "write-story"
Cohesion: 0.25
Nodes (8): OLLAMA_MODELS, SCRIPT_MODEL, SHORTS_WRITER_MODEL, write-story, env, needs, runs-on, timeout-minutes

### Community 77 - "render"
Cohesion: 0.22
Nodes (9): ASPECT, CHUNK, SHORTS_RIFE_BUDGET, render, env, if, needs, runs-on (+1 more)

### Community 80 - "discover"
Cohesion: 0.33
Nodes (6): needs, outputs, runs-on, timeout-minutes, discover, slots

### Community 81 - "test_sources_planner.py"
Cohesion: 0.17
Nodes (18): validate_storyboard(), _is_compression(), _plan(), _production_three_candidates(), test_compression_undershoot_exhausts_text_attempts_before_full_storyboard_retry(), api(), test_dialogue_requires_one_contiguous_source_span(), test_duplicate_beat_ids_rejected() (+10 more)

### Community 82 - "test_voice_captions.py"
Cohesion: 0.19
Nodes (11): _align_script(), validate_words(), _original_warguy_currency_transcript(), test_asr_cannot_silently_drop_script_words(), test_asr_number_forms_preserve_written_script(), test_caption_offsets_and_script_punctuation(), test_currency_word_omission_without_symbol_is_still_rejected(), test_incomplete_or_invalid_word_timings_rejected() (+3 more)

### Community 83 - "test_workflows.py"
Cohesion: 0.60
Nodes (4): _load(), test_generate_shorts_has_only_the_four_inputs(), test_pipeline_order_and_per_story_matrix(), test_user_text_never_reaches_shell_code_directly()

### Community 84 - "test_scene_limit_fails_before_any_model_calls"
Cohesion: 0.50
Nodes (3): test_failed_download_is_not_cached(), fail(), test_scene_limit_fails_before_any_model_calls()

### Community 85 - "validate_words"
Cohesion: 0.38
Nodes (4): repair_words(), _messy(), test_any_messy_word_timing_becomes_valid_captions(), test_captions_survive_bad_beats_and_report_repairs()

### Community 91 - "voice"
Cohesion: 0.40
Nodes (5): voice, if, needs, runs-on, timeout-minutes

## Knowledge Gaps
- **249 isolated node(s):** `name`, `description`, `required`, `type`, `branches` (+244 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 527 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `place_candidates()` connect `placement.py` to `writer.py`, `YouTube`, `MovieTranscript`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _249 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pytest` be split into smaller, more focused modules?**
  _Cohesion score 0.08306010928961749 - nodes in this community are weakly interconnected._
- **Why does `make_plan()` connect `make_plan` to `test_sources_planner.py`, `writer.py`, `pathlib`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Should `subprocess` be split into smaller, more focused modules?**
  _Cohesion score 0.05348101265822785 - nodes in this community are weakly interconnected._
- **Should `Upstream technology comparison for Recap Shorts` be split into smaller, more focused modules?**
  _Cohesion score 0.1437908496732026 - nodes in this community are weakly interconnected._
- **Should `pathlib` be split into smaller, more focused modules?**
  _Cohesion score 0.05970149253731343 - nodes in this community are weakly interconnected._
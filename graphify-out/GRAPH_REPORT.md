# Graph Report - recap-short-form  (2026-11-06)

## Corpus Check
- 110 files · ~93,994 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .ttf 2, (none) 1)

## Summary
- 1311 nodes · 2981 edges · 88 communities (68 shown, 20 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 76 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `664c5d10`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pytest
- YouTube
- test_voice_captions.py
- render_short.py
- env
- Upstream technology comparison for Recap Shorts
- Eight reference Shorts: evidence and production guide
- pathlib
- steps
- re
- recap-shorts
- render_short.py
- with
- Runtime setup verification
- steps
- phase0-probes.yml
- writers-local
- write_json
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
- reframe.py
- discovery.py
- shorts-research.yml
- make_plan
- test_sources_planner.py
- run_render
- covers.py
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
- subprocess
- publish.py
- place_candidates
- test_sources_planner.py
- placement.py
- write
- MovieTranscript
- jobs
- compilations.py
- writer.py
- api
- render
- cli.py
- generate-shorts.yml
- env
- with
- write
- finish
- synthesize_voiceover
- write-story
- render
- jobs
- install_rife.sh
- discover
- MovieTranscript
- test_workflows.py
- probe
- json
- run_write

## God Nodes (most connected - your core abstractions)
1. `make_plan()` - 34 edges
2. `render_plan()` - 30 edges
3. `MovieTranscript` - 28 edges
4. `write_captions()` - 26 edges
5. `generate()` - 23 edges
6. `Eight reference Shorts: evidence and production guide` - 23 edges
7. `YouTube` - 22 edges
8. `analyze_source_speech()` - 21 edges
9. `_compress_narration()` - 20 edges
10. `with` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Local setup` --references--> `words()`  [INFERRED]
  README.md → scripts/phase0/probe_locate.py
- `1. Automatic stories exclude original-dialogue passages` --references--> `_normalize_model_plan()`  [INFERRED]
  docs/fidelity-review.md → shorts_pipeline/planner.py
- `2. Important actions and their framing are not verified through time` --references--> `_describe()`  [INFERRED]
  docs/fidelity-review.md → shorts_pipeline/planner.py
- `2. Important actions and their framing are not verified through time` --references--> `_normalize_model_plan()`  [INFERRED]
  docs/fidelity-review.md → shorts_pipeline/planner.py
- `2. Important actions and their framing are not verified through time` --references--> `crop_filter()`  [EXTRACTED]
  docs/fidelity-review.md → shorts_pipeline/render.py

## Import Cycles
- None detected.

## Communities (88 total, 20 thin omitted)

### Community 0 - "pytest"
Cohesion: 0.14
Nodes (26): allocate_shots(), _ass_escape(), _attach_narration(), _concat(), _covers(), crop_filter(), _ffmpeg(), _master_audio() (+18 more)

### Community 1 - "YouTube"
Cohesion: 0.20
Nodes (3): YouTube, _media(), test_youtube_budget_stops_requests_and_node_runtime_is_enabled()

### Community 2 - "test_voice_captions.py"
Cohesion: 0.06
Nodes (43): 3. Captions match the broad look but omit observed opacity changes, _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions() (+35 more)

### Community 3 - "render_short.py"
Cohesion: 0.15
Nodes (17): native_size(), _concat(), duplicate_frame_ratio(), _escape(), finish(), finish_aspect(), _loudness(), motion() (+9 more)

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
Nodes (32): analyze_source_speech(), _candidate(), _number(), _transcribe(), _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url() (+24 more)

### Community 8 - "steps"
Cohesion: 0.12
Nodes (15): jobs, test, name, on, permissions, contents, name, run (+7 more)

### Community 9 - "re"
Cohesion: 0.06
Nodes (49): films(), out_dir(), slug(), write_report(), crop(), duplicate_ratio(), ffmpeg_method(), main() (+41 more)

### Community 11 - "render_short.py"
Cohesion: 0.11
Nodes (21): active_box(), classify_text(), _inside(), mirrored(), narration_suspected(), _norm(), _ocr(), read_text() (+13 more)

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

### Community 17 - "write_json"
Cohesion: 0.13
Nodes (15): chunk_indexes(), _footage(), stage(), _preview(), run_discover(), run_edit_plan(), run_finish(), run_package() (+7 more)

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
Cohesion: 0.23
Nodes (20): steps, GITHUB_TOKEN, MOVIE, OPENSUBTITLES_API_KEY, TMDB_READ_TOKEN, YOUTUBE_COOKIES, steps, steps (+12 more)

### Community 37 - "reframe.py"
Cohesion: 0.14
Nodes (13): attention(), _detector(), faces(), filter_graph(), plan_shot(), sample(), window_fraction(), moving_box_frames() (+5 more)

### Community 38 - "discovery.py"
Cohesion: 0.10
Nodes (22): best_format(), build_queries(), candidate(), Candidate, comment_peaks(), discover(), fold(), heatmap_peaks() (+14 more)

### Community 39 - "shorts-research.yml"
Cohesion: 0.12
Nodes (16): concurrency, cancel-in-progress, group, movie, description, required, type, name (+8 more)

### Community 40 - "make_plan"
Cohesion: 0.14
Nodes (16): 1. Automatic stories exclude original-dialogue passages, 2. Important actions and their framing are not verified through time, Standalone Shorts fidelity review, Voice pace and sound: what can and cannot be concluded, _compress_narration(), _compression_schema(), _describe(), _key() (+8 more)

### Community 41 - "test_sources_planner.py"
Cohesion: 0.24
Nodes (14): _normalize_speech(), _speech_candidate(), _speech_plan(), test_compression_preserves_selected_native_quote_and_uses_remaining_narration_budget(), api(), test_dialogue_words_do_not_expand_the_narration_budget(), test_source_speech_cache_binds_exact_candidates_and_writer_request(), api() (+6 more)

### Community 42 - "run_render"
Cohesion: 0.16
Nodes (8): run_render(), build_edl(), choose(), _pieces(), shot_changes(), test_choose_prefers_peaks_keeps_order_and_hits_length(), test_edl_is_continuous_dialogue_in_sync_and_forward_moving(), test_short_footage_is_slowed_gently_not_frozen()

### Community 43 - "covers.py"
Cohesion: 0.23
Nodes (11): contact_sheet(), _crop(), grab(), _grade(), hook_words(), make_covers(), score_frame(), sharpness() (+3 more)

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
Cohesion: 0.17
Nodes (8): test_bad_segment_limits_rejected(), test_narration_only_remains_available_with_or_without_source_speech(), test_plan_cache_changes_when_an_omitted_model_default_changes(), test_remote_sources_require_https_without_embedded_credentials(), test_vision_empty_length_response_retries_without_using_thinking(), generate(), test_vision_two_failed_responses_leave_no_description_cache(), test_writer_context_budget_rejects_large_notes_or_descriptions_before_writer_call()

### Community 48 - "test_scene_limit_fails_before_any_model_calls"
Cohesion: 0.50
Nodes (3): test_failed_download_is_not_cached(), fail(), test_scene_limit_fails_before_any_model_calls()

### Community 49 - "arcs.py"
Cohesion: 0.18
Nodes (14): _arc_score(), build_arcs(), candidate_arcs(), choose_arcs(), describe(), merge_duplicates(), Unit, units_from() (+6 more)

### Community 50 - "research"
Cohesion: 0.42
Nodes (9): strategy, movie, strategy, strategy, fail-fast, matrix, max-parallel, strategy (+1 more)

### Community 52 - "jobs"
Cohesion: 0.15
Nodes (13): jobs, movies, research, summary, outputs, runs-on, list, needs (+5 more)

### Community 53 - "with"
Cohesion: 0.20
Nodes (10): with, cache, key, name, node-version, path, pattern, python-version (+2 more)

### Community 54 - "voice"
Cohesion: 0.40
Nodes (5): voice, if, needs, runs-on, timeout-minutes

### Community 55 - "discover"
Cohesion: 0.25
Nodes (9): env, needs, runs-on, timeout-minutes, HF_HOME, SHORTS_CPU_THREADS, TORCH_HOME, discover (+1 more)

### Community 56 - "subprocess"
Cohesion: 0.15
Nodes (9): _duration(), tempo_for(), voice_beats(), fake_synthesize(), test_preview_mixes_beats_at_their_positions(), test_tempo_speeds_up_slow_takes_only_and_is_capped(), test_voice_beats_merge_scene_narration_and_keep_lines(), test_voiceover_timeline_and_captions() (+1 more)

### Community 57 - "publish.py"
Cohesion: 0.22
Nodes (9): description(), _hashtag(), review(), review_html(), tags(), title_options(), write_package(), test_review_flags_fake_60fps_and_loudness() (+1 more)

### Community 58 - "place_candidates"
Cohesion: 0.22
Nodes (9): place_candidates(), FakeYouTube, srt(), test_captions_place_clip_then_whisper_fallback_then_cache(), transcribe(), test_captions_skipped_without_cookies(), test_compilation_segments_are_placed(), test_without_subtitles_nothing_is_guessed() (+1 more)

### Community 59 - "test_sources_planner.py"
Cohesion: 0.17
Nodes (18): validate_storyboard(), _is_compression(), _plan(), _production_three_candidates(), test_compression_undershoot_exhausts_text_attempts_before_full_storyboard_retry(), api(), test_dialogue_requires_one_contiguous_source_span(), test_duplicate_beat_ids_rejected() (+10 more)

### Community 60 - "placement.py"
Cohesion: 0.19
Nodes (7): Cue, parse_cues(), flush(), _seconds(), tokens(), whisper_words(), test_tokens_drop_sound_tags_and_speaker_labels()

### Community 62 - "write"
Cohesion: 0.22
Nodes (9): OLLAMA_MODELS, SCRIPT_MODEL, SHORTS_WRITER_MODEL, write, env, if, needs, runs-on (+1 more)

### Community 63 - "MovieTranscript"
Cohesion: 0.30
Nodes (9): locate_captions(), timed_words(), _movie(), _rolling_vtt(), _stamp(), test_clip_is_placed_at_its_movie_time_with_context(), test_rolling_captions_are_not_double_counted(), test_too_little_dialogue_is_reported_not_guessed() (+1 more)

### Community 64 - "jobs"
Cohesion: 0.25
Nodes (8): validate, length, movie, narrator, speech_model, outputs, runs-on, timeout-minutes

### Community 65 - "compilations.py"
Cohesion: 0.21
Nodes (9): description_chapters(), _seconds(), segments_from_chapters(), segments_from_dialogue_gaps(), split(), movie(), test_compilation_segments_are_placed_separately_and_strangers_dropped(), test_description_chapters_need_ordered_stamps_from_the_start() (+1 more)

### Community 66 - "writer.py"
Cohesion: 0.13
Nodes (24): Brief, build_brief(), check(), _clean_title(), draft(), fix(), judge(), _names() (+16 more)

### Community 67 - "api"
Cohesion: 0.15
Nodes (10): _sentence_pattern(), _production_six_candidate(), test_plan_cache_binds_source_and_models_and_preserves_review_status(), api(), test_production_six_repair_uses_bounded_natural_sentences_and_preserves_all_anchors(), api(), test_real_gemma_seven_word_bounty_fits_existing_three_point_four_second_admission(), test_real_gemma_underfill_uses_second_text_attempt_to_restore_supported_fact() (+2 more)

### Community 68 - "render"
Cohesion: 0.29
Nodes (7): SHORTS_YUNET_MODEL, render, env, if, needs, runs-on, timeout-minutes

### Community 69 - "cli.py"
Cohesion: 0.29
Nodes (8): generate(), main(), assign_timeline(), request_config(), test_automatic_path_keeps_source_speech_through_planning_and_render(), test_complete_cli_path_with_reviewed_audio(), test_failure_records_stage_and_never_claims_success(), test_independent_short_inputs_and_measured_budget()

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

### Community 75 - "synthesize_voiceover"
Cohesion: 0.24
Nodes (6): apply_tempo(), forced_align(), _mms(), synthesize_voiceover(), write_short_captions(), test_render_end_to_end_true_60fps_both_aspects()

### Community 76 - "write-story"
Cohesion: 0.25
Nodes (8): OLLAMA_MODELS, SCRIPT_MODEL, SHORTS_WRITER_MODEL, write-story, env, needs, runs-on, timeout-minutes

### Community 77 - "render"
Cohesion: 0.22
Nodes (9): ASPECT, CHUNK, SHORTS_RIFE_BUDGET, render, env, if, needs, runs-on (+1 more)

### Community 78 - "jobs"
Cohesion: 0.12
Nodes (16): if, needs, runs-on, concurrency, cancel-in-progress, group, if, needs (+8 more)

### Community 80 - "discover"
Cohesion: 0.33
Nodes (6): needs, outputs, runs-on, timeout-minutes, discover, slots

### Community 81 - "MovieTranscript"
Cohesion: 0.24
Nodes (4): attach_dialogue(), place_segments(), MovieTranscript, place_clip()

### Community 82 - "test_workflows.py"
Cohesion: 0.60
Nodes (4): _load(), test_generate_shorts_has_only_the_four_inputs(), test_pipeline_order_and_per_story_matrix(), test_user_text_never_reaches_shell_code_directly()

### Community 83 - "probe"
Cohesion: 0.29
Nodes (6): excerpt(), probe(), _probe(), run(), shot_rate(), test_restored_source_cache_preserves_prepared_excerpt_without_reencoding()

## Knowledge Gaps
- **244 isolated node(s):** `name`, `description`, `required`, `type`, `description` (+239 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 489 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate()` connect `cli.py` to `pytest`, `test_voice_captions.py`, `pathlib`, `make_plan`, `re`, `write_json`, `probe`, `json`, `test_sources_planner.py`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _244 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pytest` be split into smaller, more focused modules?**
  _Cohesion score 0.13588850174216027 - nodes in this community are weakly interconnected._
- **Why does `research()` connect `research.py` to `json`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Should `test_voice_captions.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06233538191395961 - nodes in this community are weakly interconnected._
- **Why does `render_plan()` connect `pytest` to `make_plan`, `json`, `pathlib`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Should `Upstream technology comparison for Recap Shorts` be split into smaller, more focused modules?**
  _Cohesion score 0.1437908496732026 - nodes in this community are weakly interconnected._
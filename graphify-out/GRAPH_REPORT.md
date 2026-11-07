# Graph Report - recap-short-form  (2026-11-07)

## Corpus Check
- 111 files · ~103,040 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .ttf 2, (none) 1)

## Summary
- 1422 nodes · 3225 edges · 91 communities (68 shown, 23 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 79 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d3bb394d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pytest
- reframe.py
- write_captions
- render_short.py
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
- YouTube
- discovery.py
- shorts-research.yml
- make_plan
- test_sources_planner.py
- subprocess
- covers.py
- Runtime setup verification
- Top10-Movies model and implementation review
- resemble-ai/chatterbox
- MovieTranscript
- sources.py
- api
- research
- jobs
- with
- voice.py
- discover
- narration.py
- arcs.py
- place_candidates
- tokens
- jobs
- write
- MovieTranscript
- jobs
- compilations.py
- writer.py
- render
- __init__.py
- generate-shorts.yml
- env
- with
- write
- finish
- env
- write-story
- render
- plan_shots
- install_rife.sh
- discover
- validate_storyboard
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
8. `analyze_source_speech()` - 21 edges
9. `generate()` - 21 edges
10. `_compress_narration()` - 20 edges

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

## Communities (91 total, 23 thin omitted)

### Community 0 - "pytest"
Cohesion: 0.08
Nodes (36): build_edl(), choose(), _extra_footage(), _free(), _pieces(), allocate_shots(), _ass_escape(), _attach_narration() (+28 more)

### Community 1 - "reframe.py"
Cohesion: 0.12
Nodes (15): attention(), _detector(), faces(), filter_graph(), plan_shot(), window_fraction(), moving_box_frames(), test_attention_tracks_the_action_side() (+7 more)

### Community 2 - "write_captions"
Cohesion: 0.17
Nodes (18): 3. Captions match the broad look but omit observed opacity changes, _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions() (+10 more)

### Community 3 - "render_short.py"
Cohesion: 0.16
Nodes (17): native_size(), _concat(), duplicate_frame_ratio(), _escape(), finish(), finish_aspect(), _gray(), _loudness() (+9 more)

### Community 4 - "env"
Cohesion: 0.21
Nodes (12): env, ARC, HF_HOME, LENGTH, MOVIE, NARRATOR, SHORTS_CPU_THREADS, SHORTS_YUNET_MODEL (+4 more)

### Community 5 - "Upstream technology comparison for Recap Shorts"
Cohesion: 0.14
Nodes (11): faster-whisper small.en, SYSTRAN/faster-whisper, FFmpeg/FFmpeg, Zulko/moviepy, ollama/ollama, mlfoundations/open_clip, Breakthrough/PySceneDetect, remotion-dev/remotion (+3 more)

### Community 6 - "Eight reference Shorts: evidence and production guide"
Cohesion: 0.20
Nodes (9): Eight reference Shorts: evidence and production guide, V1 — Everyone Wants Him Dead, V2 — He's Not a Cop at All, V3 — He Was Hired to Kill. Now He's the Prey, V4 — He Was the Target All Along, V5 — One Man vs the Deadliest Fighter, V6 — Rookie Cop Just Learned the Hard Truth, V7 — The Next Assassin Is Already on His Way—but This Father Is Ready (+1 more)

### Community 7 - "analyze_source_speech"
Cohesion: 0.11
Nodes (16): analyze_source_speech(), _candidate(), _number(), _transcribe(), segment(), test_bad_word_bounds_and_confidence(), test_cache_and_content_invalidation(), test_english_candidate_relative_words_and_complete_evidence() (+8 more)

### Community 8 - "steps"
Cohesion: 0.12
Nodes (15): jobs, test, name, on, permissions, contents, name, run (+7 more)

### Community 9 - "re"
Cohesion: 0.06
Nodes (48): films(), out_dir(), slug(), write_report(), crop(), duplicate_ratio(), ffmpeg_method(), main() (+40 more)

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
Cohesion: 0.08
Nodes (28): chunk_indexes(), _footage(), generate(), stage(), main(), _preview(), run_discover(), run_edit_plan() (+20 more)

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
Nodes (32): choose_subtitle(), choose_tmdb_result(), title_ok(), _fold(), Http, MovieQuery, opensubtitles_file(), parse_movie() (+24 more)

### Community 36 - "steps"
Cohesion: 0.23
Nodes (20): steps, GITHUB_TOKEN, MOVIE, OPENSUBTITLES_API_KEY, TMDB_READ_TOKEN, YOUTUBE_COOKIES, steps, steps (+12 more)

### Community 38 - "discovery.py"
Cohesion: 0.08
Nodes (26): best_format(), build_queries(), candidate(), Candidate, comment_peaks(), discover(), fold(), heatmap_peaks() (+18 more)

### Community 39 - "shorts-research.yml"
Cohesion: 0.12
Nodes (16): concurrency, cancel-in-progress, group, movie, description, required, type, name (+8 more)

### Community 40 - "make_plan"
Cohesion: 0.13
Nodes (18): 1. Automatic stories exclude original-dialogue passages, 2. Important actions and their framing are not verified through time, Standalone Shorts fidelity review, Voice pace and sound: what can and cannot be concluded, _compress_narration(), _compression_schema(), _describe(), _key() (+10 more)

### Community 41 - "test_sources_planner.py"
Cohesion: 0.16
Nodes (20): _normalize_speech(), _speech_candidate(), _speech_plan(), test_compression_preserves_selected_native_quote_and_uses_remaining_narration_budget(), test_dialogue_words_do_not_expand_the_narration_budget(), test_narration_only_remains_available_with_or_without_source_speech(), test_plan_cache_changes_when_an_omitted_model_default_changes(), test_remote_sources_require_https_without_embedded_credentials() (+12 more)

### Community 42 - "subprocess"
Cohesion: 0.23
Nodes (5): excerpt(), probe(), _probe(), run(), test_restored_source_cache_preserves_prepared_excerpt_without_reencoding()

### Community 43 - "covers.py"
Cohesion: 0.11
Nodes (25): _package_story(), contact_sheet(), _crop(), grab(), _grab_all(), _grade(), hook_words(), make_covers() (+17 more)

### Community 44 - "Runtime setup verification"
Cohesion: 0.25
Nodes (7): Actual model files and download footprint, Feasible validation recommendation, Nano, Ollama availability and capacity, Original, Pinned Chatterbox package, Runtime setup verification

### Community 45 - "Top10-Movies model and implementation review"
Cohesion: 0.25
Nodes (7): Dependency/runtime pins worth retaining, Licenses actually evidenced in this checkout, Model choices actually configured, Recommendation, Reusable code ideas and changes needed for Shorts, Source acquisition and workflow, Top10-Movies model and implementation review

### Community 46 - "resemble-ai/chatterbox"
Cohesion: 0.29
Nodes (7): resemble-ai/chatterbox, Chatterbox Nano, Original and multilingual Chatterbox variants, Chatterbox Turbo, Female reference sample, Kit Laser reference sample, Warguy reference sample

### Community 47 - "MovieTranscript"
Cohesion: 0.20
Nodes (7): attach_dialogue(), place_segments(), MovieTranscript, _media(), place_clip(), _prefetch(), whisper_words()

### Community 48 - "sources.py"
Cohesion: 0.13
Nodes (16): cookie_file(), _adaptive_boundaries(), _ffmpeg_boundaries(), file_digest(), _https_url(), index_source(), resolve_source(), _run() (+8 more)

### Community 49 - "api"
Cohesion: 0.09
Nodes (23): _sentence_pattern(), _is_compression(), _production_six_candidate(), _production_three_candidates(), api(), test_compression_undershoot_exhausts_text_attempts_before_full_storyboard_retry(), api(), test_invalid_compression_is_bounded_diagnosed_and_never_cached() (+15 more)

### Community 50 - "research"
Cohesion: 0.29
Nodes (10): strategy, index, movie, slot, strategy, strategy, fail-fast, matrix (+2 more)

### Community 52 - "jobs"
Cohesion: 0.14
Nodes (14): jobs, movies, research, summary, outputs, runs-on, indexes, list (+6 more)

### Community 53 - "with"
Cohesion: 0.20
Nodes (10): with, cache, key, name, node-version, path, pattern, python-version (+2 more)

### Community 54 - "voice.py"
Cohesion: 0.11
Nodes (11): _number_words(), _ordinal(), _chunks(), _contextual_units(), _duration(), _integer_words(), _lexical(), _run() (+3 more)

### Community 55 - "discover"
Cohesion: 0.25
Nodes (9): env, needs, runs-on, timeout-minutes, HF_HOME, SHORTS_CPU_THREADS, TORCH_HOME, discover (+1 more)

### Community 56 - "narration.py"
Cohesion: 0.10
Nodes (22): apply_tempo(), _duration(), forced_align(), _forced_align(), _mask(), _mms(), shift_times(), speakable() (+14 more)

### Community 57 - "arcs.py"
Cohesion: 0.19
Nodes (16): _arc_score(), build_arcs(), candidate_arcs(), choose_arcs(), describe(), merge_duplicates(), Unit, units_from() (+8 more)

### Community 58 - "place_candidates"
Cohesion: 0.20
Nodes (11): place_candidates(), FakeYouTube, srt(), test_captions_place_clip_then_whisper_fallback_then_cache(), transcribe(), test_captions_skipped_without_cookies(), test_clips_are_downloaded_ahead_once_each(), download() (+3 more)

### Community 60 - "jobs"
Cohesion: 0.15
Nodes (12): concurrency, cancel-in-progress, group, if, needs, runs-on, timeout-minutes, jobs (+4 more)

### Community 62 - "write"
Cohesion: 0.20
Nodes (10): OLLAMA_MODELS, SCRIPT_MODEL, SHORTS_WRITER_MODEL, write, env, if, name, needs (+2 more)

### Community 63 - "MovieTranscript"
Cohesion: 0.21
Nodes (13): Cue, locate_captions(), parse_cues(), flush(), _seconds(), timed_words(), _movie(), _rolling_vtt() (+5 more)

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

### Community 69 - "__init__.py"
Cohesion: 0.15
Nodes (8): _correlation(), rife_frames_ok(), _streakiness(), fake_synthesize(), test_a_failed_rife_shot_falls_back_to_blending(), test_corrupted_rife_frames_are_rejected(), test_dark_garbage_frames_are_rejected_too(), test_render_end_to_end_true_60fps_both_aspects()

### Community 70 - "generate-shorts.yml"
Cohesion: 0.09
Nodes (22): length, movie, narrator, speech_model, default, description, options, type (+14 more)

### Community 71 - "env"
Cohesion: 0.37
Nodes (14): steps, steps, steps, continue-on-error, id, if, name, run (+6 more)

### Community 72 - "with"
Cohesion: 0.17
Nodes (12): with, cache, compression-level, key, merge-multiple, name, node-version, path (+4 more)

### Community 73 - "write"
Cohesion: 0.33
Nodes (6): write, arcs, if, needs, outputs, runs-on

### Community 74 - "finish"
Cohesion: 0.16
Nodes (15): strategy, voice, arc, aspect, chunk, slot, strategy, fail-fast (+7 more)

### Community 75 - "env"
Cohesion: 0.18
Nodes (11): if, needs, runs-on, steps, GITHUB_TOKEN, OPENSUBTITLES_API_KEY, SHORTS_INPUTS, TMDB_READ_TOKEN (+3 more)

### Community 76 - "write-story"
Cohesion: 0.25
Nodes (8): OLLAMA_MODELS, SCRIPT_MODEL, SHORTS_WRITER_MODEL, write-story, env, needs, runs-on, timeout-minutes

### Community 77 - "render"
Cohesion: 0.22
Nodes (9): ASPECT, CHUNK, SHORTS_RIFE_BUDGET, render, env, if, needs, runs-on (+1 more)

### Community 78 - "plan_shots"
Cohesion: 0.29
Nodes (4): sample(), motion(), plan_shots(), test_rife_only_on_moving_shots_within_budget_and_at_native_size()

### Community 80 - "discover"
Cohesion: 0.33
Nodes (6): needs, outputs, runs-on, timeout-minutes, discover, slots

### Community 81 - "validate_storyboard"
Cohesion: 0.47
Nodes (5): validate_storyboard(), _plan(), test_dialogue_requires_one_contiguous_source_span(), test_duplicate_beat_ids_rejected(), test_storyboard_rejects_invalid_source_ranges()

### Community 82 - "test_voice_captions.py"
Cohesion: 0.10
Nodes (19): _align_script(), _normal(), synthesize_plan(), validate_words(), voice_reference(), test_prefilter_rejects(), _original_warguy_currency_transcript(), test_asr_cannot_silently_drop_script_words() (+11 more)

### Community 83 - "test_workflows.py"
Cohesion: 0.29
Nodes (4): _load(), test_generate_shorts_has_only_the_four_inputs(), test_pipeline_order_and_per_story_matrix(), test_user_text_never_reaches_shell_code_directly()

### Community 84 - "test_scene_limit_fails_before_any_model_calls"
Cohesion: 0.50
Nodes (3): test_failed_download_is_not_cached(), fail(), test_scene_limit_fails_before_any_model_calls()

### Community 85 - "validate_words"
Cohesion: 0.22
Nodes (8): repair_words(), _number(), tidy_words(), test_word_times_are_tidied_for_captions(), _messy(), test_any_messy_word_timing_becomes_valid_captions(), test_captions_survive_bad_beats_and_report_repairs(), test_tidy_keeps_words_inside_the_audio()

### Community 91 - "voice"
Cohesion: 0.40
Nodes (5): voice, if, needs, runs-on, timeout-minutes

## Knowledge Gaps
- **249 isolated node(s):** `recap-shorts`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_MODELS`, `OLLAMA_NUM_PARALLEL`, `SCRIPT_MODEL` (+244 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 526 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `render_short()` connect `render_short.py` to `re`, `subprocess`, `plan_shots`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **What connects `recap-shorts`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_MODELS` to the rest of the system?**
  _249 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pytest` be split into smaller, more focused modules?**
  _Cohesion score 0.08306010928961749 - nodes in this community are weakly interconnected._
- **Why does `plan_shots()` connect `plan_shots` to `reframe.py`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Should `reframe.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12307692307692308 - nodes in this community are weakly interconnected._
- **Why does `place_candidates()` connect `place_candidates` to `YouTube`, `discovery.py`, `re`, `MovieTranscript`, `MovieTranscript`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Should `Upstream technology comparison for Recap Shorts` be split into smaller, more focused modules?**
  _Cohesion score 0.1437908496732026 - nodes in this community are weakly interconnected._
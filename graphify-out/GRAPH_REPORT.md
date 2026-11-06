# Graph Report - recap-short-form  (2026-11-06)

## Corpus Check
- 87 files · ~72,576 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 936 nodes · 2001 edges · 48 communities (34 shown, 14 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 59 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `399418b0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_sources_planner.py
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
- write_captions
- with
- Runtime setup verification
- steps
- phase0-probes.yml
- writers-local
- json
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
- test_discovery.py
- shorts-research.yml
- YouTube
- discovery.py
- placement.py
- test_placement.py
- Runtime setup verification
- Top10-Movies model and implementation review
- resemble-ai/chatterbox

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

## Communities (48 total, 14 thin omitted)

### Community 0 - "test_sources_planner.py"
Cohesion: 0.06
Nodes (55): _is_compression(), _normalize_speech(), _plan(), _production_six_candidate(), _production_three_candidates(), _speech_candidate(), _speech_plan(), test_bad_segment_limits_rejected() (+47 more)

### Community 1 - "inputs"
Cohesion: 0.04
Nodes (45): default, description, options, type, description, required, type, aspect (+37 more)

### Community 2 - "test_voice_captions.py"
Cohesion: 0.09
Nodes (24): _align_script(), _chunks(), _contextual_units(), _integer_words(), _lexical(), _normal(), _run(), synthesize_plan() (+16 more)

### Community 3 - "render_plan"
Cohesion: 0.13
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
Cohesion: 0.06
Nodes (45): films(), out_dir(), slug(), write_report(), crop(), duplicate_ratio(), ffmpeg_method(), main() (+37 more)

### Community 11 - "write_captions"
Cohesion: 0.18
Nodes (18): 3. Captions match the broad look but omit observed opacity changes, _ass_time(), _escape_ass(), _groups(), _srt_time(), _word_fade_text(), _wrap(), write_captions() (+10 more)

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

### Community 17 - "json"
Cohesion: 0.05
Nodes (52): 1. Automatic stories exclude original-dialogue passages, 2. Important actions and their framing are not verified through time, Standalone Shorts fidelity review, Voice pace and sound: what can and cannot be concluded, compress(), main(), prepare_model(), run_probe() (+44 more)

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

### Community 36 - "with"
Cohesion: 0.05
Nodes (51): env, needs, runs-on, steps, strategy, timeout-minutes, GITHUB_TOKEN, HF_HOME (+43 more)

### Community 37 - "test_locate.py"
Cohesion: 0.20
Nodes (10): locate_captions(), MovieTranscript, _movie(), _rolling_vtt(), _stamp(), test_clip_is_placed_at_its_movie_time_with_context(), test_rolling_captions_are_not_double_counted(), test_tokens_drop_sound_tags_and_speaker_labels() (+2 more)

### Community 38 - "test_discovery.py"
Cohesion: 0.15
Nodes (11): comment_peaks(), prefilter(), FakeYouTube, info(), test_comment_peaks_weight_by_likes(), test_compilation_flag_from_title_or_chapters(), test_discover_ranks_and_records_rejections(), test_identity_rejects_other_year_namesake() (+3 more)

### Community 39 - "shorts-research.yml"
Cohesion: 0.12
Nodes (16): concurrency, cancel-in-progress, group, movie, description, required, type, name (+8 more)

### Community 40 - "YouTube"
Cohesion: 0.22
Nodes (5): discover(), YouTube, _audio(), place_candidates(), place_clip()

### Community 41 - "discovery.py"
Cohesion: 0.19
Nodes (9): best_format(), build_queries(), candidate(), Candidate, fold(), heatmap_peaks(), identity(), score() (+1 more)

### Community 42 - "placement.py"
Cohesion: 0.21
Nodes (6): Cue, parse_cues(), _seconds(), timed_words(), tokens(), whisper_words()

### Community 43 - "test_placement.py"
Cohesion: 0.18
Nodes (6): FakeYouTube, srt(), test_captions_place_clip_then_whisper_fallback_then_cache(), transcribe(), test_without_subtitles_nothing_is_guessed(), vtt()

### Community 44 - "Runtime setup verification"
Cohesion: 0.25
Nodes (7): Actual model files and download footprint, Feasible validation recommendation, Nano, Ollama availability and capacity, Original, Pinned Chatterbox package, Runtime setup verification

### Community 45 - "Top10-Movies model and implementation review"
Cohesion: 0.25
Nodes (7): Dependency/runtime pins worth retaining, Licenses actually evidenced in this checkout, Model choices actually configured, Recommendation, Reusable code ideas and changes needed for Shorts, Source acquisition and workflow, Top10-Movies model and implementation review

### Community 46 - "resemble-ai/chatterbox"
Cohesion: 0.29
Nodes (7): resemble-ai/chatterbox, Chatterbox Nano, Original and multilingual Chatterbox variants, Chatterbox Turbo, Female reference sample, Kit Laser reference sample, Warguy reference sample

## Knowledge Gaps
- **212 isolated node(s):** `name`, `description`, `required`, `type`, `branches` (+207 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 376 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate()` connect `json` to `test_voice_captions.py`, `render_plan`, `analyze_source_speech`, `re`, `write_captions`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **What connects `name`, `description`, `required` to the rest of the system?**
  _212 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_sources_planner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05672926447574335 - nodes in this community are weakly interconnected._
- **Why does `research()` connect `research.py` to `json`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Should `inputs` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
- **Should `test_voice_captions.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09291521486643438 - nodes in this community are weakly interconnected._
- **Should `render_plan` be split into smaller, more focused modules?**
  _Cohesion score 0.1331923890063425 - nodes in this community are weakly interconnected._
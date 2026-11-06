# Recap Shorts

A standalone movie recap Shorts pipeline with its own **Generate Shorts** workflow. Choose footage, a story brief, a narrator, a maximum duration, and square or vertical output. This repository does not trigger or depend on long-form generation.

The initial style profile comes from eight owner-supplied references: action before backstory, causal story beats, compact white italic captions, meaningful object/face shots, selected movie dialogue, and story-dependent endings. All supplied exports are 1080×1080, roughly 136–180 seconds. Square is the default; vertical is an explicit option. This is an initial implementation, not a verified recreation of the creator's production process.

Read the [reference analysis](docs/reference-analysis.md), [ten-repository comparison](docs/technology-comparison.md), and [validation record](docs/validation.md). The [complete automatic workflow passed](https://github.com/justsomeoneretarded/Recap-Short-form/actions/runs/42165849180), producing a [14-second Warguy engineering preview](docs/validation-samples/automatic-warguy-pilot.mp4) at1080square/60fps. This test reused verified source analysis and generated a fresh script, voice and edit. The reference already has captions/narration, which overlap the generated content; the sample is not channel-ready.

## Generate Shorts on GitHub (one button)

Open **Actions → Generate Shorts → Run workflow** and fill in four things:

| Field | What to provide |
|---|---|
| Movie | The movie name, optionally with its year: `Nobody (2021)` |
| Narrator | Warguy (default), Kit Laser or Female |
| Length | 60, 90, 120, 150 (default) or 180 seconds per Short |
| Speech model | Original Chatterbox (best), Turbo or Nano (faster) |

Everything else is automatic:

1. **Research** — TMDB (title, cast photos, studio clips), Wikipedia plot, and the movie's full English
   subtitles from OpenSubtitles.
2. **Find clips** on any YouTube channel; reject trailers, recaps, reactions, edits, re-uploads and
   other films; rank by views, subscribers, verified checkmark, likes, Most Replayed and quality.
3. **Place each clip inside the movie** by matching its dialogue (Whisper) against the subtitles;
   compilations are split into scenes.
4. **Screen** downloads: burned-in subtitles, watermarks, promo/end cards, mirrored uploads, narration.
5. **Stories**: nearby scenes become up to five Shorts that never share footage.
6. **Write** each script with Qwen3 14B from the movie's real dialogue (3 drafts, checks + judge, fix-up),
   keeping up to three real movie lines.
7. **Voice** with the chosen narrator at ~195 words/minute; word-exact captions.
8. **Edit and render** square 1080×1080 and vertical 1080×1920 at true 60 fps (RIFE, or motion
   blending as a fallback), smart face/action framing, −14 LUFS.
9. **Package**: covers, title options, description, tags, captions and an automatic quality review.

Download **Artifacts → shorts**: one folder per Short with `final-square.mp4`, `final-vertical.mp4`,
`captions-*.srt`, six covers, `title-options.txt`, `description.txt`, `tags.txt`, `contact-sheet.jpg`
and `review.html`.

Repository secrets: `TMDB_READ_TOKEN` and `OPENSUBTITLES_API_KEY` (required for good stories), and
optionally `YOUTUBE_COOKIES` (a Netscape `cookies.txt` export, ideally from a spare account) to reduce
YouTube's bot checks. No paid APIs are used. Footage belongs to its owners; check your platform's
rules before publishing.

The previous single-source command (`python -m shorts_pipeline generate --request …`) still works locally.

## Local setup

Use Python 3.11 or 3.12, FFmpeg/FFprobe with libass, and DejaVu fonts. Keep this environment separate from Graphify's environment because their dependency versions differ.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e '.[voice,analysis,source,test]'
```

Start Ollama separately, then prepare the configured writer and vision model:

```bash
ollama serve
# In a second terminal, with the environment activated:
python scripts/prepare_models.py
python -m shorts_pipeline doctor
python -m shorts_pipeline generate --request examples/request.json --output output/shorts
```

Edit `examples/request.json` with a real local source path or HTTPS URL. Optional `source_window: [51, 73]` limits analysis to those original-source seconds. Writer/vision names and Ollama URL can be overridden in the request. `target_seconds` is a maximum, not an instruction to stretch speech. Real synthesized duration drives the edit; over-budget speech and insufficient footage fail with an actionable error. A bounded compression pass can rewrite overlong narration against its fixed shot budget; source quotes and selected shots remain unchanged and every attempt is retained for review. Output may be shorter than the chosen maximum. Use a fresh output folder for each run; completed results are preserved rather than overwritten.

For a reviewed edit, add `"plan": "work/storyboard.json"` to the request. A storyboard contains `beats` with `id`, `kind`, `text`, `delivery`, and `shots` (`start`, `end`, optional horizontal `focus_x`). Narration is synthesized with the selected voice. A `dialogue` beat keeps one contiguous source range and its audio. Reviewed narration files can instead be supplied as `audio_path` with relative per-word `words` timestamps. Imported word timings are validated against every written token and the measured audio. Audio paths are resolved relative to the storyboard file.

```json
{
  "beats": [
    {
      "id": "opening", "kind": "narration", "delivery": "dramatic",
      "text": "A stranger steps inside, but someone is already waiting.",
      "shots": [{"start": 2.0, "end": 8.0, "focus_x": 0.5}]
    },
    {
      "id": "exchange", "kind": "dialogue",
      "text": "Replace this with the verified words spoken in the source.",
      "shots": [{"start": 12.0, "end": 16.0}]
    }
  ]
}
```

The example demonstrates the schema; those words are not a claim about your footage. Automatic planning can now select short English source-speech passages from a fully retained ASR transcript. It copies recognized words and source times by ID, reserves their time, and does not invent quotes or speaker identities. Reviewed storyboards remain available for precise dialogue choices and other languages. The source analysis records confidence and rejected candidates; ASR still needs final playback review. Crop focus is explicit per shot, not an automatic guarantee of face tracking. Optional local `music` can be added in the request; source audio is reduced under narration and retained for dialogue.

## Models and timing

- Writer: default `gemma4:12b`, drawing on the Top10 model selection. Its first saved-case draft and repair produced coherent narration covering the suit, broken rule and bounty. The smaller `qwen3:4b-instruct-2507-q4_K_M` remains a legacy option after repeated timing/quality failures. This is a case-specific comparison, not a broad writing benchmark. See the [validation record](docs/validation.md) for full pipeline coverage.
- Frame descriptions: explicit `qwen3-vl:2b-instruct-q4_K_M`, one midpoint image per indexed span. The floating `2b` alias selected a thinking model in a runner test, so the instruction variant is selected deliberately. Scene boundaries prefer PySceneDetect AdaptiveDetector, with a labeled FFmpeg fallback.
- Voice: pinned Chatterbox original/Turbo/Nano and the three existing owner-supplied references. Chatterbox's current upstream README describes it as retired research; the adapter is separate so it can be replaced. The pinned code still declares a mutable Perth dependency; inspect dependency resolution when upgrading.
- Source speech: multilingual faster-whisper `base` CPU int8, configurable through `SHORTS_SOURCE_WHISPER_MODEL`; automatic retained-speech selection currently admits English utterances only. Narration verification: faster-whisper CPU int8, default `base.en`, configurable through `SHORTS_WHISPER_MODEL`. Word timestamps are **ASR estimates**, not WhisperX forced alignment. Captions preserve script text and record timing provenance. The default burn-in progressively reveals and fades white words using the observed reference behavior; SRT remains plain text. Set `caption_style` to `static` in a CLI request to disable that animation.
- Final editing: FFmpeg hard cuts and focus crops; measured two-pass audio normalization targets −14 LUFS and −1.5 dBTP. This is our chosen output policy, not a uniform measured setting in the references.

New model-generated scripts and crops require editorial review. Evidence links and automated checks help identify issues; they do not establish factual accuracy or indistinguishable style.

## Tests and Graphify

```bash
python -m pytest -q
```

Tests include actual synthetic A/V renders with audio checks, captions, duration/coverage validation, source and planner failures, and a complete supplied-audio CLI run. Synthetic tones exercise the machinery; they are not narrator-quality tests.

Graphify 0.9.102 was installed separately with video dependencies and a project Codex skill. Code extraction works offline; its video ingestion transcribes speech. Use it to connect the detailed reference observations with implementation decisions. Install the official package and project integration with:

```bash
uv tool install 'graphifyy[video]==0.9.102'
graphify install --project --platform codex
```

Keep original media and timestamped evidence: a graph is a retrieval aid and can omit details. Source video files remain in the [reference release](https://github.com/justsomeoneretarded/Recap-Short-form/releases/tag/references-v1), rather than in Git history.

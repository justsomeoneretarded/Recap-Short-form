# Validation record

Verified on 5 November 2026 in a Linux CPU workspace (Python 3.12, 3 available CPU cores, 8 GiB cgroup RAM). This record distinguishes running code from configured model paths.

## Completed

- Retrieved all eight original release assets and verified every SHA-256 against GitHub's asset digest; total about 485 MiB. Original files are 1080-square H.264 at reported60fps, with stereo AAC, 135.69–179.53seconds long.
- Transcribed all eight with faster-whisper small.en CPUint8 and retained segment/word evidence. Measured full-file scene-change candidates and full-mix loudness; examined sampled frames. The analysis is detailed but not exhaustive frame-by-frame viewing or subjective audio audition.
- Installed Graphify0.9.102 with video dependencies in a separate environment; verified graph creation/query/path traversal. Code graph extraction produced270nodes before the final merge with reference findings.
- Installed the actual pinned Chatterbox CPU stack and Nano weights. Generated the same complete13-word test sentence with **Warguy (4.76s), KitLaser (4.44s), and Female (4.88s)**. All three passed non-silence/duration checks and ASR script matching. These checks do not establish perceived voice similarity, emotional quality, or suitability for long narration.
- Rendered a6.2second engineering preview combining actual generated Warguy/Nano speech, reference footage and a retained source-dialogue interval, with burned captions, covers, source provenance, audio-endpoint and duration QC. It is a machinery test; the source reference already contains captions and the generic test sentence is not a finished recap script.
- **45 automated tests passed**, including real synthetic A/V tests for narration/dialogue separation, vertical crop, ASS captions, complete CLI generation, failed source acquisition, cached planning, invalid model output, footage coverage, source bounds, preservation of completed output folders, and workflow input handling.
- Reproduced and fixed a real narration-truncation defect caused by short source audio. The reproduction now has2.0seconds of video and2.0seconds of audio instead of0.512seconds of audio. Regression tests cover missing source-bed packets and reject retained dialogue outside recorded source audio.
- `uv pip check` passed for126installed packages after the pinned speech installation.

## Configured but not yet fully validated

- The complete **automatic source → Qwen3-VL frame descriptions → writer → original-Chatterbox narration → final1080render** chain needs a suitable larger runner. Qwen3 4B is the smaller default; Top10's Gemma4 12B remains selectable. Neither writer's comparative script quality has been benchmarked here.
- Original and Turbo Chatterbox inference were not run in this workspace; actual successful narration checks usedNano.
- GitHub runner memory, disk, model downloads and dependency resolution can differ. The workflow validates inputs and checks capacity, verifies a pinned CPUOllama archive, unloads vision before writing, unloads the writer before narration, and records model failures as failures.
- Automatic planning uses one representative frame per indexed span, not continuous motion interpretation. Automatic output currently contains narration beats. Verified original-dialogue inserts, detailed reframing, character identity and nuanced scene logic require a reviewed storyboard.
- SRT/ASS word timings are ASR estimates, not forced alignment. Final voice likeness, narration delivery, source-action correspondence, captions and the complete mix need human playback review before channel publication.

The pipeline produces files and review artifacts. It does not publish to YouTube or promise retention, monetization, or identical output to a reference channel.

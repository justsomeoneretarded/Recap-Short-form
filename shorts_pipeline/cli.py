from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
from .config import request_config, assign_timeline
from .media import probe, write_json, excerpt


def generate(request: dict, workdir: Path, outdir: Path) -> dict:
    from .sources import resolve_source, index_source
    from .planner import make_plan, validate_storyboard
    from .voice import synthesize_plan
    from .captions import write_captions
    from .render import render_plan
    request = request_config(request)
    workdir, outdir = Path(workdir).resolve(), Path(outdir).resolve()
    workdir.mkdir(parents=True,exist_ok=True)
    outdir.mkdir(parents=True,exist_ok=True)
    if (outdir/'final.mp4').exists():
        raise FileExistsError('Output folder already contains final.mp4. Choose a fresh --output folder to preserve the previous completed run.')
    started = time.time()
    status = {'state':'running','stage':'source','started_at_epoch':started}
    def stage(name):
        status['stage'] = name
        write_json(outdir/'status.json',status)
        print(f'Shorts: {name}',flush=True)
    try:
        stage('source')
        source = resolve_source(request['source'],workdir)
        if request.get('source_window'):
            stage('source excerpt')
            source=excerpt(source,workdir,request['source_window'])
        source_info = probe(source)
        if request.get('plan'):
            plan_path = Path(request['plan']).resolve()
            plan = json.loads(plan_path.read_text(encoding='utf-8'))
            # Imported media paths are relative to the storyboard file.
            for beat in plan.get('beats',[]):
                if beat.get('audio_path') and not Path(beat['audio_path']).is_absolute():
                    beat['audio_path'] = str((plan_path.parent/beat['audio_path']).resolve())
            plan = validate_storyboard(plan,source_info['duration'])
            plan['planning_mode'] = 'supplied-storyboard'
        else:
            candidates=[]
            if request['auto_source_speech'] and source_info['has_audio']:
                from .source_speech import analyze_source_speech
                stage('source speech')
                speech=analyze_source_speech(source,workdir)
                write_json(outdir/'source-speech.json',speech)
                candidates=speech['candidates']
            stage('index')
            scenes = index_source(source,workdir)
            stage('storyboard')
            plan = make_plan(request,source,scenes,workdir,source_speech=candidates)
        plan['title'] = request['title']
        plan['source_path'] = str(source)
        plan['source_origin'] = request['source']
        plan['source_window'] = request.get('source_window')
        plan['caption_style'] = request['caption_style']
        write_json(outdir/'request.json',request)
        write_json(outdir/'storyboard.json',plan)
        stage('narration')
        plan = synthesize_plan(plan,request['narrator'],workdir,model=request['tts_model'])
        plan = assign_timeline(plan,request['target_seconds'])
        write_json(outdir/'timeline.json',plan)
        width,height = (1080,1080) if request['aspect']=='square' else (1080,1920)
        # CLI-only small preview override; production workflow uses 1080.
        if request.get('preview_width'):
            width = int(request['preview_width'])
            if not 160 <= width <= 1080 or width%2:
                raise ValueError('preview_width must be an even integer between 160 and1080.')
            height = width if request['aspect']=='square' else round(width*16/9/2)*2
        stage('captions')
        write_captions(plan,outdir,width,height)
        stage('render')
        result = render_plan(plan,source,outdir,width,height,int(request['fps']),
                             Path(request['music']).resolve() if request.get('music') else None)
        (outdir/'script.txt').write_text('\n\n'.join(b.get('text','') for b in plan['beats']),encoding='utf-8')
        (outdir/'description.txt').write_text(plan.get('description',request['brief'])+'\n',encoding='utf-8')
        status.update(state='succeeded',stage='complete',elapsed_seconds=round(time.time()-started,2),duration=plan['duration'])
        write_json(outdir/'status.json',status)
        return result
    except Exception as exc:
        status.update(state='failed',error=str(exc),elapsed_seconds=round(time.time()-started,2))
        write_json(outdir/'status.json',status)
        raise


def run_research(movie: str, workdir: Path, output: Path | None = None) -> dict:
    """Movie name → research.json (+ plot.txt, movie.srt), cached under the work directory."""
    import shutil
    from .research import research
    result = research(movie, Path(workdir).resolve())
    if output:
        output = Path(output).resolve()
        output.mkdir(parents=True, exist_ok=True)
        write_json(output/'research.json', result)
        for name in ('plot.txt', 'movie.srt'):
            source = Path(result['folder'])/name
            if source.exists():
                shutil.copyfile(source, output/name)
    for warning in result['warnings']:
        print(f'Research warning: {warning}', file=sys.stderr)
    return result


def run_discover(movie: str, workdir: Path, output: Path, *, top: int = 12, use_whisper: bool = True,
                 screen: int = 0, length: float = 150) -> dict:
    """Movie name → ranked, placed clip list (clips.json) plus a short summary."""
    from .discovery import YouTube, discover
    from .placement import place_candidates
    research = run_research(movie, workdir, output)
    youtube = YouTube()
    found = discover(research, youtube)
    placed = place_candidates(research, found, youtube, Path(workdir).resolve(), top=top, use_whisper=use_whisper)
    screened = {}
    if screen:
        from .screening import screen_candidates
        screened = {r['id']: r for r in screen_candidates(placed, youtube, Path(workdir).resolve(), top=screen)}
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    write_json(output/'screening.json', list(screened.values()))
    from .arcs import build_arcs
    from .locate import MovieTranscript
    subtitles = research.get('subtitles', {}).get('path')
    transcript = MovieTranscript.from_subtitles(Path(subtitles).read_text(errors='ignore')) if subtitles else None
    stories = build_arcs(placed['clips'], screened, length, transcript)
    write_json(output/'arcs.json', stories)
    write_json(output/'clips.json', {'movie': research['movie']['title'], 'queries': found['queries'],
                                     'placed': placed, 'rejected': found['rejected'], 'errors': found['errors'],
                                     'youtube_log': youtube.log[-200:]})
    rows = [{'rank': i+1, 'id': c['id'], 'title': c['title'][:70], 'channel': c['channel'],
             'views': c['signals']['views'], 'verified': c['signals']['verified'], 'height': c['signals']['height'],
             'score': c['score']['total'], 'compilation': c['compilation'], 'method': c['placement'].get('method'),
             'movie_time': [c['placement'].get('movie_start'), c['placement'].get('movie_end')]
             if c['placement'].get('matched') else None,
             'segments_placed': c['placement'].get('segments_placed'),
             'caption_note': c['placement'].get('caption_error') or (None if c['placement'].get('caption_file')
                                                                    else 'no caption file'),
             'screen': (None if c['id'] not in screened else
                        'pass' if screened[c['id']].get('accept') else '; '.join(screened[c['id']].get('reasons', [])))}
            for i, c in enumerate(placed['clips'])]
    summary = {'movie': research['movie']['title'], 'year': research['movie']['year'],
               'candidates': len(found['candidates']), 'rejected': len(found['rejected']),
               'search_errors': len(found['errors']), 'placed': placed['placed'], 'considered': placed['considered'],
               'arcs': [{'id': a['id'], 'movie': [a['movie_start'], a['movie_end']], 'footage': a['footage_seconds'],
                         'score': a['score'], 'scenes': [s['clip_title'][:40] for s in a['scenes']],
                         'shorter': a['shorter_than_requested']} for a in stories['arcs']],
               'clips': rows}
    write_json(output/'summary.json', summary)
    return summary


def run_write(source: Path, output: Path, *, max_arcs: int = 5, drafts: int = 2, model: str | None = None,
              arc_index: int | None = None) -> dict:
    """discover folder (research.json, arcs.json, movie.srt, plot.txt) → scripts.json + scripts.md."""
    from .locate import MovieTranscript
    from .writer import Ollama, WRITER_MODEL, write_short
    source, output = Path(source).resolve(), Path(output).resolve()
    research = json.loads((source/'research.json').read_text())
    stories = json.loads((source/'arcs.json').read_text())
    srt, plot = source/'movie.srt', source/'plot.txt'
    transcript = MovieTranscript.from_subtitles(srt.read_text(errors='ignore')) if srt.exists() else None
    llm = Ollama(model or WRITER_MODEL)
    output.mkdir(parents=True, exist_ok=True)
    results, lines = [], [f"# {research['movie']['title']} ({research['movie']['year']}) — scripts", '']
    chosen = stories['arcs'][:max_arcs]
    if arc_index is not None:  # one story per machine: the workflow writes stories in parallel
        chosen = chosen[arc_index:arc_index+1]
    for arc in chosen:
        started = time.time()
        result = write_short(arc, research, transcript, llm, plot=plot.read_text() if plot.exists() else '', drafts=drafts)
        result['seconds_to_write'] = round(time.time()-started, 1)
        results.append(result)
        write_json(output/'scripts.json', results)
        script, check = result['script'], result['check']
        lines += [f"## {arc['id']}: {script.get('title')}", '',
                  f"Movie {arc['movie_start']/60:.1f}–{arc['movie_end']/60:.1f} min · {check['total_words']}/{check['target_words']} words · "
                  f"score {check['score']} · issues: {'; '.join(check['issues']) or 'none'} · {result['seconds_to_write']} s", '',
                  f"**Hook:** {script.get('hook')}", '']
        calls = result.get('model_calls') or []
        if calls:
            lines[-2:-2] = [f"Model: {len(calls)} calls · reading prompt {sum(c['prompt_seconds'] for c in calls):.0f} s "
                            f"({sum(c['prompt_tokens'] for c in calls)} tokens) · writing {sum(c['output_seconds'] for c in calls):.0f} s "
                            f"({sum(c['output_tokens'] for c in calls)} tokens)", '']
        for beat in script.get('beats', []):
            if beat.get('kind') == 'dialogue':
                line = result['dialogue_lines'].get(beat.get('line'), {})
                lines.append(f"> 🎬 *movie line:* \"{line.get('text', beat.get('line'))}\"")
            else:
                lines.append(beat.get('text', ''))
        lines += ['', f"*Ending: {script.get('ending')}*", '']
        (output/'scripts.md').write_text('\n'.join(lines))
    return {'movie': research['movie']['title'], 'scripts': [
        {'arc': r['arc'], 'title': r['script'].get('title'), 'words': r['check']['total_words'],
         'target': r['check']['target_words'], 'score': r['check']['score'], 'issues': r['check']['issues'],
         'seconds': r['seconds_to_write']} for r in results]}


def _preview(voiceover: dict, target: Path) -> None:
    """Voice-only listening file: every beat at its timeline position."""
    beats = voiceover['beats']
    if not beats:
        return
    args = ['ffmpeg','-y','-v','error']
    for beat in beats:
        args += ['-i', beat['audio_path']]
    chains = [f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={round(b['timeline_start']*1000)}|"
              f"{round(b['timeline_start']*1000)}[a{i}]" for i, b in enumerate(beats)]
    mix = ''.join(f'[a{i}]' for i in range(len(beats))) + f'amix=inputs={len(beats)}:normalize=0[out]'
    import subprocess
    subprocess.run(args + ['-filter_complex', ';'.join(chains + [mix]), '-map', '[out]', str(target)], check=True)


def run_voice(discover: Path, scripts: Path, output: Path, workdir: Path, *, narrator: str = 'warguy',
              model: str = 'original', max_arcs: int = 5, only: str | None = None) -> dict:
    """Scripts → voiceover.json, preview.wav and captions (square + vertical) per story."""
    from .discovery import YouTube
    from .narration import synthesize_voiceover, write_short_captions
    discover, scripts, output, workdir = (Path(p).resolve() for p in (discover, scripts, output, workdir))
    arcs = {a['id']: a for a in json.loads((discover/'arcs.json').read_text())['arcs']}
    screened = {r['id']: r for r in json.loads((discover/'screening.json').read_text())} \
        if (discover/'screening.json').exists() else {}
    youtube = YouTube()
    rows = []
    chosen = json.loads((scripts/'scripts.json').read_text())
    chosen = [r for r in chosen if r['arc'] == only] if only else chosen[:max_arcs]
    for result in chosen:
        arc = arcs[result['arc']]
        footage = {}
        for scene in arc['scenes']:
            path = screened.get(scene['clip_id'], {}).get('path')
            if not path or not Path(path).exists():
                try:
                    found = youtube.download(scene['clip_id'], workdir/'footage')
                    path = str(found) if found else None
                except RuntimeError as exc:
                    print(f'Footage {scene["clip_id"]} unavailable: {str(exc)[:120]}', file=sys.stderr)
                    path = None
            if path:
                footage[scene['clip_id']] = path
        voiceover = synthesize_voiceover(result, footage, arc, narrator, workdir, model)
        folder = output/result['arc']
        (folder/'audio').mkdir(parents=True, exist_ok=True)
        import shutil
        for beat in voiceover['beats']:  # bundle audio so another machine can render from this folder
            local = folder/'audio'/f"{beat['id']}{Path(beat['audio_path']).suffix}"
            shutil.copyfile(beat['audio_path'], local)
            beat['audio_path'] = str(local)
        write_json(folder/'voiceover.json', {**voiceover, 'beats': [
            {**b, 'audio_path': str(Path(b['audio_path']).relative_to(folder))} for b in voiceover['beats']]})
        _preview(voiceover, folder/'preview.wav')
        for aspect in ('square','vertical'):
            write_short_captions(voiceover, folder/f'captions-{aspect}', aspect=aspect)
        rows.append({'arc': result['arc'], 'title': result['script'].get('title'), 'seconds': voiceover['duration'],
                     'wpm': voiceover['words_per_minute'], 'beats': len(voiceover['beats']),
                     'movie_lines': sum(1 for b in voiceover['beats'] if b['kind'] == 'dialogue'),
                     'tempo': [b.get('tempo') for b in voiceover['beats'] if b['kind'] == 'narration'],
                     'timing': sorted({b.get('timing_provenance') or '' for b in voiceover['beats']})})
    write_json(output/'summary.json', rows)
    return {'voiced': rows}


def run_render(discover: Path, voice: Path, output: Path, workdir: Path, *,
               aspects: tuple[str, ...] = ('square', 'vertical'), interpolation: str = 'auto') -> dict:
    """Voiced stories → edit decision list → final-square.mp4 / final-vertical.mp4 per story."""
    from .discovery import YouTube
    from .edit import build_edl, shot_changes
    from .render_short import render_short
    discover, voice, output, workdir = (Path(p).resolve() for p in (discover, voice, output, workdir))
    arcs = {a['id']: a for a in json.loads((discover/'arcs.json').read_text())['arcs']}
    screened = {r['id']: r for r in json.loads((discover/'screening.json').read_text())} \
        if (discover/'screening.json').exists() else {}
    youtube, rows = YouTube(), []
    for path in sorted(voice.glob('*/voiceover.json')):
        folder = path.parent
        voiceover = json.loads(path.read_text())
        for beat in voiceover['beats']:
            beat['audio_path'] = str((folder/beat['audio_path']).resolve())
        arc = arcs[voiceover['arc']]
        footage, cuts = {}, {}
        for scene in arc['scenes']:
            clip = screened.get(scene['clip_id'], {}).get('path')
            if not clip or not Path(clip).exists():
                found = youtube.download(scene['clip_id'], workdir/'footage')
                clip = str(found) if found else None
            if not clip:
                raise RuntimeError(f"Footage {scene['clip_id']} could not be downloaded")
            footage[scene['clip_id']] = clip
            cuts[scene['clip_id']] = shot_changes(Path(clip), scene['clip_start'], scene['clip_end'])
        edl = build_edl(arc, voiceover, footage, cuts)
        captions = {a: folder/f'captions-{a}'/'captions.ass' for a in aspects
                    if (folder/f'captions-{a}'/'captions.ass').exists()}
        reports = render_short(edl, voiceover, screened, captions, output/voiceover['arc'], aspects=aspects,
                               interpolation=interpolation)
        rows.append({'arc': voiceover['arc'], 'shots': edl['shot_count'], 'median_shot': edl['median_shot'],
                     'outputs': {a: {k: r[k] for k in ('duration', 'width', 'height', 'fps', 'integrated_lufs',
                                                        'true_peak_db', 'duplicate_frames', 'modes', 'interpolation')}
                                 for a, r in reports.items()}})
    write_json(output/'summary.json', rows)
    return {'rendered': rows}


def run_package(discover: Path, scripts: Path, voice: Path, render: Path, output: Path, *, length: float = 150) -> dict:
    """Everything needed to upload each Short, in one folder per story."""
    import shutil
    from .covers import contact_sheet, make_covers
    from .publish import write_package
    discover, scripts, voice, render, output = (Path(p).resolve() for p in (discover, scripts, voice, render, output))
    research = json.loads((discover/'research.json').read_text())
    arcs = {a['id']: a for a in json.loads((discover/'arcs.json').read_text())['arcs']}
    clips = {c['id']: c for c in json.loads((discover/'clips.json').read_text())['placed']['clips']} \
        if (discover/'clips.json').exists() else {}
    results = {r['arc']: r for r in json.loads((scripts/'scripts.json').read_text())}
    try:
        from .screening import read_text as text_reader
    except Exception:  # noqa: BLE001 - OCR is optional for cover scoring
        text_reader = None
    try:
        from .reframe import faces as face_finder
    except Exception:  # noqa: BLE001
        face_finder = None
    rows = []
    for render_json in sorted(render.glob('*/render.json')):
        arc_id = render_json.parent.name
        rendered = json.loads(render_json.read_text())
        outputs, edl = rendered['outputs'], rendered['edl']
        voiceover = json.loads((voice/arc_id/'voiceover.json').read_text())
        folder = output/arc_id
        folder.mkdir(parents=True, exist_ok=True)
        for aspect, info in outputs.items():
            shutil.copyfile(info['path'] if Path(info['path']).exists() else render_json.parent/f'final-{aspect}.mp4',
                            folder/f'final-{aspect}.mp4')
            srt = voice/arc_id/f'captions-{aspect}'/'captions.srt'
            if srt.exists():
                shutil.copyfile(srt, folder/f'captions-{aspect}.srt')
        main_video = folder/('final-vertical.mp4' if (folder/'final-vertical.mp4').exists() else 'final-square.mp4')
        made = make_covers(main_video, edl, results[arc_id]['script'].get('title', ''), folder,
                           aspects=tuple(outputs), text_reader=text_reader, face_finder=face_finder)
        sheet = contact_sheet(main_video, edl['duration'], folder/'contact-sheet.jpg')
        pack = write_package(folder, result=results[arc_id], research=research, arc=arcs[arc_id], clips=clips,
                             voiceover=voiceover, edl=edl, render=outputs, covers=made, sheet=str(sheet),
                             target_seconds=length)
        rows.append({'arc': arc_id, 'title': pack['titles'][0] if pack['titles'] else None, 'verdict': pack['verdict'],
                     'warnings': [f"{c['check']}: {c['detail']}" for c in pack['checks'] if c['status'] != 'pass']})
    write_json(output/'summary.json', rows)
    return {'packages': rows}


def _footage(clip_ids, screened: dict, workdir: Path) -> dict[str, str]:
    from .discovery import YouTube
    youtube, footage = None, {}
    for clip_id in dict.fromkeys(clip_ids):
        path = screened.get(clip_id, {}).get('path')
        if not path or not Path(path).exists():
            youtube = youtube or YouTube()
            found = youtube.download(clip_id, Path(workdir)/'footage')
            path = str(found) if found else None
        if not path:
            raise RuntimeError(f'Footage {clip_id} could not be downloaded')
        footage[clip_id] = path
    return footage


def chunk_indexes(edit: dict, chunks: int, chunk: int) -> list[int]:
    """Contiguous runs of shots (few clips to download per machine) with balanced work.

    Moving shots (RIFE) weigh ~30x a calm shot (blend), so chunks split by expected cost, not count.
    """
    from .render_short import CALM_MOTION
    shots = edit['edl']['shots']
    cost = [s['duration'] * (30 if edit['plans'][str(i)].get('motion', 99) >= CALM_MOTION else 1)
            for i, s in enumerate(shots)]
    total, bounds, running = sum(cost) or 1.0, [0], 0.0
    for i, c in enumerate(cost):
        running += c
        if len(bounds) < chunks and running >= total * len(bounds) / chunks:
            bounds.append(i + 1)
    bounds += [len(shots)] * (chunks + 1 - len(bounds))
    return list(range(bounds[chunk], bounds[chunk + 1]))


def run_edit_plan(discover: Path, voice: Path, output: Path, workdir: Path) -> dict:
    from .edit import build_edl, shot_changes
    from .render_short import plan_shots
    discover, voice, output, workdir = (Path(p).resolve() for p in (discover, voice, output, workdir))
    arcs = {a['id']: a for a in json.loads((discover/'arcs.json').read_text())['arcs']}
    screened = {r['id']: r for r in json.loads((discover/'screening.json').read_text())} \
        if (discover/'screening.json').exists() else {}
    rows = []
    for path in sorted(voice.glob('*/voiceover.json')):
        voiceover = json.loads(path.read_text())
        arc = arcs[voiceover['arc']]
        footage = _footage([s['clip_id'] for s in arc['scenes']], screened, workdir)
        cuts = {s['clip_id']: shot_changes(Path(footage[s['clip_id']]), s['clip_start'], s['clip_end']) for s in arc['scenes']}
        edl = build_edl(arc, voiceover, footage, cuts)
        plans = plan_shots(edl, screened)
        for shot in edl['shots']:
            shot.pop('source', None)  # machine-specific; each render machine downloads its own copy
        write_json(output/voiceover['arc']/'edit.json', {'arc': voiceover['arc'], 'edl': edl, 'plans': plans})
        rows.append({'arc': voiceover['arc'], 'shots': edl['shot_count'],
                     'moving_shots': sum(1 for p in plans.values() if p['motion'] >= 2.5)})
    return {'planned': rows}


def run_render_part(edit_dir: Path, arc: str, aspect: str, chunk: int, chunks: int, output: Path, workdir: Path) -> dict:
    from .render_short import render_parts
    edit = json.loads((Path(edit_dir)/arc/'edit.json').read_text())
    indexes = chunk_indexes(edit, chunks, chunk)
    footage = _footage([edit['edl']['shots'][i]['clip_id'] for i in indexes], {}, Path(workdir).resolve())
    for i in indexes:
        edit['edl']['shots'][i]['source'] = footage[edit['edl']['shots'][i]['clip_id']]
    folder = Path(output).resolve()/arc
    rows = render_parts(edit['edl'], edit['plans'], aspect, indexes, folder)
    write_json(folder/f'{aspect}-chunk-{chunk}.json', rows)
    return {'arc': arc, 'aspect': aspect, 'chunk': chunk, 'shots': len(indexes),
            'rife': sum(1 for r in rows if r['interpolation'] == 'rife')}


def run_finish(edit_dir: Path, voice: Path, parts: Path, arc: str, output: Path) -> dict:
    from .render_short import SIZES, finish_aspect
    edit = json.loads((Path(edit_dir)/arc/'edit.json').read_text())
    folder = Path(voice).resolve()/arc
    voiceover = json.loads((folder/'voiceover.json').read_text())
    for beat in voiceover['beats']:
        beat['audio_path'] = str((folder/beat['audio_path']).resolve())
    parts_folder = Path(parts).resolve()/arc
    out = Path(output).resolve()/arc
    out.mkdir(parents=True, exist_ok=True)
    reports = {}
    for aspect in SIZES:
        rows = [r for p in sorted(parts_folder.glob(f'{aspect}-chunk-*.json')) for r in json.loads(p.read_text())]
        if not rows:
            continue
        captions = folder/f'captions-{aspect}'/'captions.ass'
        reports[aspect] = finish_aspect(edit['edl'], voiceover, aspect, parts_folder,
                                        captions if captions.exists() else None, out, rows)
    write_json(out/'render.json', {'edl': edit['edl'], 'outputs': reports, 'plans': edit['plans']})
    return {'arc': arc, 'outputs': {a: {k: r[k] for k in ('duration', 'fps', 'duplicate_frames', 'integrated_lufs',
                                                          'interpolation_reasons')} for a, r in reports.items()}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Generate a standalone movie recap Short.')
    sub = parser.add_subparsers(dest='command',required=True)
    make = sub.add_parser('generate')
    make.add_argument('--request',required=True,type=Path)
    make.add_argument('--workdir',type=Path,default=Path('work/shorts'))
    make.add_argument('--output',type=Path,default=Path('output/shorts'))
    find = sub.add_parser('research', help='Resolve a movie by name and gather plot and full subtitles.')
    find.add_argument('--movie',required=True,help="Movie name, optionally with its year: 'Nobody (2021)'")
    find.add_argument('--workdir',type=Path,default=Path('work/shorts'))
    find.add_argument('--output',type=Path,default=None,help='Optional folder for research.json, plot.txt and movie.srt')
    scout = sub.add_parser('discover', help='Research a movie, find and rank scene clips, and place them in the film.')
    scout.add_argument('--movie',required=True)
    scout.add_argument('--workdir',type=Path,default=Path('work/shorts'))
    scout.add_argument('--output',type=Path,default=Path('output/discover'))
    scout.add_argument('--top',type=int,default=12,help='How many ranked clips to place in the movie')
    scout.add_argument('--no-whisper',action='store_true',help='Skip audio transcription for clips without captions')
    scout.add_argument('--screen',type=int,default=0,help='Download and screen this many top clips (0 = skip)')
    scout.add_argument('--length',type=float,default=150,help='Target Short length in seconds, used to group stories')
    pen = sub.add_parser('write', help='Write scripts for the stories found by discover.')
    pen.add_argument('--from',dest='source',type=Path,default=Path('output/discover'),help='discover output folder')
    pen.add_argument('--output',type=Path,default=Path('output/write'))
    pen.add_argument('--max-arcs',type=int,default=5)
    pen.add_argument('--drafts',type=int,default=2)
    pen.add_argument('--arc-index',type=int,default=None,help='Write only this story (0-based), for parallel machines')
    pen.add_argument('--model',default=None,help='Ollama writer model (default qwen3:14b)')
    speak = sub.add_parser('voice', help='Voice the written scripts and make captions.')
    speak.add_argument('--discover',type=Path,default=Path('output/discover'))
    speak.add_argument('--scripts',type=Path,default=Path('output/write'))
    speak.add_argument('--output',type=Path,default=Path('output/voice'))
    speak.add_argument('--workdir',type=Path,default=Path('work/shorts'))
    speak.add_argument('--narrator',default='warguy',choices=['warguy','kit-laser','female'])
    speak.add_argument('--tts-model',default='original',choices=['original','turbo','nano'])
    speak.add_argument('--max-arcs',type=int,default=5)
    speak.add_argument('--arc',default=None,help='Voice only this story id (e.g. arc2)')
    cut = sub.add_parser('render', help='Edit and render the voiced Shorts (square + vertical, 60 fps).')
    cut.add_argument('--discover',type=Path,default=Path('output/discover'))
    cut.add_argument('--voice',type=Path,default=Path('output/voice'))
    cut.add_argument('--output',type=Path,default=Path('output/render'))
    cut.add_argument('--workdir',type=Path,default=Path('work/shorts'))
    cut.add_argument('--aspects',default='square,vertical')
    cut.add_argument('--interpolation',default='auto',choices=['auto','rife','blend'])
    box = sub.add_parser('package', help='Covers, titles, description, tags and a quality review per Short.')
    box.add_argument('--discover',type=Path,default=Path('output/discover'))
    box.add_argument('--scripts',type=Path,default=Path('output/write'))
    box.add_argument('--voice',type=Path,default=Path('output/voice'))
    box.add_argument('--render',type=Path,default=Path('output/render'))
    box.add_argument('--output',type=Path,default=Path('output/shorts'))
    box.add_argument('--length',type=float,default=150)
    planp = sub.add_parser('edit-plan', help='Edit decisions + framing plans for parallel rendering.')
    planp.add_argument('--discover',type=Path,default=Path('output/discover'))
    planp.add_argument('--voice',type=Path,default=Path('output/voice'))
    planp.add_argument('--output',type=Path,default=Path('output/edit'))
    planp.add_argument('--workdir',type=Path,default=Path('work/shorts'))
    partp = sub.add_parser('render-part', help='Render one chunk of one aspect of one story.')
    partp.add_argument('--edit',type=Path,default=Path('output/edit'))
    partp.add_argument('--arc',required=True)
    partp.add_argument('--aspect',required=True,choices=['square','vertical'])
    partp.add_argument('--chunk',type=int,required=True)
    partp.add_argument('--chunks',type=int,required=True)
    partp.add_argument('--output',type=Path,default=Path('output/parts'))
    partp.add_argument('--workdir',type=Path,default=Path('work/shorts'))
    finp = sub.add_parser('finish', help='Join rendered chunks into final videos for one story.')
    finp.add_argument('--edit',type=Path,default=Path('output/edit'))
    finp.add_argument('--voice',type=Path,default=Path('output/voice'))
    finp.add_argument('--parts',type=Path,default=Path('output/parts'))
    finp.add_argument('--arc',required=True)
    finp.add_argument('--output',type=Path,default=Path('output/render'))
    doctor = sub.add_parser('doctor')
    doctor.add_argument('--ollama-url',default='http://127.0.0.1:11434')
    args = parser.parse_args(argv)
    try:
        if args.command=='research':
            result=run_research(args.movie,args.workdir,args.output)
            print(json.dumps({k:result[k] for k in ('movie','wikipedia','subtitles','warnings')},default=str,indent=2))
        elif args.command=='discover':
            summary=run_discover(args.movie,args.workdir,args.output,top=args.top,use_whisper=not args.no_whisper,
                                 screen=args.screen,length=args.length)
            print(json.dumps(summary,default=str,indent=2))
        elif args.command=='write':
            summary=run_write(args.source,args.output,max_arcs=args.max_arcs,drafts=args.drafts,model=args.model,
                              arc_index=args.arc_index)
            print(json.dumps(summary,default=str,indent=2))
        elif args.command=='voice':
            summary=run_voice(args.discover,args.scripts,args.output,args.workdir,narrator=args.narrator,
                              model=args.tts_model,max_arcs=args.max_arcs,only=args.arc)
            print(json.dumps(summary,default=str,indent=2))
        elif args.command=='render':
            summary=run_render(args.discover,args.voice,args.output,args.workdir,
                               aspects=tuple(a.strip() for a in args.aspects.split(',') if a.strip()),
                               interpolation=args.interpolation)
            print(json.dumps(summary,default=str,indent=2))
        elif args.command=='package':
            summary=run_package(args.discover,args.scripts,args.voice,args.render,args.output,length=args.length)
            print(json.dumps(summary,default=str,indent=2))
        elif args.command=='edit-plan':
            print(json.dumps(run_edit_plan(args.discover,args.voice,args.output,args.workdir),default=str,indent=2))
        elif args.command=='render-part':
            print(json.dumps(run_render_part(args.edit,args.arc,args.aspect,args.chunk,args.chunks,args.output,
                                             args.workdir),default=str,indent=2))
        elif args.command=='finish':
            print(json.dumps(run_finish(args.edit,args.voice,args.parts,args.arc,args.output),default=str,indent=2))
        elif args.command=='generate':
            result=generate(json.loads(args.request.read_text()),args.workdir,args.output)
            print(json.dumps(result,default=str,indent=2))
        else:
            import importlib.util, shutil, requests
            report = {name:bool(shutil.which(name)) for name in ('ffmpeg','ffprobe')}
            report.update({name:importlib.util.find_spec(name) is not None for name in ('faster_whisper','chatterbox','scenedetect')})
            try:
                response=requests.get(args.ollama_url.rstrip('/')+'/api/tags',timeout=5)
                response.raise_for_status()
                report['ollama_models']=[m['name'] for m in response.json()['models']]
            except requests.RequestException:
                report['ollama_models']=None
            print(json.dumps(report,indent=2))
        return 0
    except (RuntimeError,ValueError,OSError,KeyError) as exc:
        print(f'Shorts failed: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())

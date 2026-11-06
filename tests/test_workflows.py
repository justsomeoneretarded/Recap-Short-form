from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def _load(name):
    return yaml.load((ROOT/'.github/workflows'/name).read_text(),Loader=yaml.BaseLoader)


def test_generate_shorts_has_only_the_four_inputs():
    workflow=_load('generate-shorts.yml')
    assert workflow['name']=='Generate Shorts'
    inputs=workflow['on']['workflow_dispatch']['inputs']
    assert set(inputs)=={'movie','narrator','length','speech_model'}
    assert inputs['narrator']['options']==['warguy','kit-laser','female']
    assert inputs['speech_model']['options']==['original','turbo','nano']
    assert 'pull_request' not in workflow['on'] and 'push' not in workflow['on']


def test_user_text_never_reaches_shell_code_directly():
    workflow=_load('generate-shorts.yml')
    validate=workflow['jobs']['validate']['steps'][1]
    assert validate['env']['SHORTS_INPUTS']=='${{ toJSON(inputs) }}'
    for job in workflow['jobs'].values():
        for step in job.get('steps',[]):
            assert '${{ inputs.' not in step.get('run','')
            assert '${{ needs.validate.outputs' not in step.get('run','')


def test_pipeline_order_and_per_story_matrix():
    jobs=_load('generate-shorts.yml')['jobs']
    assert jobs['discover']['needs']=='validate'
    story=jobs['write-story']
    assert story['strategy']['matrix']['slot']=='${{ fromJSON(needs.discover.outputs.slots) }}'
    assert '--arc-index ${{ matrix.slot }}' in ' '.join(s.get('run','') for s in story['steps'])
    assert jobs['write']['needs']==['write-story'] and 'arcs' in jobs['write']['outputs']
    # Render machines reuse the voice machine's clips; YouTube is only a fallback there.
    assert 'footage-${{ matrix.arc }}' in str(jobs['voice']['steps']) and 'footage-${{ matrix.arc }}' in str(jobs['render']['steps'])
    for step in jobs['render']['steps']:
        if 'YouTube' in step.get('name', '') or 'WARP' in step.get('name', ''):
            assert step.get('if') == "steps.footage.outcome != 'success'"
    assert jobs['voice']['strategy']['matrix']['arc']=='${{ fromJSON(needs.write.outputs.arcs) }}'
    render=jobs['render']['strategy']['matrix']
    assert render['aspect']==['square','vertical'] and render['chunk']==['0','1','2','3']
    voice_runs=' '.join(s.get('run','') for s in jobs['voice']['steps'])
    assert voice_runs.index('shorts_pipeline voice')<voice_runs.index('shorts_pipeline edit-plan')
    assert '--chunks 4' in ' '.join(s.get('run','') for s in jobs['render']['steps'])
    finish_runs=' '.join(s.get('run','') for s in jobs['finish']['steps'])
    assert finish_runs.index('shorts_pipeline finish')<finish_runs.index('shorts_pipeline package')
    assert 'secrets.YOUTUBE_COOKIES' in str(jobs['render']) and 'setup-node' in str(jobs['discover'])

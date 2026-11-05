import json
import subprocess
from pathlib import Path
import pytest
from shorts_pipeline.config import request_config, assign_timeline
from shorts_pipeline.cli import generate, main


def test_independent_short_inputs_and_measured_budget():
    request = request_config({'title':'A short','source':'footage.mp4'})
    assert request['aspect']=='square'
    assert request['narrator']=='warguy'
    for window in [[1,0],[float('nan'),4],[0,1,2]]:
        with pytest.raises(ValueError):
            request_config({'title':'A','source':'x','source_window':window})
    for invalid in [float('nan'),181,0]:
        with pytest.raises(ValueError):
            request_config({'title':'A','source':'x','target_seconds':invalid})
    with pytest.raises(ValueError,match='audio will not be cut'):
        assign_timeline({'beats':[{'duration':16}]},15)
    plan=assign_timeline({'beats':[{'duration':1.25},{'duration':2.5}]},15)
    assert plan['beats'][1]['timeline_start']==1.25
    assert plan['duration']==3.75


def test_complete_cli_path_with_reviewed_audio(tmp_path):
    # Synthetic media exercises pipeline wiring, not model voice quality.
    source=tmp_path/'source.mp4'
    audio=tmp_path/'tone.wav'
    def ff(*args):
        subprocess.run(['ffmpeg','-y','-v','error','-threads','1','-filter_threads','1',*map(str,args)],check=True)
    ff('-f','lavfi','-i','testsrc2=size=160x160:rate=30:duration=2',
       '-c:v','libx264','-threads','1',source)
    ff('-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=1.5',audio)
    storyboard=tmp_path/'plan.json'
    storyboard.write_text(json.dumps({'beats':[{'text':'Reviewed fixture.', 'audio_path':'tone.wav',
        'words':[{'word':'Reviewed','start':.1,'end':.6},{'word':'fixture.','start':.7,'end':1.3}],
        'shots':[{'start':0,'end':2}]}]}))
    out=tmp_path/'out'
    result=generate({'title':'Synthetic pipeline test','source':str(source),'plan':str(storyboard),
                     'target_seconds':15,'fps':30,'preview_width':160,'source_window':[0,2]},tmp_path/'work',out)
    assert Path(result['video']).is_file()
    assert json.loads((out/'status.json').read_text())['state']=='succeeded'
    assert 'REVIEWED FIXTURE.' in (out/'captions.ass').read_text()
    assert (out/'script.txt').read_text()=='Reviewed fixture.'
    assert len(list(out.glob('cover-*.jpg')))==3
    assert json.loads((out/'source-attribution.json').read_text())['source_sha256']
    assert json.loads((out/'source-attribution.json').read_text())['original_source_window']==[0,2]
    with pytest.raises(FileExistsError,match='fresh --output'):
        generate({'title':'Another run','source':str(source)},tmp_path/'work',out)
    assert json.loads((out/'status.json').read_text())['state']=='succeeded'


def test_failure_records_stage_and_never_claims_success(tmp_path):
    out=tmp_path/'out'
    with pytest.raises(FileNotFoundError):
        generate({'title':'Missing source','source':str(tmp_path/'missing.mp4')},tmp_path/'work',out)
    status=json.loads((out/'status.json').read_text())
    assert status['state']=='failed' and status['stage']=='source'
    assert not (out/'final.mp4').exists()

import json
import re
import subprocess
from pathlib import Path

import pytest

from shorts_pipeline.voice import _align_script, _chunks, synthesize_plan, validate_words, voice_reference
from shorts_pipeline.captions import write_captions


def test_imported_audio_preserves_every_word_without_models(tmp_path):
    audio=tmp_path/'voice.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=220:duration=2','-c:a','pcm_s16le',str(audio)],check=True)
    plan={'beats':[{'id':'b1','kind':'narration','text':'Hello there.','audio_path':str(audio),'words':[{'word':'Hello','start':.1,'end':.5},{'word':'there.','start':.6,'end':1.2}]}]}
    voiced=synthesize_plan(plan,'warguy',tmp_path)
    assert voiced['beats'][0]['duration']==pytest.approx(2,abs=.03)
    assert voiced['beats'][0]['timing_provenance']=='provided-word-timings'
    assert 'duration' not in plan['beats'][0]


def test_caption_offsets_and_script_punctuation(tmp_path):
    plan={'beats':[{'id':'b2','text':'Hello there.','duration':2,'timeline_start':4,'words':[{'word':'Hello','start':.1,'end':.5},{'word':'there.','start':.6,'end':1.2}]}]}
    files=write_captions(plan,tmp_path,1080,1080)
    assert '00:00:04,100 --> 00:00:05,200' in files['srt'].read_text()
    assert 'Hello there.' in files['srt'].read_text()
    assert r'\pos(540,648)' in files['ass'].read_text()
    assert 'HELLO THERE.' in re.sub(r'\{[^}]*\}', '', files['ass'].read_text())
    assert json.loads((tmp_path/'caption-timing.json').read_text())['beats'][0]['beat_id']=='b2'


@pytest.mark.parametrize('words',[
    [{'word':'Hello','start':.1,'end':.5}],
    [{'word':'Hello','start':.1,'end':1.2},{'word':'there.','start':.2,'end':.6}],
    [{'word':'Hello','start':.1,'end':.5},{'word':'there.','start':1.9,'end':3}],
])
def test_incomplete_or_invalid_word_timings_rejected(words):
    with pytest.raises(ValueError): validate_words('Hello there.',words,2)


def test_asr_cannot_silently_drop_script_words():
    with pytest.raises(ValueError):
        _align_script('He takes the bag and runs.',[{'word':word,'start':i*.2,'end':i*.2+.1} for i,word in enumerate('He takes bag and runs.'.split())],2)


def test_chunking_preserves_long_script():
    text=' '.join(f'word{i}' for i in range(125))
    pieces=_chunks(text)
    assert ' '.join(pieces)==text
    assert all(len(p.split())<=40 for p in pieces)


def test_dialogue_with_reviewed_timings_preserves_source_span(tmp_path):
    plan={'beats':[{'id':'d1','kind':'dialogue','text':'Go.','shots':[{'start':5,'end':8}],'words':[{'word':'Go.','start':.5,'end':1}]}]}
    voiced=synthesize_plan(plan,'female',tmp_path)
    assert voiced['beats'][0]['duration']==3
    assert voiced['beats'][0]['shots']==plan['beats'][0]['shots']


def test_explicit_reference_directory_has_no_silent_fallback(tmp_path,monkeypatch):
    monkeypatch.setenv('SHORTS_VOICE_DIR',str(tmp_path))
    with pytest.raises(FileNotFoundError): voice_reference('warguy')
    reference=tmp_path/'warguy.ogg'
    reference.write_bytes(b'fixture')
    assert voice_reference('warguy')==reference.resolve()


def test_asr_number_forms_preserve_written_script():
    recognized=[{'word':'He','start':0,'end':.2},{'word':'took','start':.2,'end':.4},
                {'word':'21','start':.4,'end':1.2},{'word':'coins.','start':1.2,'end':1.6}]
    aligned=_align_script('He took twenty one coins.',recognized,2)
    assert [w['word'] for w in aligned]==['He','took','twenty','one','coins.']
    assert aligned[2]['start']==pytest.approx(.4)
    assert aligned[3]['end']==pytest.approx(1.2)
    recognized=[{'word':'twenty','start':0,'end':.5},{'word':'one','start':.5,'end':1}]
    assert _align_script('21',recognized,1)[0]=={'word':'21','start':0,'end':1}

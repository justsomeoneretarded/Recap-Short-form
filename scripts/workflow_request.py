"""Read structured Actions inputs without interpolating user text into shell code."""
import json
import os
import hashlib
from datetime import datetime,timezone
from pathlib import Path
from shorts_pipeline.config import request_config

data = json.loads(os.environ['SHORTS_INPUTS'])
window=json.loads('['+data['source_window']+']') if data.get('source_window','').strip() else None
request = request_config({'title':data['title'], 'source':data['source_url'],
                          'brief':data['brief'], 'story_notes':data.get('story_notes',''),
                          'narrator':data['narrator'], 'target_seconds':float(data['target_seconds']),
                          'aspect':data['aspect'], 'tts_model':data['speech_model'],
                          'script_model':data.get('writer_model','qwen3:4b-instruct-2507-q4_K_M'),'source_window':window})
Path('work').mkdir(exist_ok=True)
Path('work/request.json').write_text(json.dumps(request,indent=2),encoding='utf-8')
if os.environ.get('GITHUB_ENV'):
    source_code=hashlib.sha256(Path('shorts_pipeline/sources.py').read_bytes()).hexdigest()
    key=hashlib.sha256(json.dumps([request['source'],window,source_code,
                                 datetime.now(timezone.utc).date().isoformat()]).encode()).hexdigest()
    with open(os.environ['GITHUB_ENV'],'a',encoding='utf-8') as stream:
        stream.write(f'SHORTS_SOURCE_CACHE_KEY={key}\n')
